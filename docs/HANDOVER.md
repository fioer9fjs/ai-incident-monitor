# Project Handover — AI Incident Monitor

State as of 2026-08-09. This document replaces the original chat history.

## 1. Purpose

Automated, open, taxonomy-driven monitoring of real-world AI incidents.
Daily pipeline: fetch news candidates from GDELT/BigQuery, filter them,
classify them into a 3-layer taxonomy, publish as Markdown knowledge base
(static site planned).

## 2. Core Definition (intellectual core — do not dilute)

> AI Incident is an alleged or confirmed event, circumstance, or series of
> events in which the development, deployment, use, malfunction, or misuse
> of one or more AI systems directly or indirectly leads to actual harm,
> potential harm, or a significant deviation from intended safe operation
> affecting people, property, the environment, fundamental rights, or
> systemic integrity.

Synthesis sources: AIID (alleged/confirmed), OECD (lifecycle scope),
EU AI Act + NIST (actual/potential harm hybrid), MIT/ISO (systemic integrity).

## 3. Taxonomy (config/taxonomy.yaml, v3)

Integrative 3-layer model, NOT a flat category list:
- event: verification_status, lifecycle_phase, system_classification
- mechanism: root_cause_category (MIT causal taxonomy), failure_mode
- consequence: harm_domain, temporality (actual/potential/latent), severity

Regulatory frameworks (EU AI Act, NIST RMF, ISO 42001, DoD) are NOT
categories. They are "views": derived queries over the three layers,
computed at runtime (see views section in taxonomy.yaml and
scripts/enrich_rules.py compute_views()).

## 4. Architecture & Interfaces

scripts/interfaces.py defines RawItem, Candidate, Incident dataclasses and
four protocols: SourceAdapter.fetch(), FilterEngine.filter(),
EnrichPipe.enrich(), RenderAdapter.render(). Implementations:
- Source: scripts/source_gdelt_bigquery.py (GdeltBigQuerySource)
- Filter: scripts/filter_engine.py (WatchlistFilterEngine)
- Enrich: scripts/enrich_rules.py (RuleBasedEnricher, v1 heuristics)
- Render: scripts/run_pipeline.py (MarkdownRenderer)
- Orchestrator: scripts/run_pipeline.py

## 5. Data Strategy (hard-won lessons)

- GDELT REST APIs are rate-limited and shallow -> use BigQuery.
- GKG Themes contain NO AI-specific themes (verified against full theme
  lookup). GKG Entities are dynamic (no static list). Therefore:
  URL-based keyword detection (AI term AND incident term) is the primary
  filter; the curated entity watchlist (config/ai_entity_watchlist.yaml)
  is a secondary signal and future source-adapter seed.
- Aviation exclusion list avoids "copilot" false positives.
- Tone < -3.0 pre-selects negative coverage.
- Cost breakthrough: use table `gdelt-bq.gdeltv2.gkg_partitioned` with
  `_PARTITIONTIME` (2.7 TB -> 0.2 GB per daily run).

## 6. Infrastructure

- Public GitHub repo; static publishing planned (Cloudflare Pages).
- One GCP project used for BigQuery only. CI authenticates via
  Workload Identity Federation (OIDC), restricted to this repository.
  No service account JSON keys exist anywhere.
- Concrete identifiers (project id/number, service account email,
  WIF pool/provider, enabled APIs) live ONLY in the gitignored file
  docs/INFRA.local.md. Never commit that file.
- Workflows: ci.yml runs all scripts/check_*.py plus a dry-run on every
  push/PR; ingest.yml runs the live pipeline daily at 06:00 UTC and on
  dispatch, then auto-commits incidents/ with [skip ci].

## 7. Current Status

- End-to-end pipeline works with synthetic data (idempotent dry-run).
- Live fetch verified: ~7 candidates/day at ~0.2 GB scanned.
- Filter rewrite (URL signal) committed; a live run after that rewrite
  had NOT yet been verified at handover time. First task: run ingest once
  and confirm [filter] > 0 and rendered files.
- Enricher v1 fills defaults (often systemic_integrity/undetermined)
  because GKG provides little context. Titles are missing (GKG has none).

## 8. Conventions

- English only in repo (see .clinerules).
- Modular replaceability over convenience.
- CI checks guard every module; never delete a check without replacement.
- Complete-file edits when guiding the owner.

## 9. Local Run

    gcloud auth application-default login
    GCP_PROJECT=<see docs/INFRA.local.md> python -m scripts.run_pipeline
    python -m scripts.run_pipeline --dry-run   # no GCP needed