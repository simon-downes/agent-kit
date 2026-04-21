"""Tests for agent_kit.google.mail."""

from base64 import urlsafe_b64encode
from unittest.mock import patch

import respx
from httpx import Response

from agent_kit.google.mail import (
    _extract_body,
    _format_message_summary,
    _list_attachments,
    html_to_markdown,
    search_messages,
)

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class TestFormatMessageSummary:
    def test_extracts_headers(self):
        msg = {
            "id": "m1",
            "snippet": "Hello",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@co.com"},
                    {"name": "To", "value": "bob@co.com"},
                    {"name": "Subject", "value": "Test"},
                    {"name": "Date", "value": "2026-01-01"},
                ],
            },
        }
        result = _format_message_summary(msg)
        assert result["id"] == "m1"
        assert result["from"] == "alice@co.com"
        assert result["subject"] == "Test"
        assert result["snippet"] == "Hello"

    def test_missing_headers(self):
        msg = {"id": "m2", "payload": {"headers": []}}
        result = _format_message_summary(msg)
        assert result["from"] == ""
        assert result["subject"] == ""


class TestExtractBody:
    def test_prefers_plain_text(self):
        plain = urlsafe_b64encode(b"Hello plain").decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": plain}},
                {"mimeType": "text/html", "body": {"data": urlsafe_b64encode(b"<b>Hi</b>").decode()}},
            ],
        }
        assert _extract_body(payload) == "Hello plain"

    def test_falls_back_to_html(self):
        html = urlsafe_b64encode(b"<p>Hello</p>").decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": html}},
            ],
        }
        result = _extract_body(payload)
        assert "Hello" in result

    def test_empty_payload(self):
        assert _extract_body({}) == ""


class TestListAttachments:
    def test_finds_attachments(self):
        payload = {
            "parts": [
                {
                    "filename": "doc.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att1"},
                },
                {"filename": "", "body": {}},
            ],
        }
        result = _list_attachments(payload)
        assert len(result) == 1
        assert result[0]["filename"] == "doc.pdf"

    def test_no_attachments(self):
        assert _list_attachments({"parts": []}) == []
        assert _list_attachments({}) == []


class TestHtmlToMarkdown:
    def test_pandoc_conversion(self):
        with patch("agent_kit.google.mail.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "# Hello\n\nWorld"
            result = html_to_markdown("<h1>Hello</h1><p>World</p>")
            assert "Hello" in result
            assert "World" in result

    def test_fallback_when_pandoc_missing(self):
        with patch(
            "agent_kit.google.mail.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = html_to_markdown("<p>Hello &amp; world</p>")
            assert "Hello" in result
            assert "&" in result

    def test_strips_images(self):
        with patch(
            "agent_kit.google.mail.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = html_to_markdown('<p>Text</p><img src="logo.png">')
            assert "img" not in result
            assert "Text" in result


class TestSearchMessages:
    @respx.mock
    def test_search(self, google_client):
        plain = urlsafe_b64encode(b"body text").decode()
        respx.get(f"{GMAIL_API}/messages").mock(
            return_value=Response(200, json={"messages": [{"id": "m1"}]})
        )
        respx.get(f"{GMAIL_API}/messages/m1").mock(
            return_value=Response(200, json={
                "id": "m1",
                "snippet": "body text",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test"},
                        {"name": "From", "value": "a@co.com"},
                        {"name": "To", "value": "b@co.com"},
                        {"name": "Date", "value": "2026-01-01"},
                    ],
                    "body": {"data": plain},
                },
            })
        )
        result = search_messages(google_client, "test", limit=5)
        assert len(result) == 1
        assert result[0]["subject"] == "Test"
