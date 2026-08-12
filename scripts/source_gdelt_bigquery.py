"""GDELT GKG source adapter via BigQuery.

Implements the SourceAdapter protocol. Uses the partitioned GKG table
with a two-dimensional URL filter (AI term + incident term), an aviation
exclusion, and a negative tone threshold. Keyword lists are shared with
the filter engine via scripts/keywords.py so source and filter agree.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional

from scripts.interfaces import RawItem
from scripts.keywords import (
    AI_KEYWORDS,
    EXCLUDE_TERMS,
    INCIDENT_KEYWORDS,
    TONE_THRESHOLD,
    alternation,
)

# Partitioned table with _PARTITIONTIME column for proper partition pruning.
GKG_TABLE = "`gdelt-bq.gdeltv2.gkg_partitioned`"

DEFAULT_MAX_ROWS = 5000


def build_query(since: datetime, until: datetime,
                max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Build a cost-controlled query against the partitioned GKG table."""
    if not isinstance(since, datetime) or not isinstance(until, datetime):
        raise TypeError("since and until must be datetime instances")
    if since.tzinfo is None or until.tzinfo is None:
        raise ValueError("since and until must be timezone-aware")
    if since >= until:
        raise ValueError("since must be earlier than until")
    if not (1 <= max_rows <= 50000):
        raise ValueError("max_rows must be between 1 and 50000")

    ai_re = alternation(AI_KEYWORDS)

    inc_re = alternation(INCIDENT_KEYWORDS)
    excl_re = alternation(EXCLUDE_TERMS)

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
            items.append(
                RawItem(
                    source=self.source_name,
                    source_id=f"{row['DATE']}-{str(row['url'])[:32]}",
                    url=str(row["url"]),
                    title="",
                    snippet="",
                    published_at=datetime.strptime(
                        date_str, "%Y%m%d%H%M%S"
                    ).replace(tzinfo=timezone.utc),
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