"""Tests for mem models and validation."""

import pytest

from agent_kit.mem.models import (
    MEMORY_KINDS,
    validate_kebab_case,
    validate_kind,
    validate_metadata,
)


def test_memory_kinds_defined():
    """Test that memory kinds are defined."""
    assert len(MEMORY_KINDS) == 9
    assert "decision" in MEMORY_KINDS
    assert "change" in MEMORY_KINDS
    assert "issue" in MEMORY_KINDS
    assert "context" in MEMORY_KINDS
    assert "task" in MEMORY_KINDS
    assert "note" in MEMORY_KINDS
    assert "pattern" in MEMORY_KINDS
    assert "dependency" in MEMORY_KINDS
    assert "experiment" in MEMORY_KINDS


def test_validate_kebab_case_valid():
    """Test valid kebab-case strings."""
    validate_kebab_case("valid-project")
    validate_kebab_case("my-api-design")
    validate_kebab_case("a")
    validate_kebab_case("test123")
    validate_kebab_case("test-123-abc")


def test_validate_kebab_case_invalid():
    """Test invalid kebab-case strings."""
    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("UPPERCASE")

    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("has_underscore")

    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("has space")

    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("-starts-with-dash")

    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("ends-with-dash-")

    with pytest.raises(ValueError, match="lower-kebab-case"):
        validate_kebab_case("double--dash")


def test_validate_kind_valid():
    """Test valid memory kinds."""
    for kind in MEMORY_KINDS:
        validate_kind(kind)


def test_validate_kind_invalid():
    """Test invalid memory kinds."""
    with pytest.raises(ValueError, match="Invalid kind"):
        validate_kind("invalid-kind")

    with pytest.raises(ValueError, match="Must be one of"):
        validate_kind("random")


def test_validate_metadata_empty():
    """Test that empty metadata is valid."""
    validate_metadata("")
    validate_metadata("   ")


def test_validate_metadata_valid_json():
    """Test valid JSON metadata."""
    validate_metadata('{"key": "value"}')
    validate_metadata('{"nested": {"key": "value"}}')
    validate_metadata('[]')
    validate_metadata('[1, 2, 3]')


def test_validate_metadata_invalid_json():
    """Test invalid JSON metadata."""
    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_metadata("{invalid json}")

    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_metadata("not json at all")

    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_metadata('{"unclosed": ')
