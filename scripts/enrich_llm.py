"""LLM-based enrich pipe (v2): classifies candidates into the taxonomy.

Implements the EnrichPipe protocol from scripts/interfaces.py.
Uses a cheap LLM (GPT-4o-mini or Gemini Flash) to extract structured
taxonomy fields from article text.

Falls back to RuleBasedEnricher if the LLM call fails or returns invalid JSON.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from scripts.enrich_rules import RuleBasedEnricher, compute_views
from scripts.interfaces import Candidate, Incident
from scripts.llm_client import LLMClient
from scripts.llm_prompts import SYSTEM_PROMPT, build_user_prompt, parse_json_response


class LLMEnricher:
    """EnrichPipe implementation using a cheap LLM for taxonomy extraction."""

    def __init__(self, client: LLMClient | None = None):
        self.client = client
        self.fallback = RuleBasedEnricher()
        self._cost_log: List[Dict[str, Any]] = []

    def enrich(self, candidates: List[Candidate]) -> List[Incident]:
        incidents: List[Incident] = []
        for cand in candidates:
            try:
                incident = self._classify_with_llm(cand)
            except Exception as exc:
                # Fallback to rule-based on any LLM failure
                print(f"[llm-enrich] fallback for {cand.raw.url}: {exc}")
                incident = self.fallback._classify(cand)
            incidents.append(incident)
        self._print_cost_summary()
        return incidents

    def _classify_with_llm(self, cand: Candidate) -> Incident:
        if self.client is None:
            # Lazy init: will raise if env vars are missing
            self.client = LLMClient()

        user_prompt = build_user_prompt(cand)
        resp = self.client.chat(SYSTEM_PROMPT, user_prompt)

        self._cost_log.append({
            "url": cand.raw.url,
            "model": resp.model,
            "prompt_tokens": resp.usage["prompt_tokens"],
            "completion_tokens": resp.usage["completion_tokens"],
        })

        data = parse_json_response(resp.content)

        event = data.get("event", {})
        mechanism = data.get("mechanism", {})
        consequence = data.get("consequence", {})

        # Validate required fields against taxonomy
        event.setdefault("verification_status", "alleged")
        event.setdefault("lifecycle_phase", "operation_and_monitoring")
        event.setdefault("system_classification", "unclassified")
        mechanism.setdefault("root_cause_category", "undetermined")
        mechanism.setdefault("failure_mode", "")
        consequence.setdefault("harm_domain", "systemic_integrity")
        consequence.setdefault("temporality", "potential")
        consequence.setdefault("severity", "low")

        title = data.get("title", cand.raw.title or "AI incident")
        summary = data.get("summary", cand.raw.snippet[:200])

        return Incident(
            incident_id=f"{cand.raw.published_at:%Y%m%d}-{cand.raw.source_id[:8]}",
            date=cand.raw.published_at,
            title=title,
            summary=summary,
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
                "llm_model": resp.model,
            },
        )

    def _print_cost_summary(self) -> None:
        if not self._cost_log:
            return
        total_prompt = sum(e["prompt_tokens"] for e in self._cost_log)
        total_completion = sum(e["completion_tokens"] for e in self._cost_log)
        print(
            f"[llm-enrich] cost summary: {len(self._cost_log)} calls, "
            f"{total_prompt} prompt + {total_completion} completion tokens"
        )
