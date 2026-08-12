"""Unit tests for BigQuery source adapter query builder."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.source_gdelt_bigquery import build_query


class TestBuildQueryValidation:
    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            build_query(
                datetime(2026, 1, 1),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
            )

    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError, match="earlier than"):
            build_query(
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_rejects_zero_max_rows(self):
        with pytest.raises(ValueError, match="max_rows"):
            build_query(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                max_rows=0,
            )

    def test_includes_partition_pruning(self):
        sql = build_query(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        assert "_PARTITIONTIME" in sql
        assert "gkg_partitioned" in sql

    def test_includes_limit(self):
        sql = build_query(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        assert "LIMIT 5000" in sql
