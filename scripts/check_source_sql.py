"""CI check: the BigQuery source adapter builds a valid, cost-controlled query."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.config_loader import all_entity_aliases, load_watchlist
from scripts.source_gdelt_bigquery import build_query


def main() -> None:
    entities = all_entity_aliases(load_watchlist())
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=2)
    sql = build_query(since, until, entities)

    assert "gdelt-bq.gdeltv2.gkg" in sql, "wrong table"
    assert "DATE BETWEEN" in sql, "missing partition pruning (cost control)"
    assert "REGEXP_CONTAINS" in sql, "missing entity/theme matching"
    assert "LIMIT" in sql, "missing result cap (cost control)"

    print(f"OK: source SQL builds correctly ({len(sql)} chars)")


if __name__ == "__main__":
    main()
