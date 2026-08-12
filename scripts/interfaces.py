"""Stable module contracts for the AI Incident Monitor pipeline.

Each pipeline stage is implemented as a class fulfilling one of the
protocols below. Modules may be replaced independently as long as
they respect these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Protocol, runtime_checkable


@dataclass
class RawItem:
    """Normalized unit of raw input from any source adapter."""

    source: str
    source_id: str
    url: str
    title: str
    snippet: str
    published_at: datetime
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    """A raw item that passed the filter stage."""

    raw: RawItem
    matched_entities: List[str] = field(default_factory=list)
    matched_themes: List[str] = field(default_factory=list)
    matched_cameo: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Incident:
    """A fully classified incident conforming to config/taxonomy.yaml."""

    incident_id: str
    date: datetime
    title: str
    summary: str
    source_urls: List[str]
    event: Dict[str, Any]
    mechanism: Dict[str, Any]
    consequence: Dict[str, Any]
    views: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    updates: List[Dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class SourceAdapter(Protocol):
    def fetch(self, since: datetime, until: datetime) -> List[RawItem]: ...



@runtime_checkable
class FilterEngine(Protocol):
    def filter(self, items: List[RawItem]) -> List[Candidate]: ...


@runtime_checkable
class EnrichPipe(Protocol):
    def enrich(self, candidates: List[Candidate]) -> List[Incident]: ...


@runtime_checkable
class RenderAdapter(Protocol):
    def render(self, incidents: List[Incident]) -> Dict[str, str]: ...
