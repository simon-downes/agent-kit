"""Tests for agent_kit.google.drive."""

from unittest.mock import patch

import pytest
import respx
from httpx import Response

from agent_kit.google.drive import (
    GOOGLE_DOC_TYPES,
    _format_file,
    fetch_file,
    fetch_to_stdout,
    search_files,
)

DRIVE_API = "https://www.googleapis.com/drive/v3"

SAMPLE_FILE = {
    "id": "f1",
    "name": "My Doc",
    "mimeType": "application/pdf",
    "modifiedTime": "2026-01-01T00:00:00Z",
    "owners": [{"emailAddress": "a@co.com"}],
}


class TestFormatFile:
    def test_formats_file(self):
        result = _format_file(SAMPLE_FILE)
        assert result["id"] == "f1"
        assert result["name"] == "My Doc"
        assert result["owners"] == ["a@co.com"]

    def test_missing_owners(self):
        result = _format_file({"id": "f2", "name": "X"})
        assert result["owners"] == []


class TestSearchFiles:
    @respx.mock
    def test_search(self):
        respx.get(f"{DRIVE_API}/files").mock(
            return_value=Response(200, json={"files": [SAMPLE_FILE]})
        )
        result = search_files("My Doc", limit=5)
        assert len(result) == 1
        assert result[0]["name"] == "My Doc"


class TestFetchFile:
    @respx.mock
    def test_downloads_binary(self, tmp_path):
        # _get adds supportsAllDrives/includeItemsFromAllDrives params
        # _download hits the raw URL with ?alt=media
        respx.get(f"{DRIVE_API}/files/f1").mock(
            side_effect=[
                Response(200, json={
                    "id": "f1",
                    "name": "report.pdf",
                    "mimeType": "application/pdf",
                }),
                Response(200, content=b"%PDF-content"),
            ]
        )
        path = fetch_file("f1", tmp_path)
        assert path.name == "report.pdf"
        assert path.read_bytes() == b"%PDF-content"

    @respx.mock
    def test_exports_google_doc_as_markdown(self, tmp_path):
        with patch("agent_kit.google.drive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = b"# Title\n\nContent"
            respx.get(f"{DRIVE_API}/files/f2").mock(
                return_value=Response(200, json={
                    "id": "f2",
                    "name": "My Document",
                    "mimeType": "application/vnd.google-apps.document",
                })
            )
            respx.get(f"{DRIVE_API}/files/f2/export").mock(
                return_value=Response(200, content=b"<h1>Title</h1><p>Content</p>")
            )
            path = fetch_file("f2", tmp_path)
            assert path.suffix == ".md"

    @respx.mock
    def test_exports_spreadsheet_as_csv(self, tmp_path):
        respx.get(f"{DRIVE_API}/files/f3").mock(
            return_value=Response(200, json={
                "id": "f3",
                "name": "Data Sheet",
                "mimeType": "application/vnd.google-apps.spreadsheet",
            })
        )
        respx.get(f"{DRIVE_API}/files/f3/export").mock(
            return_value=Response(200, content=b"a,b,c\n1,2,3")
        )
        path = fetch_file("f3", tmp_path)
        assert path.suffix == ".csv"
        assert b"a,b,c" in path.read_bytes()


class TestFetchToStdout:
    @respx.mock
    def test_exports_google_doc(self):
        with patch("agent_kit.google.mail.subprocess.run", side_effect=FileNotFoundError):
            respx.get(f"{DRIVE_API}/files/f1").mock(
                return_value=Response(200, json={
                    "id": "f1",
                    "name": "Doc",
                    "mimeType": "application/vnd.google-apps.document",
                })
            )
            respx.get(f"{DRIVE_API}/files/f1/export").mock(
                return_value=Response(200, content=b"<p>Hello</p>")
            )
            result = fetch_to_stdout("f1")
            assert "Hello" in result

    @respx.mock
    def test_raises_for_binary(self):
        respx.get(f"{DRIVE_API}/files/f1").mock(
            return_value=Response(200, json={
                "id": "f1",
                "name": "file.zip",
                "mimeType": "application/zip",
            })
        )
        with pytest.raises(ValueError, match="binary files cannot be output"):
            fetch_to_stdout("f1")


class TestGoogleDocTypes:
    def test_doc_exports_html(self):
        t = GOOGLE_DOC_TYPES["application/vnd.google-apps.document"]
        assert t["export"] == "text/html"
        assert t["ext"] == ".md"

    def test_spreadsheet_exports_csv(self):
        t = GOOGLE_DOC_TYPES["application/vnd.google-apps.spreadsheet"]
        assert t["export"] == "text/csv"
        assert t["ext"] == ".csv"
