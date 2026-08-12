"""Incident tracker: cross-day deduplication and timeline merging.

Loads existing incidents from the incidents/ directory, matches new
incidents against them by URL or entity overlap, and merges updates
into a single incident file with a chronological updates array.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from scripts.interfaces import Incident

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENTS_DIR = REPO_ROOT / "incidents"

# How far back to look for matching incidents (days)
MERGE_WINDOW_DAYS = 7

# Minimum Jaccard similarity for entity-based matching
ENTITY_OVERLAP_THRESHOLD = 0.5


class IncidentTracker:
    """Tracks incidents across pipeline runs and merges related updates."""

    def __init__(self, merge_window_days: int = MERGE_WINDOW_DAYS):
        self.merge_window_days = merge_window_days
        self._existing: List[Incident] = []
        self._loaded = False

    def _load_existing(self) -> None:
        """Load all existing incidents from the incidents/ directory."""
        if self._loaded:
            return
        if not INCIDENTS_DIR.exists():
            self._loaded = True
            return

        for path in INCIDENTS_DIR.glob("*.md"):
            try:
                incident = self._parse_incident_file(path)
                if incident:
                    self._existing.append(incident)
            except Exception:
                continue
        self._loaded = True

    @staticmethod
    def _parse_incident_file(path: Path) -> Optional[Incident]:
        """Parse a Markdown incident file and extract the Incident object."""
        content = path.read_text(encoding="utf-8")
        # Extract YAML frontmatter
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            return None

        if not fm or "incident_id" not in fm:
            return None

        # Parse date
        date_str = fm.get("date", "")
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            date = datetime.now(timezone.utc)

        return Incident(
            incident_id=fm["incident_id"],
            date=date,
            title=fm.get("title", ""),
            summary="",  # We don't need the full summary for matching
            source_urls=fm.get("source_urls", []),
            event=fm.get("event", {}),
            mechanism=fm.get("mechanism", {}),
            consequence=fm.get("consequence", {}),
            views=fm.get("views", []),
            metadata=fm.get("metadata", {}),
            updates=fm.get("updates", []),
        )

    def merge_or_create(self, new_incidents: List[Incident]) -> List[Incident]:
        """Match new incidents against existing ones and merge or create.

        Returns the final list of incidents to render (existing + new + merged).
        """
        self._load_existing()

        result: List[Incident] = list(self._existing)
        merged_ids: Set[str] = set()

        for new_inc in new_incidents:
            match = self._find_match(new_inc, result)
            if match:
                self._merge_update(match, new_inc)
                merged_ids.add(match.incident_id)
            else:
                result.append(new_inc)

        # Remove duplicates (keep only the merged versions)
        # We keep all incidents, but merged ones have been updated in-place
        return result

    def _find_match(self, new_inc: Incident, candidates: List[Incident]) -> Optional[Incident]:
        """Find the best matching existing incident for a new one."""
        cutoff = new_inc.date - timedelta(days=self.merge_window_days)

        for cand in candidates:
            # Only consider incidents within the merge window
            if cand.date < cutoff:
                continue

            # URL match: same normalized URL
            if self._url_match(new_inc, cand):
                return cand

            # Entity overlap match
            if self._entity_overlap_match(new_inc, cand):
                return cand

        return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip query params and trailing slash for comparison."""
        if not url:
            return ""
        url = url.lower().rstrip("/")
        if "?" in url:
            url = url.split("?")[0]
        return url

    def _url_match(self, a: Incident, b: Incident) -> bool:
        """Check if two incidents share at least one normalized URL."""
        urls_a = {self._normalize_url(u) for u in a.source_urls}
        urls_b = {self._normalize_url(u) for u in b.source_urls}
        return bool(urls_a & urls_b)

    def _entity_overlap_match(self, a: Incident, b: Incident) -> bool:
        """Check if entity overlap exceeds the threshold."""
        entities_a = set(a.metadata.get("matched_entities", []))
        entities_b = set(b.metadata.get("matched_entities", []))
        if not entities_a or not entities_b:
            return False
        intersection = entities_a & entities_b
        union = entities_a | entities_b
        if not union:
            return False
        jaccard = len(intersection) / len(union)
        return jaccard >= ENTITY_OVERLAP_THRESHOLD

    def _merge_update(self, existing: Incident, new_inc: Incident) -> None:
        """Merge a new incident as an update to an existing one."""
        update = {
            "date": new_inc.date.isoformat(),
            "title": new_inc.title,
            "summary": new_inc.summary,
            "source_urls": new_inc.source_urls,
            "event": new_inc.event,
            "mechanism": new_inc.mechanism,
            "consequence": new_inc.consequence,
            "views": new_inc.views,
        }
        existing.updates.append(update)
        # Sort updates chronologically
        existing.updates.sort(key=lambda u: u["date"])

        # Merge source URLs (deduplicated)
        all_urls = set(existing.source_urls) | set(new_inc.source_urls)
        existing.source_urls = sorted(all_urls)

        # Update title if the new one is more specific (longer)
        if len(new_inc.title) > len(existing.title):
            existing.title = new_inc.title

        # Update severity if the new one is higher
        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        old_sev = severity_rank.get(existing.consequence.get("severity", "low"), 0)
        new_sev = severity_rank.get(new_inc.consequence.get("severity", "low"), 0)
        if new_sev > old_sev:
            existing.consequence["severity"] = new_inc.consequence["severity"]
