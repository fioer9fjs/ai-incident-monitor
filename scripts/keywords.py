"""Keyword lists for AI incident detection in GDELT GKG queries.

Centralised here so they can be reused by the BigQuery source adapter,
alternative source adapters, or CI checks without duplicating constants.
"""

from __future__ import annotations

import re


# AI-related keywords (case-insensitive, word-boundary anchored).
AI_KEYWORDS = [
    "ai", "artificial-intelligence", "genai", "generative-ai",
    "machine-learning", "chatgpt", "openai", "gpt", "llm",
    "deepmind", "anthropic", "claude", "copilot", "gemini",
    "mistral", "huggingface", "hugging-face", "xai",
    "midjourney", "stable-diffusion", "sora", "perplexity", "grok",
]

# Incident-related keywords — must co-occur with an AI keyword.
INCIDENT_KEYWORDS = [
    "incident", "failure", "outage", "glitch", "breach", "hack",
    "flaw", "vulnerability", "hallucination", "deepfake", "bias",
    "jailbreak", "lawsuit", "fraud", "fine", "ban", "probe",
    "investigation", "violation", "copyright", "penalty", "leak",
    "exploit", "scam", "malware", "error", "crash", "bug",
    "malfunction", "misinformation", "disinformation",
    "plagiarism", "propaganda",
]

# Aviation terms to exclude (avoid "Copilot" false positives in airline news).
EXCLUDE_TERMS = ["flight", "plane", "aircraft", "aviation",
                 "airline", "airlines", "pilot", "jet"]

# GDELT V2Tone threshold — only negative-toned articles.
TONE_THRESHOLD = -3.0


def alternation(words: list[str]) -> str:
    """Build a BigQuery REGEXP-compatible word-boundary alternation."""
    return r"\b(" + "|".join(words) + r")\b"


def compile_patterns() -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    """Compile AI, incident, and exclusion regex patterns for Python matching."""
    ai_re = re.compile(alternation(AI_KEYWORDS))
    inc_re = re.compile(alternation(INCIDENT_KEYWORDS))
    excl_re = re.compile(alternation(EXCLUDE_TERMS))
    return ai_re, inc_re, excl_re



