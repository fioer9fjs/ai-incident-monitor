"""Unit tests for the article scraper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests.exceptions

from scripts.scraper import Article, fetch_article


class TestFetchArticle:
    """Mocked HTTP tests — no real network calls."""

    @patch("scripts.scraper.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = (
            b"<html><head><title>Test Title</title></head>"
            b"<body>"
            b"<h1>Header</h1>"
            b"<p>First meaningful paragraph with enough characters.</p>"
            b"<p>Second paragraph with more text here.</p>"
            b"</body></html>"
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        article = fetch_article("https://example.com/article")
        assert article is not None
        assert article.title == "Test Title"
        assert "First meaningful paragraph" in article.first_paragraph
        assert "Second paragraph" in article.full_text

    @patch("scripts.scraper.requests.get")
    def test_404_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404", response=mock_resp
        )
        mock_get.return_value = mock_resp

        assert fetch_article("https://example.com/404") is None

    @patch("scripts.scraper.requests.get")
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        assert fetch_article("https://example.com/slow") is None

    @patch("scripts.scraper.requests.get")
    def test_empty_url_returns_none(self, mock_get):
        assert fetch_article("") is None
        assert fetch_article("not-a-url") is None
        mock_get.assert_not_called()

    @patch("scripts.scraper.requests.get")
    def test_server_error_retries_then_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "503", response=mock_resp
        )
        mock_get.return_value = mock_resp

        assert fetch_article("https://example.com/error") is None
        assert mock_get.call_count == 3  # MAX_RETRIES

    @patch("scripts.scraper.requests.get")
    def test_no_paragraphs(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"<html><body><div>no paragraphs here</div></body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        article = fetch_article("https://example.com/nop")
        assert article is not None
        assert article.first_paragraph == ""
        assert article.full_text == ""
