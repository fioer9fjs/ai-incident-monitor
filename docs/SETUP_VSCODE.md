# Local Setup: VS Code + Cline + OpenRouter

## 1. Install
- VS Code: https://code.visualstudio.com
- Extension: "Cline" (marketplace)
- Git if not installed.

## 2. Clone & Python environment
    git clone https://github.com/fioer9fjs/ai-incident-monitor.git
    cd ai-incident-monitor
    python -m venv .venv
    # Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt

    git config user.name "<your name>"
    git config user.email "<your noreply or personal mail>"

## 3. Cline + OpenRouter
- Create API key at https://openrouter.ai/keys
- Cline sidebar -> API Provider: OpenRouter -> paste key.
- Recommended model: a strong agentic model, e.g.
  anthropic/claude-sonnet-4.5 (check OpenRouter model list for current best).
- Keep terminal-command approval ON while the pipeline touches GCP quotas.

## 4. First Cline session (onboarding prompt)

    Read .clinerules, docs/HANDOVER.md, docs/BACKLOG.md and
    docs/SETUP_VSCODE.md. Then:
    1) Summarize the current project state in 5 bullet points.
    2) Confirm the P0 task from the backlog and show the exact command
       or workflow trigger to verify it.
    3) Propose a concrete implementation plan for the P1 LLM Enricher v2
       WITHOUT changing any files yet.

## 5. Optional: local GCP access
    gcloud auth application-default login
    GCP_PROJECT=<see docs/INFRA.local.md> python -m scripts.run_pipeline
(Your Google account is project Owner, so local queries work; each run
scans <2 GB of the 1 TB free tier.)