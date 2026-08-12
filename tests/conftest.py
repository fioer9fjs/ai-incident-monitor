"""pytest fixtures for AI Incident Monitor."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from scripts.interfaces import RawItem


@pytest.fixture
def raw_item_factory():
    """Return a factory that creates RawItem instances."""
    def _make(
        url: str = "https://example.com/1",
        names: str = "",
        themes: str = "",
        source_id: str = "test-001",
    ) -> RawItem:
        return RawItem(
            source="test",
            source_id=source_id,
            url=url,
            title="Test title",
            snippet="Test snippet",
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            language="en",
            metadata={"names": names, "themes": themes},
        )
    return _make
