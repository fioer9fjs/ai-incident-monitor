"""Pipeline orchestrator: chains Source → Filter → Enrich → Render.

Run modes:
  --dry-run     Skip source adapter, use synthetic sample data
  --since DATE  Override the fetch window (ISO 8601, default: 2 days ago)

Outputs Markdown incident files into the incidents/ directory.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from scripts.config_loader import load_taxonomy, load_watchlist
from scripts.filter_engine import WatchlistFilterEngine
from scripts.enrich_rules import RuleBasedEnricher
from scripts.interfaces import (
    Candidate,
    EnrichPipe,
    FilterEngine,
    Incident,
    RawItem,
    RenderAdapter,
    SourceAdapter,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
INCIDENTS_DIR = REPO_ROOT / "incidents"


# ---------------------------------------------------------------------------
# Stubs — minimal implementations fulfilling the module contracts.
# Each stub will be replaced by a real module in subsequent steps.
# ---------------------------------------------------------------------------


class StubFilter:
    """Pass-through filter until the real filter engine is built."""

    def filter(self, items: List[RawItem]) -> List[Candidate]:
        return [
            Candidate(raw=item, matched_entities=[], matched_themes=[],
                      matched_cameo=[], confidence=1.0)
            for item in items
        ]


class StubEnrich:
    """Minimal enrich: populates required taxonomy fields with placeholders."""

    def __init__(self) -> None:
        self.taxonomy = load_taxonomy()
        self.watchlist = load_watchlist()

    def enrich(self, candidates: List[Candidate]) -> List[Incident]:
        incidents: List[Incident] = []
        for i, cand in enumerate(candidates):
            incidents.append(
                Incident(
                    incident_id=f"{cand.raw.published_at:%Y%m%d}-{cand.raw.source_id[:8] or i}",
                    date=cand.raw.published_at,
                    title=cand.raw.title or "(untitled candidate)",
                    summary=cand.raw.snippet[:200],
                    source_urls=[cand.raw.url] if cand.raw.url else [],
                    event={
                        "verification_status": "alleged",
                        "lifecycle_phase": "operation_and_monitoring",
                        "system_classification": "unclassified",
                    },
                    mechanism={
                        "root_cause_category": "undetermined",
                        "failure_mode": "",
                    },
                    consequence={
                        "harm_domain": "systemic_integrity",
                        "temporality": "potential",
                        "severity": "low",
                    },
                    views=[],
                    metadata={"raw_source": cand.raw.source},
                )
            )
        return incidents


class StubRender:
    """Writes one Markdown file per incident with YAML frontmatter."""

    def render(self, incidents: List[Incident]) -> dict[str, str]:
        INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
        outputs: dict[str, str] = {}
        for inc in incidents:
            filename = f"{inc.incident_id}.md"
            path = INCIDENTS_DIR / filename
            content = self._render_one(inc)
            path.write_text(content, encoding="utf-8")
            outputs[str(path.relative_to(REPO_ROOT))] = content
        return outputs

    @staticmethod
    def _render_one(inc: Incident) -> str:
        fm = (
            "---\n"
            f"incident_id: {inc.incident_id}\n"
            f"date: {inc.date:%Y-%m-%d}\n"
            f"title: \"{inc.title}\"\n"
            f"event:\n"
            f"  verification_status: {inc.event['verification_status']}\n"
            f"  lifecycle_phase: {inc.event['lifecycle_phase']}\n"
            f"  system_classification: {inc.event['system_classification']}\n"
            f"mechanism:\n"
            f"  root_cause_category: {inc.mechanism['root_cause_category']}\n"
            f"consequence:\n"
            f"  harm_domain: {inc.consequence['harm_domain']}\n"
            f"  temporality: {inc.consequence['temporality']}\n"
            f"  severity: {inc.consequence['severity']}\n"
            f"source_urls: {inc.source_urls}\n"
            f"views: {inc.views}\n"
            f"matched_entities: {inc.metadata.get('matched_entities', [])}\n"
            "---\n\n"
        )
        return fm + f"# {inc.title}\n\n{inc.summary}\n"


# ---------------------------------------------------------------------------
# Synthetic data for --dry-run (so CI can exercise the full pipeline)
# ---------------------------------------------------------------------------


def _synthetic_items() -> List[RawItem]:
    now = datetime.now(timezone.utc)
    return [
        RawItem(
            source="synthetic",
            source_id="dry-run-001",
            url="https://example.com/openai-incident",
            title="Synthetic dry-run incident: OpenAI",
            snippet="Sample candidate generated by run_pipeline.py --dry-run.",
            published_at=now,
            language="en",
            metadata={
                "names": "OpenAI ChatGPT",
                "themes": "TECH_AUTOMATION",
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AI Incident pipeline.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip source adapter, use synthetic data.")
    parser.add_argument("--since", type=str, default=None,
                        help="ISO-8601 datetime; default = 2 days ago.")
    args = parser.parse_args(argv)

    since = (
        datetime.fromisoformat(args.since)
        if args.since
        else datetime.now(timezone.utc) - timedelta(days=2)
    )

    if args.dry_run:
        raw: List[RawItem] = _synthetic_items()
        print(f"[dry-run] using {len(raw)} synthetic items")
    else:
        from scripts.source_gdelt_bigquery import GdeltBigQuerySource
        source: SourceAdapter = GdeltBigQuerySource()
        raw = source.fetch(since)
        print(f"[source] fetched {len(raw)} candidates since {since:%Y-%m-%d}")

    filter_engine: FilterEngine = WatchlistFilterEngine()
    enrich_pipe: EnrichPipe = RuleBasedEnricher()
    renderer: RenderAdapter = StubRender()

    candidates = filter_engine.filter(raw)
    print(f"[filter] {len(candidates)} candidates passed")

    incidents = enrich_pipe.enrich(candidates)
    print(f"[enrich] {len(incidents)} incidents classified")

    outputs = renderer.render(incidents)
    print(f"[render] wrote {len(outputs)} files to {INCIDENTS_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
