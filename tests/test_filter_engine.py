"""Unit tests for the watchlist filter engine."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from scripts.filter_engine import WatchlistFilterEngine
from scripts.interfaces import RawItem


def _item(url: str, names: str, themes: str) -> RawItem:
    return RawItem(
        source="test", source_id=url, url=url, title="",
        snippet="", published_at=datetime.now(timezone.utc),
        language="en", metadata={"names": names, "themes": themes},
    )


class TestDeduplication:
    """URL normalization must collapse UTM params and trailing slashes."""

    def test_exact_duplicate_dropped(self):
        engine = WatchlistFilterEngine()
        items = [
            _item("https://a.example/1", "OpenAI", ""),
            _item("https://a.example/1", "OpenAI", ""),
        ]
        result = engine.filter(items)
        assert len(result) == 1

    def test_utm_params_collapsed(self):
        engine = WatchlistFilterEngine()
        items = [
            _item("https://a.example/1?utm_source=x", "OpenAI", ""),
            _item("https://a.example/1", "OpenAI", ""),
        ]
        result = engine.filter(items)
        assert len(result) == 1

    def test_trailing_slash_collapsed(self):
        engine = WatchlistFilterEngine()
        items = [
            _item("https://a.example/1/", "OpenAI", ""),
            _item("https://a.example/1", "OpenAI", ""),
        ]
        result = engine.filter(items)
        assert len(result) == 1


class TestContextRequirement:
    """Entities marked requires_context need a theme hit to pass."""

    def test_tesla_fsd_without_context_blocked(self):
        engine = WatchlistFilterEngine()
        items = [_item("https://a.example/1", "tesla fsd update", "")]
        result = engine.filter(items)
        assert len(result) == 0

    def test_tesla_fsd_with_context_passes(self):
        engine = WatchlistFilterEngine()
        items = [_item("https://a.example/1", "tesla fsd crash", "TECH_AUTOMATION")]
        result = engine.filter(items)
        assert len(result) == 1
        assert result[0].confidence >= engine.min_confidence


class TestConfidence:
    """Plain entities must score above the default threshold."""

    def test_openai_plain_passes(self):
        engine = WatchlistFilterEngine()
        items = [_item("https://a.example/1", "OpenAI announces model", "")]
        result = engine.filter(items)
        assert len(result) == 1
        assert result[0].confidence >= engine.min_confidence

    def test_theme_only_fails_threshold(self):
        engine = WatchlistFilterEngine()
        items = [_item("https://a.example/1", "weather report", "SURVEILLANCE")]
        result = engine.filter(items)
        assert len(result) == 0
