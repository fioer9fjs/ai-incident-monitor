"""Unit tests for the LLM-based enricher."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from scripts.enrich_llm import LLMEnricher
from scripts.interfaces import Candidate, RawItem
from scripts.llm_client import LLMResponse


def _cand(title: str = "Test", snippet: str = "snippet") -> Candidate:
    item = RawItem(
        source="test", source_id="t-001",
        url="https://example.com/1", title=title, snippet=snippet,
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        language="en", metadata={},
    )
    return Candidate(raw=item, matched_entities=["OpenAI"], matched_themes=["TECH_AUTOMATION"], confidence=0.8)


class TestLLMEnricher:
    """Mocked LLM tests — no real API calls."""

    def test_llm_success(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = LLMResponse(
            content=json.dumps({
                "event": {
                    "verification_status": "confirmed",
                    "lifecycle_phase": "operation_and_monitoring",
                    "system_classification": "general_purpose_model",
                },
                "mechanism": {
                    "root_cause_category": "model",
                    "failure_mode": "hallucination",
                },
                "consequence": {
                    "harm_domain": "persons_rights",
                    "temporality": "actual",
                    "severity": "high",
                },
                "title": "OpenAI Hallucination Incident",
                "summary": "A detailed summary.",
            }),
            usage={"prompt_tokens": 500, "completion_tokens": 200},
            model="gpt-4o-mini",
        )

        enricher = LLMEnricher(client=mock_client)
        incidents = enricher.enrich([_cand()])

        assert len(incidents) == 1
        inc = incidents[0]
        assert inc.event["verification_status"] == "confirmed"
        assert inc.consequence["severity"] == "high"
        assert inc.title == "OpenAI Hallucination Incident"
        assert inc.metadata["llm_model"] == "gpt-4o-mini"

    def test_llm_invalid_json_falls_back(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = LLMResponse(
            content="not valid json",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model="gpt-4o-mini",
        )

        enricher = LLMEnricher(client=mock_client)
        incidents = enricher.enrich([_cand()])

        assert len(incidents) == 1
        inc = incidents[0]
        # Should fallback to rule-based defaults
        assert inc.event["verification_status"] == "alleged"

    def test_llm_missing_fields_uses_defaults(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = LLMResponse(
            content=json.dumps({
                "title": "Partial",
                "summary": "Only title and summary provided.",
            }),
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            model="gpt-4o-mini",
        )

        enricher = LLMEnricher(client=mock_client)
        incidents = enricher.enrich([_cand()])

        assert len(incidents) == 1
        inc = incidents[0]
        assert inc.event["verification_status"] == "alleged"
        assert inc.event["system_classification"] == "unclassified"
        assert inc.mechanism["root_cause_category"] == "undetermined"
        assert inc.consequence["severity"] == "low"
        assert inc.title == "Partial"

    def test_no_client_falls_back(self):
        """When no client is provided and no API key is set, gracefully fallback."""
        enricher = LLMEnricher(client=None)
        incidents = enricher.enrich([_cand()])
        assert len(incidents) == 1
        inc = incidents[0]
        # Should fallback to rule-based defaults
        assert inc.event["verification_status"] == "alleged"
