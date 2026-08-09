"""CI check: the rule-based enricher classifies deterministically."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.enrich_rules import RuleBasedEnricher
from scripts.filter_engine import WatchlistFilterEngine
from scripts.interfaces import RawItem


def _item(url: str, names: str, themes: str) -> RawItem:
    return RawItem(
        source="synthetic", source_id=url, url=url, title="",
        snippet="sample", published_at=datetime.now(timezone.utc),
        language="en", metadata={"names": names, "themes": themes},
    )


def main() -> None:
    engine = WatchlistFilterEngine()
    enricher = RuleBasedEnricher()

    sample = _item("https://a.example/d1", "OpenAI model", "DISCRIMINATION_RACE")
    cands = engine.filter([sample])
    assert cands, "discrimination item must pass the filter"

    inc = enricher.enrich(cands)[0]
    assert inc.consequence["harm_domain"] == "persons_rights"
    assert inc.mechanism["root_cause_category"] == "data"
    assert inc.consequence["severity"] == "medium"
    assert "iso_42001_communication_required" in inc.views

    # Stable identity: same URL must always produce the same incident_id
    inc2 = enricher.enrich(engine.filter([sample]))[0]
    assert inc.incident_id == inc2.incident_id, "incident_id must be stable per URL"

    print("OK: enricher classifies deterministically")


if __name__ == "__main__":
    main()
