"""Unit tests for the rule-based enricher."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.enrich_rules import RuleBasedEnricher, compute_views
from scripts.filter_engine import WatchlistFilterEngine
from scripts.interfaces import RawItem


def _cand(url: str, names: str, themes: str):
    item = RawItem(
        source="test", source_id=url, url=url, title="",
        snippet="test", published_at=datetime.now(timezone.utc),
        language="en", metadata={"names": names, "themes": themes},
    )
    return WatchlistFilterEngine().filter([item])[0]


class TestClassification:
    def test_discrimination_maps_to_persons_rights(self):
        enricher = RuleBasedEnricher()
        cand = _cand("https://a.example/1", "OpenAI model", "DISCRIMINATION_RACE")
        inc = enricher.enrich([cand])[0]
        assert inc.consequence["harm_domain"] == "persons_rights"
        assert inc.consequence["severity"] == "medium"

    def test_no_theme_defaults_to_systemic_integrity(self):
        enricher = RuleBasedEnricher()
        cand = _cand("https://a.example/1", "OpenAI model", "")
        inc = enricher.enrich([cand])[0]
        assert inc.consequence["harm_domain"] == "systemic_integrity"


class TestIncidentIdStability:
    def test_same_url_same_id(self):
        enricher = RuleBasedEnricher()
        cand = _cand("https://a.example/stable", "OpenAI", "")
        id1 = enricher.enrich([cand])[0].incident_id
        id2 = enricher.enrich([cand])[0].incident_id
        assert id1 == id2


class TestViews:
    def test_iso_42001_triggered_on_medium_severity(self):
        event = {"verification_status": "alleged", "lifecycle_phase": "operation_and_monitoring", "system_classification": "unclassified"}
        mechanism = {"root_cause_category": "undetermined"}
        consequence = {"harm_domain": "persons_rights", "temporality": "potential", "severity": "medium"}
        views = compute_views(event, mechanism, consequence)
        assert "iso_42001_communication_required" in views
