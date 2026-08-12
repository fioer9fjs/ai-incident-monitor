"""Unit tests for the incident tracker (cross-day deduplication)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts.incident_tracker import IncidentTracker
from scripts.interfaces import Incident


def _inc(
    incident_id: str,
    date: datetime,
    url: str = "https://example.com/1",
    entities: list[str] | None = None,
    severity: str = "low",
) -> Incident:
    return Incident(
        incident_id=incident_id,
        date=date,
        title="Test",
        summary="summary",
        source_urls=[url],
        event={"verification_status": "alleged", "lifecycle_phase": "operation_and_monitoring", "system_classification": "unclassified"},
        mechanism={"root_cause_category": "undetermined", "failure_mode": ""},
        consequence={"harm_domain": "systemic_integrity", "temporality": "potential", "severity": severity},
        views=[],
        metadata={"matched_entities": entities or []},
        updates=[],
    )


class TestURLMatching:
    def test_same_url_merges(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1")]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/1")]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 1
        assert len(result[0].updates) == 1
        assert result[0].incident_id == "20260101-abc"

    def test_different_urls_create_separate(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1")]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/2")]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 2

    def test_utm_params_collapsed(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1")]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/1?utm=x")]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 1


class TestEntityOverlap:
    def test_high_overlap_merges(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), entities=["OpenAI", "ChatGPT"])]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), entities=["OpenAI", "ChatGPT", "GPT-4"])]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 1

    def test_low_overlap_creates_separate(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1", entities=["OpenAI"])]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/2", entities=["Tesla", "FSD"])]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 2


class TestMergeWindow:
    def test_old_incident_ignored(self):
        tracker = IncidentTracker(merge_window_days=7)
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1")]
        new = [_inc("20260115-def", datetime(2026, 1, 15, tzinfo=timezone.utc), url="https://a.example/1")]

        result = tracker.merge_or_create(existing + new)
        assert len(result) == 2


class TestMergeEffects:
    def test_severity_escalation(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1", severity="low")]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/1", severity="high")]

        result = tracker.merge_or_create(existing + new)
        assert result[0].consequence["severity"] == "high"

    def test_source_urls_merged(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1", entities=["OpenAI"])]
        new = [_inc("20260102-def", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/2", entities=["OpenAI"])]

        result = tracker.merge_or_create(existing + new)
        assert "https://a.example/1" in result[0].source_urls
        assert "https://a.example/2" in result[0].source_urls

    def test_updates_sorted_chronologically(self):
        tracker = IncidentTracker()
        existing = [_inc("20260101-abc", datetime(2026, 1, 1, tzinfo=timezone.utc), url="https://a.example/1")]
        new1 = [_inc("20260103-def", datetime(2026, 1, 3, tzinfo=timezone.utc), url="https://a.example/1")]
        new2 = [_inc("20260102-ghi", datetime(2026, 1, 2, tzinfo=timezone.utc), url="https://a.example/1")]

        result = tracker.merge_or_create(existing + new1 + new2)
        assert len(result) == 1
        dates = [u["date"][:10] for u in result[0].updates]
        assert dates == ["2026-01-02", "2026-01-03"]
