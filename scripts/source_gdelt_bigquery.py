"""GDELT Global Knowledge Graph source adapter via Google BigQuery.

Implements the SourceAdapter protocol from scripts/interfaces.py.
Queries the public GKG 2.0 table using a multi-dimensional filter:
curated AI entities (watchlist) combined with contextual GKG themes.
CAMEO/event-based filtering is intentionally a separate future adapter.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List

from scripts.config_loader import all_entity_aliases, load_watchlist
from scripts.interfaces import RawItem

GKG_TABLE = "`gdelt-bq.gdeltv2.gkg`"

# GKG themes providing incident / regulation context (consequence side)
CONTEXT_THEME_PATTERNS = [
    "TECH_AUTOMATION",
    "TECH_BIGDATA",
    "SURVEILLANCE",
    "DISCRIMINATION",
    "WB_670_ICT_SECURITY",
    "EPU_CATS_REGULATION",
]


def build_query(
    since: datetime,
    until: datetime,
    entity_records: List[Dict[str, Any]],
    max_rows: int = DEFAULT_MAX_ROWS,
) -> str:
    """Build a cost-controlled SQL query for candidate articles.

    Cost control: Explicit BETWEEN on DATE enables partition pruning,
    only five columns are selected, and LIMIT caps the result set.
    """
    if not entity_records:
        raise ValueError("entity_records must not be empty")

    plain_aliases = [
        alias
        for record in entity_records
        if not record["requires_context"]
        for alias in record["aliases"]
    ]
    contextual_aliases = [
        alias
        for record in entity_records
        if record["requires_context"]
        for alias in record["aliases"]
    ]

    plain_re = "|".join(re.escape(a) for a in sorted(set(plain_aliases)))
    ctx_re = "|".join(re.escape(a) for a in sorted(set(contextual_aliases)))
    theme_re = "|".join(re.escape(t) for t in CONTEXT_THEME_PATTERNS)

    since_int = int(since.strftime("%Y%m%d000000"))
    until_int = int(until.strftime("%Y%m%d000000"))

    return f"""
SELECT
  GKGRecordId,
  DATE,
  DocumentIdentifier,
  V2Themes,
  AllNames,
  V2Tone
FROM {GKG_TABLE}
WHERE DATE BETWEEN {since_int} AND {until_int}
  AND (
    REGEXP_CONTAINS(LOWER(AllNames), r'{plain_re}')
    OR (
      REGEXP_CONTAINS(LOWER(AllNames), r'{ctx_re}')
      AND REGEXP_CONTAINS(V2Themes, r'{theme_re}')
    )
  )
LIMIT {max_rows}
""".strip()


class GdeltBigQuerySource:
    """SourceAdapter implementation for the GDELT GKG 2.0 BigQuery table."""

    source_name = "gdelt_gkg"

    def __init__(self, project: str | None = None, max_rows: int = 500):
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
    """Fetch candidates from GKG table within the time window."""
    entities = all_entity_aliases(load_watchlist())
    sql = build_query(since, until, entities, self.max_rows)
    client = self._get_client()
    
    # Dry run to estimate bytes before executing
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    dry_job = client.query(sql, job_config=job_config)
    print(f"[dry-run] estimated bytes scanned: {dry_job.total_bytes_processed:,}")
    
    # Actual query
    rows = client.query(sql).result()
    items: List[RawItem] = []
    
    for row in rows:
        items.append(
            RawItem(
                source="gdelt_gkg",
                source_id=str(row["GKGRecordId"]),
                url=str(row["DocumentIdentifier"]),
                title="",
                snippet="",
                published_at=datetime.strptime(
                    str(row["DATE"]), "%Y%m%d%H%M%S"
                ).replace(tzinfo=timezone.utc),
                language="",
                metadata={
                    "themes": row["V2Themes"],
                    "names": row["AllNames"],
                    "tone": row["V2Tone"],
                },
            )
        )
    return items
