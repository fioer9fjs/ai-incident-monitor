# AI Incident Monitor

Automated global tracking, taxonomy-driven analysis, and open knowledge
base for AI incidents.

## Architecture

Source Adapter -> Filter Engine -> Enrich Pipe -> Render Adapter
(GDELT/BigQuery)   (keywords +    (rule-based    (Markdown +
                    watchlist)     v1; LLM v2     YAML frontmatter)
                                   planned)

All modules communicate via stable protocols (scripts/interfaces.py).
Each stage is replaceable independently.

## Key Files

- `config/taxonomy.yaml` - 3-layer incident model (Event -> Mechanism -> Consequence)
- `config/ai_entity_watchlist.yaml` - curated AI entity filter
- `scripts/keywords.py` - shared AI/incident keyword lists
- `scripts/run_pipeline.py` - orchestrator
- `.github/workflows/` - CI + daily ingest (OIDC, no secrets)
- `incidents/` - generated Markdown files with YAML frontmatter
- `docs/` - handover, backlog, setup documentation

## Local Run

    pip install -r requirements.txt
    python -m scripts.run_pipeline --dry-run

## License

MIT