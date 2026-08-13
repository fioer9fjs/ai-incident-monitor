"""Keyword loader: reads config/keywords.yaml and exposes typed constants.

Provides backward-compatible exports so existing callers (source_gdelt_bigquery,
filter_engine, tests) do not need to change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = REPO_ROOT / "config" / "keywords.yaml"


def _load() -> Dict[str, Any]:
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _flatten(d: Dict[str, Any]) -> List[str]:
    """Recursively extract string values from nested dicts/lists."""
    result: List[str] = []
    for v in d.values():
        if isinstance(v, list):
            result.extend(str(x) for x in v)
        elif isinstance(v, dict):
            result.extend(_flatten(v))
    return result


# ---------------------------------------------------------------------------
# Backward-compatible flat lists (used by source_gdelt_bigquery + filter_engine)
# ---------------------------------------------------------------------------

_data = _load()
_tiers = _data.get("tiers", {})
_t1 = _tiers.get("tier_1", {})
_t2 = _tiers.get("tier_2", {})
_exclusions = _data.get("exclusions", {})

# AI keywords = tier_1 models/products + tier_1 providers + tier_2 models/products + tier_2 providers
AI_KEYWORDS: List[str] = (
    _t1.get("models_products", [])
    + _t1.get("providers", [])
    + _t2.get("models_products", [])
    + _t2.get("providers", [])
)

# Incident keywords = tier_1 incident_terms + tier_2 harms + regulatory + transparency + cset
INCIDENT_KEYWORDS: List[str] = (
    _t1.get("incident_terms", [])
    + _t2.get("harms_mit", [])
    + _t2.get("harms_cset", [])
    + _t2.get("transparency", [])
    + _t2.get("regulatory", [])
)

# Exclusion terms = aviation + financial
EXCLUDE_TERMS: List[str] = (
    _exclusions.get("aviation", {}).get("terms", [])
    + _exclusions.get("financial", {}).get("terms", [])
)

# GDELT V2Tone threshold — only negative-toned articles.
TONE_THRESHOLD = -3.0


# ---------------------------------------------------------------------------
# New structured API (for future modules)
# ---------------------------------------------------------------------------

def load_keywords() -> Dict[str, Any]:
    """Return the full parsed keywords.yaml document."""
    return _data.copy()


def tier_1() -> Dict[str, List[str]]:
    return {
        "models_products": _t1.get("models_products", []),
        "providers": _t1.get("providers", []),
        "incident_terms": _t1.get("incident_terms", []),
    }


def tier_2() -> Dict[str, List[str]]:
    return {
        "models_products": _t2.get("models_products", []),
        "providers": _t2.get("providers", []),
        "harms_mit": _t2.get("harms_mit", []),
        "harms_cset": _t2.get("harms_cset", []),
        "transparency": _t2.get("transparency", []),
        "regulatory": _t2.get("regulatory", []),
    }


def tier_3() -> List[str]:
    t3 = _tiers.get("tier_3", {})
    return t3.get("general_terms", [])


# ---------------------------------------------------------------------------
# Helpers (backward-compatible)
# ---------------------------------------------------------------------------


def alternation(words: list[str]) -> str:
    """Build a BigQuery REGEXP-compatible word-boundary alternation."""
    return r"\b(" + "|".join(words) + r")\b"


def compile_patterns() -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    """Compile AI, incident, and exclusion regex patterns for Python matching."""
    ai_re = re.compile(alternation(AI_KEYWORDS))
    inc_re = re.compile(alternation(INCIDENT_KEYWORDS))
    excl_re = re.compile(alternation(EXCLUDE_TERMS))
    return ai_re, inc_re, excl_re
