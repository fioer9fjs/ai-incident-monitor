"""CI check: the filter engine matches, enforces context, and deduplicates."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.filter_engine import WatchlistFilterEngine
from scripts.interfaces import RawItem


def _item(url: str, names: str, themes: str) -> RawItem:
    return RawItem(
        source="synthetic",
        source_id=url,
        url=url,
        title="",
        snippet="",
        published_at=datetime.now(timezone.utc),
        language="en",
        metadata={"names": names, "themes": themes},
    )


def main() -> None:
    engine = WatchlistFilterEngine()

    items = [
        # Plain entity, no context required -> must pass
        _item("https://a.example/1", "OpenAI announces new model", ""),
        # Context-required entity WITH context theme -> must pass
        _item("https://a.example/2", "tesla fsd crash under investigation",
              "TECH_AUTOMATION"),
        # Context-required entity WITHOUT context -> must NOT pass
        _item("https://a.example/3", "drivers complain about tesla fsd update", ""),
        # Duplicate URL -> must be dropped
        _item("https://a.example/1", "OpenAI announces new model", ""),
        # Theme only, no entity -> below threshold, must NOT pass
        _item("https://a.example/4", "weather report", "SURVEILLANCE"),
    ]

    result = engine.filter(items)
    urls = [c.raw.url for c in result]

    assert "https://a.example/1" in urls, "plain entity must pass"
    assert "https://a.example/2" in urls, "contextual entity with context must pass"
    assert "https://a.example/3" not in urls, "contextual entity without context must fail"
    assert urls.count("https://a.example/1") == 1, "duplicates must be dropped"
    assert "https://a.example/4" not in urls, "theme-only item must fail threshold"

    print(f"OK: filter engine behaves correctly ({len(result)} of {len(items)} passed)")


if __name__ == "__main__":
    main()
