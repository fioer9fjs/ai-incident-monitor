"""Lightweight article scraper: title + first paragraph extraction.

Uses requests + BeautifulSoup.  No headless browser — keeps costs at zero.
Respects timeouts, retries on transient errors, and sanitises all output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 5  # seconds
MAX_RETRIES = 3

# Common User-Agents to rotate (minimal set, polite)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


@dataclass
class Article:
    """Extracted article metadata."""

    url: str
    title: str
    first_paragraph: str
    full_text: str


def _clean_text(text: str) -> str:
    """Collapse whitespace and strip control characters."""
    text = re.sub(r"[\s\u200b\ufeff]+", " ", text)
    return text.strip()


def _extract_first_paragraph(soup: BeautifulSoup) -> str:
    """Find the first meaningful paragraph (<p> with > 40 chars)."""
    for p in soup.find_all("p"):
        txt = _clean_text(p.get_text())
        if len(txt) > 40:
            return txt
    return ""


def _extract_full_text(soup: BeautifulSoup) -> str:
    """Concatenate all meaningful paragraphs."""
    paragraphs = []
    for p in soup.find_all("p"):
        txt = _clean_text(p.get_text())
        if len(txt) > 20:
            paragraphs.append(txt)
    return "\n\n".join(paragraphs)


def fetch_article(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[Article]:
    """Fetch and parse a single article.

    Returns None on network failure, non-2xx status, or parse error.
    Retries up to MAX_RETRIES on transient errors (5xx, timeouts).
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    headers = {"User-Agent": _USER_AGENTS[0]}

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code >= 500:
                last_exc = exc
                continue
            return None
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                continue
            return None
    else:
        return None

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception:
        return None

    # Title: <title> tag first, then <h1>
    title = ""
    if soup.title and soup.title.string:
        title = _clean_text(soup.title.string)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = _clean_text(h1.get_text())

    first_paragraph = _extract_first_paragraph(soup)
    full_text = _extract_full_text(soup)

    # Safety cap: never store > 50 KB of text per article
    full_text = full_text[:50_000]
    first_paragraph = first_paragraph[:2_000]

    return Article(
        url=url,
        title=title,
        first_paragraph=first_paragraph,
        full_text=full_text,
    )
