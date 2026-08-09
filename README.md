# AI Incident Monitor

Automated global tracking, taxonomy-driven analysis, and open knowledge base for AI incidents.

## Architecture

Source Adapter → Filter Engine → Enrich Pipe → Render Adapter
(GDELT/BQ) (Watchlist+ (LLM+ (Astro/Quartz → Themes+CAMEO) Taxonomy) Cloudflare Pages)


All modules communicate via stable Python interfaces. Each can be replaced independently.

## Key Files

- `config/taxonomy.yaml` – 3-layer incident model (Event → Mechanism → Consequence)
- `config/ai_entity_watchlist.yaml` – Curated AI entity filter for GDELT
- `scripts/` – Platform-agnostic ETL pipeline
- `.github/workflows/` – GitHub Actions orchestrator
- `incidents/` – Markdown files with YAML frontmatter (generated)

## Status

🚧 Early setup phase. Core taxonomy and entity watchlist defined. ETL pipeline in development.

## License

MIT
