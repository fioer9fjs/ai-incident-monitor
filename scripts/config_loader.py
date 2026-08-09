"""Load and validate YAML configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_taxonomy() -> Dict[str, Any]:
    path = CONFIG_DIR / "taxonomy.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_watchlist() -> Dict[str, Any]:
    path = CONFIG_DIR / "ai_entity_watchlist.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def all_entity_aliases(watchlist: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the watchlist into a list of matchable entity records."""
    records: List[Dict[str, Any]] = []
    for category, payload in watchlist.get("entities", {}).items():
        for entry in payload.get("entries", []):
            requires_context = entry.get(
                "requires_context", category == "technical_terms"
            )
            aliases = [entry["name"].lower()] + [
                alias.lower() for alias in entry.get("aliases", [])
            ]
            records.append(
                {
                    "category": category,
                    "name": entry["name"],
                    "aliases": aliases,
                    "requires_context": bool(requires_context),
                }
            )
    return records
