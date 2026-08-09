"""Rule-based filter engine: second-pass refinement of raw candidates.

Implements the FilterEngine protocol from scripts/interfaces.py.
Matches raw items against the curated entity watchlist and contextual
GKG themes, enforces context requirements, scores confidence, and
deduplicates by URL.
"""

from __future__ import annotations

import re
from typing import List

from scripts.config_loader import all_entity_aliases, load_watchlist
from scripts.interfaces import Candidate, RawItem

CONTEXT_THEME_PATTERNS = [
    "TECH_AUTOMATION",
    "TECH_BIGDATA",
    "SURVEILLANCE",
    "DISCRIMINATION",
    "WB_670_ICT_SECURITY",
    "EPU_CATS_REGULATION",
]

DEFAULT_MIN_CONFIDENCE = 0.3

# Confidence weights
W_PLAIN_ENTITY = 0.4
W_CONTEXT_ENTITY = 0.3
W_CONTEXT_THEME = 0.2


class WatchlistFilterEngine:
    """FilterEngine implementation based on watchlist + theme context."""

    def __init__(self, min_confidence: float = DEFAULT_MIN_CONFIDENCE):
        self.min_confidence = min_confidence
        self.entities = all_entity_aliases(load_watchlist())
        self.theme_re = re.compile(
            "|".join(re.escape(t) for t in CONTEXT_THEME_PATTERNS)
        )

    def filter(self, items: List[RawItem]) -> List[Candidate]:
        seen_urls = set()
        candidates: List[Candidate] = []
        for item in items:
            if item.url:
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
            candidate = self._score(item)
            if candidate.confidence >= self.min_confidence:
                candidates.append(candidate)
        return candidates

    def _score(self, item: RawItem) -> Candidate:
        names = (item.metadata.get("names", "") or "").lower()
        themes = item.metadata.get("themes", "") or ""
        has_context = bool(self.theme_re.search(themes))

        matched_entities: List[str] = []
        matched_themes: List[str] = []
        confidence = 0.0

        if has_context:
            confidence += W_CONTEXT_THEME
            matched_themes = [t for t in CONTEXT_THEME_PATTERNS if t in themes]

        for record in self.entities:
            if not any(alias in names for alias in record["aliases"]):
                continue
            if record["requires_context"] and not has_context:
                continue
            matched_entities.append(record["name"])
            confidence += (
                W_CONTEXT_ENTITY if record["requires_context"] else W_PLAIN_ENTITY
            )

        return Candidate(
            raw=item,
            matched_entities=sorted(set(matched_entities)),
            matched_themes=matched_themes,
            matched_cameo=[],
            confidence=min(round(confidence, 2), 1.0),
        )
