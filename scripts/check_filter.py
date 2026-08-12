"""CI check: the filter engine scores URL keywords, entities, and themes."""

from __future__ import annotations

from datetime import datetime, timezone

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

    items = [
        # URL AI+incident co-occurrence -> must pass
        _item("https://a.example/openai-chatgpt-hallucination-lawsuit", "", ""),
        # URL AI term only -> must fail
        _item("https://a.example/openai-announces-new-model", "", ""),
        # Aviation exclusion -> must fail
        _item("https://a.example/airline-copilot-error-in-flight", "", ""),
        # Watchlist entity + context theme -> must pass
        _item("https://a.example/4", "OpenAI", "TECH_AUTOMATION"),
        # Duplicate of the first item -> must be dropped
        _item("https://a.example/openai-chatgpt-hallucination-lawsuit", "", ""),
    ]

    result = engine.filter(items)
    urls = [c.raw.url for c in result]

    assert "https://a.example/openai-chatgpt-hallucination-lawsuit" in urls, \
        "URL keyword co-occurrence must pass"
    assert "https://a.example/openai-announces-new-model" not in urls, \
        "AI-only URL must fail"
    assert "https://a.example/airline-copilot-error-in-flight" not in urls, \
        "aviation exclusion must fail"
    assert "https://a.example/4" in urls, \
        "watchlist entity with context theme must pass"
    assert urls.count("https://a.example/openai-chatgpt-hallucination-lawsuit") == 1, \
        "duplicates must be dropped"

    print(f"OK: filter engine behaves correctly ({len(result)} of {len(items)} passed)")


if __name__ == "__main__":
    main()