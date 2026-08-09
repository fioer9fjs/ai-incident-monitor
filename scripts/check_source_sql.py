"""CI check: the BigQuery source builds a partition-pruned, cost-controlled query."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.source_gdelt_bigquery import build_query


def main() -> None:
    until = datetime.now(timezone.utc)
    since = until - timedelta(hours=24)
    sql = build_query(since, until)

    assert "gkg_partitioned" in sql, "must target the partitioned table"
    assert "_PARTITIONTIME" in sql, "must use the partition column"
    assert r"\b(ai|" in sql, "must include AI keyword alternation"
    assert r"\b(incident|" in sql, "must include incident keyword alternation"
    assert "NOT REGEXP_CONTAINS" in sql, "must include exclusion filter"
    assert "< -3.0" in sql, "must include tone threshold"
    assert "LIMIT" in sql, "must cap result size"

    print(f"OK: source SQL builds correctly ({len(sql)} chars)")


if __name__ == "__main__":
    main()
