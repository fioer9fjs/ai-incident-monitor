"""GDELT Global Knowledge Graph source adapter via Google BigQuery.

Implements the SourceAdapter protocol from scripts/interfaces.py.
Queries the public GKG 2.0 table using a multi-dimensional filter:
curated AI entities (watchlist) combined with contextual GKG themes.
CAMEO/event-based filtering is intentionally a separate future adapter.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scripts.config_loader import all_entity_aliases, load_watchlist
from scripts.interfaces import RawItem

GKG_TABLE = "`gdelt-bq.gdeltv2.gkg`"

CONTEXT_THEME_PATTERNS = [
    "TECH_AUTOMATION",
    "TECH_BIGDATA",
    "SURVEILLANCE",
    "DISCRIMINATION",
    "WB_670_ICT_SECURITY",
    "EPU_CATS_REGULATION",
]

DEFAULT_MAX_ROWS = 500


def build_query(
    since: datetime,
    until: datetime,
    entity_records: List[Dict[str, Any]],
    max_rows: int = DEFAULT_MAX_ROWS,
) -> str:
    """Build a cost-controlled SQL query for candidate articles.

    Cost control: explicit BETWEEN on DATE enables partition pruning,
    only six columns are selected, and LIMIT caps the result set.
    """
    if not entity_records:
        raise ValueError("entity_records must not be empty")

    plain = [r for r in entity_records if not r["requires_context"]]
    contextual = [r for r in entity_records if r["requires_context"]]

    plain_re = "|".join(
        re.escape(a) for a in sorted({a for r in plain for a in r["aliases"]})
    )
    ctx_re = "|".join(
        re.escape(a) for a in sorted({a for r in contextual for a in r["aliases"]})
    )
    theme_re = "|".join(re.escape(t) for t in CONTEXT_THEME_PATTERNS)

    since_int = int(since.strftime("%Y%m%d000000"))
    until_int = int(until.strftime("%Y%m%d000000"))

    plain_cond = f"REGEXP_CONTAINS(LOWER(AllNames), r'{plain_re}')"
    ctx_cond = (
        f"(REGEXP_CONTAINS(LOWER(AllNames), r'{ctx_re}') "
        f"AND REGEXP_CONTAINS(V2Themes, r'{theme_re}'))"
    )

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
  AND ({plain_cond} OR {ctx_cond})
LIMIT {max_rows}
"""


class GdeltBigQuerySource:
    """SourceAdapter implementation for the GDELT GKG 2.0 BigQuery table."""

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
        """Fetch candidates from the GKG table within the time window."""
        from google.cloud import bigquery

        entities = all_entity_aliases(load_watchlist())
        sql = build_query(since, until, entities, self.max_rows)
        client = self._get_client()

        # Dry run first: estimate scanned bytes without executing.
        dry_job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                dry_run=True, use_query_cache=False
            ),
        )
        print(f"[dry-run] estimated bytes scanned: {dry_job.total_bytes_processed:,}")

        rows = client.query(sql).result()

        items: List[RawItem] = []
        for row in rows:
            items.append(
                RawItem(
                    source=self.source_name,
                    source_id=str(row["GKGRecordId"]),
                    url=str(row["DocumentIdentifier"]),
                    title="",  # GKG has no title; filled by the enrich stage
                    snippet=str(row["V2Themes"])[:500],
                    published_at=datetime.strptime(
                        str(row["DATE"])[:14], "%Y%m%d%H%M%S"
                    ).replace(tzinfo=timezone.utc),
                    language="unknown",
                    metadata={
                        "themes": str(row["V2Themes"]),
                        "names": str(row["AllNames"])[:2000],
                        "tone": row["V2Tone"],
                    },
                )
            )
        return items
