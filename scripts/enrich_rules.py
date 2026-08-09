"""Rule-based enrich pipe (v1): classifies candidates into the taxonomy.

Implements the EnrichPipe protocol from scripts/interfaces.py.
Deterministic, CI-safe heuristics derived from matched entities/themes.
Will be superseded by an LLM-based enricher (v2) without interface change.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from scripts.interfaces import Candidate, Incident

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

HARM_FROM_THEME = [
    ("DISCRIMINATION", "persons_rights"),
    ("SURVEILLANCE", "persons_rights"),
    ("WB_670_ICT_SECURITY", "systemic_integrity"),
    ("TECH_AUTOMATION", "systemic_integrity"),
]

SYSTEM_FROM_TERM = [
    (("facial recognition", "face recognition", "biometric"), "biometric_identification"),
    (("autonomous vehicle", "self-driving", "tesla fsd", "tesla autopilot"), "high_risk_regulated"),
    (("large language model", "llm", "generative ai", "genai",
      "chatgpt", "gemini", "claude", "llama"), "general_purpose_model"),
]

CAUSE_FROM_THEME = [
    ("DISCRIMINATION", "data"),
]


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def compute_views(event: Dict[str, Any], mechanism: Dict[str, Any],
                  consequence: Dict[str, Any]) -> List[str]:
    """Evaluate the regulatory views defined in config/taxonomy.yaml."""
    views: List[str] = []
    sev = consequence["severity"]
    harm = consequence["harm_domain"]
    temp = consequence["temporality"]
    system = event["system_classification"]
    root = mechanism["root_cause_category"]

    if (temp == "actual" and sev in ("critical", "high")
            and harm in ("persons_physical", "persons_mental", "persons_rights",
                         "property", "environment")
            and system == "high_risk_regulated"):
        views.append("eu_ai_act_serious_incident")

    if (root == "governance"
            or (temp == "potential"
                and SEVERITY_RANK[sev] >= SEVERITY_RANK["medium"])
            or harm == "systemic_integrity"):
        views.append("nist_ai_rmf_measure_trigger")

    if SEVERITY_RANK[sev] >= SEVERITY_RANK["medium"] or root == "governance":
        views.append("iso_42001_communication_required")

    if (event["verification_status"] != "disputed"
            and root != "undetermined" and harm):
        views.append("trend_analysis_eligible")

    return views


class RuleBasedEnricher:
    """EnrichPipe implementation using deterministic heuristics."""

    def enrich(self, candidates: List[Candidate]) -> List[Incident]:
        return [self._classify(cand) for cand in candidates]

    def _classify(self, cand: Candidate) -> Incident:
        names = (cand.raw.metadata.get("names", "") or "").lower()
        themes = cand.raw.metadata.get("themes", "") or ""

        harm = "systemic_integrity"
        for pattern, domain in HARM_FROM_THEME:
            if pattern in themes:
                harm = domain
                break

        root = "undetermined"
        for pattern, cause in CAUSE_FROM_THEME:
            if pattern in themes:
                root = cause
                break

        system = "unclassified"
        for terms, cls in SYSTEM_FROM_TERM:
            if any(term in names for term in terms):
                system = cls
                break

        severity = "medium" if harm == "persons_rights" else "low"

        event = {
            "verification_status": "alleged",
            "lifecycle_phase": "operation_and_monitoring",
            "system_classification": system,
        }
        mechanism = {
            "root_cause_category": root,
            "failure_mode": (
                f"entities={','.join(cand.matched_entities) or '-'}; "
                f"themes={','.join(cand.matched_themes) or '-'}"
            ),
        }
        consequence = {
            "harm_domain": harm,
            "temporality": "potential",
            "severity": severity,
        }

        title = cand.raw.title or (
            " - ".join(cand.matched_entities) + " media coverage"
            if cand.matched_entities else "AI system media coverage"
        )

        return Incident(
            incident_id=f"{cand.raw.published_at:%Y%m%d}-{_md5(cand.raw.url)}",
            date=cand.raw.published_at,
            title=title,
            summary=cand.raw.snippet[:200],
            source_urls=[cand.raw.url] if cand.raw.url else [],
            event=event,
            mechanism=mechanism,
            consequence=consequence,
            views=compute_views(event, mechanism, consequence),
            metadata={
                "raw_source": cand.raw.source,
                "matched_entities": cand.matched_entities,
                "matched_themes": cand.matched_themes,
                "confidence": cand.confidence,
            },
        )
