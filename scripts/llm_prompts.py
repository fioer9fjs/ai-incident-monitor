"""Prompt templates for LLM-based taxonomy enrichment.

All prompts are deterministic (temperature=0) and request structured JSON
output so the response can be parsed without regex heuristics.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from scripts.interfaces import Candidate


SYSTEM_PROMPT = """You are an expert AI incident analyst. Your task is to classify news articles about AI incidents according to a strict taxonomy.

You must respond with a single JSON object. Do not include markdown formatting, explanations, or any text outside the JSON object.

The JSON must follow this exact schema:
{
  "event": {
    "verification_status": "alleged|confirmed|disputed",
    "lifecycle_phase": "design_and_training|testing_and_validation|deployment_and_integration|operation_and_monitoring|decommissioning",
    "system_classification": "high_risk_regulated|general_purpose_model|autonomous_agent|biometric_identification|critical_infrastructure_component|dual_use_security|unclassified"
  },
  "mechanism": {
    "root_cause_category": "data|model|human|governance|external|undetermined",
    "failure_mode": "string describing the concrete failure"
  },
  "consequence": {
    "harm_domain": "persons_physical|persons_mental|persons_rights|property|environment|systemic_integrity|societal",
    "temporality": "actual|potential|latent",
    "severity": "critical|high|medium|low"
  },
  "title": "A concise, factual title for the incident (max 120 chars)",
  "summary": "A 2-3 sentence summary of what happened and why it matters"
}

Classification rules:
- verification_status: "alleged" unless the article explicitly states official confirmation or regulatory finding
- system_classification: infer from the AI system described (facial recognition = biometric_identification, self-driving cars = high_risk_regulated, ChatGPT/LLMs = general_purpose_model)
- root_cause_category: "data" for bias/poisoning issues, "model" for hallucinations/robustness failures, "human" for negligence/misuse, "governance" for missing risk assessment, "external" for adversarial attacks
- harm_domain: "persons_physical" for injuries/deaths, "persons_rights" for discrimination/privacy, "systemic_integrity" for safety failures without direct human harm, "societal" for democratic manipulation
- temporality: "actual" if harm already occurred, "potential" if it's a near miss or risk disclosure, "latent" if it's a discovered vulnerability not yet exploited
- severity: "critical" for deaths or systemic collapse, "high" for significant harm or regulatory action, "medium" for moderate impact, "low" for minor issues
"""


def build_user_prompt(candidate: Candidate) -> str:
    """Build a user prompt from a filtered candidate."""
    raw = candidate.raw
    metadata_lines = []
    if candidate.matched_entities:
        metadata_lines.append(f"Matched entities: {', '.join(candidate.matched_entities)}")
    if candidate.matched_themes:
        metadata_lines.append(f"Matched themes: {', '.join(candidate.matched_themes)}")

    parts = [
        "=== ARTICLE ===",
        f"Title: {raw.title or '(no title)'}",
        f"URL: {raw.url}",
        f"Date: {raw.published_at:%Y-%m-%d}",
        "",
        "=== CONTENT ===",
        raw.snippet or "(no snippet available)",
        "",
    ]

    if raw.metadata.get("full_text"):
        parts.extend([
            "=== FULL TEXT (first 3000 chars) ===",
            str(raw.metadata.get("full_text", ""))[:3_000],
            "",
        ])

    if metadata_lines:
        parts.extend([
            "=== METADATA ===",
            "\n".join(metadata_lines),
            "",
        ])

    parts.append("Classify this article according to the taxonomy. Respond with JSON only.")
    return "\n".join(parts)


def parse_json_response(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from an LLM response.

    Handles common LLM formatting issues (markdown code blocks, extra whitespace).
    """
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)
