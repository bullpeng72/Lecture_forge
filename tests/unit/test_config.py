"""
Tests for configuration module.
"""

import os
import pytest

from lecture_forge.config import Config


def test_config_has_required_attributes():
    """Test that Config has all required attributes."""
    assert hasattr(Config, "OPENAI_API_KEY")
    assert hasattr(Config, "SERPER_API_KEY")
    assert hasattr(Config, "DEFAULT_MODEL")
    assert hasattr(Config, "EMBEDDING_MODEL")
    assert hasattr(Config, "VECTOR_DB_PATH")


def test_config_default_values():
    """Test default configuration values."""
    assert Config.DEFAULT_MODEL == "gpt-4o-mini"
    assert Config.EMBEDDING_MODEL == "text-embedding-3-small"
    assert Config.TEMPERATURE == 0.7
    assert Config.CHUNK_SIZE == 1000
    assert Config.CHUNK_OVERLAP == 200


def test_config_quality_settings():
    """Test quality assurance settings."""
    assert Config.QUALITY_THRESHOLD == 80
    assert Config.MAX_ITERATIONS == 3
    assert 0 <= Config.QUALITY_THRESHOLD <= 100
    assert Config.MAX_ITERATIONS > 0


def test_config_validate_with_valid_keys(test_env_vars):
    """Test validation passes with valid API keys."""
    # Should not raise any exception
    Config.validate()


def test_config_validate_missing_openai_key(monkeypatch):
    """Test validation fails when OPENAI_API_KEY is missing."""
    monkeypatch.setattr(Config, "OPENAI_API_KEY", None)

    with pytest.raises(ValueError) as exc_info:
        Config.validate()

    assert "OPENAI_API_KEY is required" in str(exc_info.value)


def test_config_validate_invalid_openai_key_format(monkeypatch):
    """Test validation fails with invalid OPENAI_API_KEY format."""
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "invalid-key")

    with pytest.raises(ValueError) as exc_info:
        Config.validate()

    assert "invalid format" in str(exc_info.value).lower()


def test_config_validate_short_serper_key(monkeypatch):
    """Test validation fails with too short SERPER_API_KEY."""
    monkeypatch.setattr(Config, "SERPER_API_KEY", "short")

    with pytest.raises(ValueError) as exc_info:
        Config.validate()

    assert "too short" in str(exc_info.value).lower()


def test_config_image_settings():
    """Test image-related configuration."""
    assert Config.MAX_IMAGES_PER_SEARCH == 10
    assert Config.IMAGE_FORMAT == "webp"
    assert Config.IMAGE_MAX_WIDTH == 1200


def test_config_paths_exist(test_env_vars):
    """Test that required directories are created."""
    Config.ensure_directories()

    assert Config.DATA_DIR.exists()
    assert Config.OUTPUT_DIR.exists()
    assert Config.VECTOR_DB_PATH.exists()
    assert (Config.DATA_DIR / "images").exists()
    assert (Config.DATA_DIR / "cache").exists()
