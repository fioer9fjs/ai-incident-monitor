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


def build_query(since: datetime, entity_records: List[Dict[str, Any]],
                max_rows: int = 500) -> str:
    """Build a cost-controlled SQL query for candidate articles.

    Cost control: DATE filter enables partition pruning, only five
    columns are selected, and LIMIT caps the result set.
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
WHERE DATE >= {since_int}
  AND ({plain_cond} OR {ctx_cond})
LIMIT {max_rows}
"""


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

    def fetch(self, since: datetime) -> List[RawItem]:
        sql = build_query(
            since, all_entity_aliases(load_watchlist()), self.max_rows
        )
        client = self._get_client()
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
                    ),
                    language="unknown",
                    metadata={
                        "themes": str(row["V2Themes"]),
                        "names": str(row["AllNames"])[:2000],
                        "tone": row["V2Tone"],
                    },
                )
            )
        return items
