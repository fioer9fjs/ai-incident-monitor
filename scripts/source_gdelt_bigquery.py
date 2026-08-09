"""GDELT GKG source adapter via BigQuery.

Implements the SourceAdapter protocol. Uses the partitioned GKG table
with a two-dimensional filter: AI keywords AND incident keywords must
both appear in the document URL, combined with a negative tone threshold
and an aviation-term exclusion (to avoid Copilot false positives).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from scripts.interfaces import RawItem

# Partitioned table with _PARTITIONTIME column — enables proper partition pruning.
GKG_TABLE = "`gdelt-bq.gdeltv2.gkg_partitioned`"

# AI-related keywords (case-insensitive, word-boundary anchored).
AI_KEYWORDS = [
    "ai", "artificial-intelligence", "genai", "generative-ai",
    "machine-learning", "chatgpt", "openai", "gpt", "llm",
    "deepmind", "anthropic", "claude", "copilot", "gemini",
    "mistral", "huggingface", "hugging-face", "xai",
    "midjourney", "stable-diffusion", "sora", "perplexity", "grok",
]

# Incident-related keywords — must co-occur with an AI keyword.
INCIDENT_KEYWORDS = [
    "incident", "failure", "outage", "glitch", "breach", "hack",
    "flaw", "vulnerability", "hallucination", "deepfake", "bias",
    "jailbreak", "lawsuit", "fraud", "fine", "ban", "probe",
    "investigation", "violation", "copyright", "penalty", "leak",
    "exploit", "scam", "malware", "error", "crash", "bug",
    "malfunction", "misinformation", "disinformation",
    "plagiarism", "propaganda",
]

# Aviation terms to exclude (avoid "Copilot" false positives in airline news).
EXCLUDE_TERMS = ["flight", "plane", "aircraft", "aviation",
                 "airline", "airlines", "pilot", "jet"]

DEFAULT_MAX_ROWS = 5000
TONE_THRESHOLD = -3.0


def _build_alternation(words: List[str]) -> str:
    return r"\b(" + "|".join(words) + r")\b"


def build_query(
    since: datetime,
    until: datetime,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> str:
    """Build a cost-controlled query against the partitioned GKG table.

    Cost control relies on _PARTITIONTIME pruning plus three additional
    reductions: URL-only regex matching, negative tone filter, and a
    hard LIMIT cap.
    """
    ai_re = _build_alternation(AI_KEYWORDS)
    inc_re = _build_alternation(INCIDENT_KEYWORDS)
    excl_re = _build_alternation(EXCLUDE_TERMS)

    # BigQuery accepts ISO-8601 timestamps directly.
    since_iso = since.isoformat()
    until_iso = until.isoformat()

    return f"""
SELECT
  DATE,
  DocumentIdentifier AS url,
  SourceCommonName AS source_name,
  CAST(SPLIT(V2Tone, ',')[OFFSET(0)] AS FLOAT64) AS tone,
  V2Themes,
  AllNames
FROM {GKG_TABLE}
WHERE _PARTITIONTIME BETWEEN TIMESTAMP('{since_iso}') AND TIMESTAMP('{until_iso}')
  AND REGEXP_CONTAINS(LOWER(DocumentIdentifier), r'{ai_re}')
  AND REGEXP_CONTAINS(LOWER(DocumentIdentifier), r'{inc_re}')
  AND NOT REGEXP_CONTAINS(LOWER(DocumentIdentifier), r'{excl_re}')
  AND CAST(SPLIT(V2Tone, ',')[OFFSET(0)] AS FLOAT64) < {TONE_THRESHOLD}
LIMIT {max_rows}
"""


class GdeltBigQuerySource:
    """SourceAdapter implementation for the partitioned GKG table."""

    source_name = "gdelt_gkg"

    def __init__(self, project: Optional[str] = None,
                 max_rows: int = DEFAULT_MAX_ROWS):
        self.project = project or os.environ.get("GCP_PROJECT")
        self.max_rows = max_rows
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import bigquery
            except ImportError as exc:
                raise RuntimeError(
                    "google-cloud-bigquery is not installed"
                ) from exc
            if not self.project:
                raise RuntimeError(
                    "GCP_PROJECT environment variable is not set"
                )
            self._client = bigquery.Client(project=self.project)
        return self._client

    def fetch(self, since: datetime, until: datetime) -> List[RawItem]:
        """Fetch candidates from the partitioned GKG table."""
        from google.cloud import bigquery

        sql = build_query(since, until, self.max_rows)
        client = self._get_client()

        dry_job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                dry_run=True, use_query_cache=False
            ),
        )
        estimated_bytes = dry_job.total_bytes_processed
        print(f"[dry-run] estimated bytes scanned: {estimated_bytes:,} "
              f"({estimated_bytes / (1024**3):.3f} GB)")

        if estimated_bytes > 100 * 1024 * 1024 * 1024:
            raise RuntimeError(
                f"Query would scan {estimated_bytes / (1024**3):.2f} GB, "
                f"exceeding 100 GB safety limit."
            )

        rows = client.query(sql).result()

        items: List[RawItem] = []
        for row in rows:
            date_str = str(row["DATE"])[:14].ljust(14, "0")
            published_at = datetime.strptime(
                date_str, "%Y%m%d%H%M%S"
            ).replace(tzinfo=timezone.utc)

            items.append(
                RawItem(
                    source=self.source_name,
                    source_id=f"{row['DATE']}-{row['url'][:32]}",
                    url=str(row["url"]),
                    title="",
                    snippet="",
                    published_at=published_at,
                    language="unknown",
                    metadata={
                        "source_name": str(row["source_name"]),
                        "tone": float(row["tone"]),
                        "themes": str(row["V2Themes"]),
                        "names": str(row["AllNames"])[:2000],
                    },
                )
            )
        return items
