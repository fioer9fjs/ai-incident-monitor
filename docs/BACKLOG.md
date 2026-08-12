# Backlog (prioritized)

## P0 — Verify live pipeline
- Run ingest workflow once; confirm filter passes candidates and real
  incident Markdown files are committed.

## P1 — LLM Enricher v2
- Replace RuleBasedEnricher heuristics with an LLM call (OpenRouter or
  Groq free tier) behind the same EnrichPipe protocol.
- Input: article URL content (fetch + fallback to metadata), matched
  entities/themes. Output: full taxonomy fields + summary + title.
- Must stay CI-safe: rule-based enricher remains the default; LLM only
  when API key present.

## P1 — Incident timeline tracking (owner request)
- Incidents are often ongoing stories, not one-off reports.
- Design direction: stable incident_id + `updates:` array in frontmatter
  or separate timeline entries linked via related_incidents.
- The URL-slug aggregation idea (GROUP BY url_slug from the owner's
  original query) belongs here or in the filter stage.

## P2 — Financial damage estimation (owner request)
- Add consequence.financial_estimate (range + currency + confidence +
  source) to taxonomy and enricher prompt.

## P2 — Titles & readability
- GKG has no titles. Fetch Open Graph title from article URL during
  enrich (with timeout/fallback).

## P2 — Website
- Static site (Astro or Quartz) rendering incidents/ + taxonomy views;
  deploy via Cloudflare Pages (free tier). Render adapter stays
  replaceable.

## P3 — Additional sources
- Second SourceAdapter using the entity watchlist (RSS feeds, AIID import)
  to prove adapter replaceability.

## P3 — China regulation view
- taxonomy.yaml has a placeholder view; research CAC/TC260 triggers.

## P3 — GCP budget alert
- Billing -> Budgets & alerts, $1 symbolic budget with 50%/90% mail alerts.