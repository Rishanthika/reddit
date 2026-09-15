"""
Tests for app/config.py's settings loading and validation — especially
the AI_PROVIDER / OPENAI_API_KEY validation rules this task added/tightened.

Uses monkeypatch.setenv so no real .env file or real credentials are
needed, and points env_file at a nonexistent path so a real .env in the
working directory can never leak into a test.
"""

import pytest

from app.config import ConfigError, load_settings

_MISSING_ENV_FILE = "/nonexistent/.env-for-tests"


def _set_base_env(monkeypatch):
    """The environment variables required regardless of AI_PROVIDER."""
    monkeypatch.setenv("APIFY_API_TOKEN", "fake-apify-token")
    monkeypatch.setenv("APIFY_ACTOR_ID", "automation-lab/reddit-scraper")
    monkeypatch.setenv("SUBREDDITS", "studyabroad,gradadmissions")
    monkeypatch.setenv("POST_LIMIT", "25")
    monkeypatch.setenv("DATABASE_PATH", "data/leads.db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("CLASSIFIER_VALIDATION_MODE", "false")
    monkeypatch.setenv("CLASSIFIER_VALIDATION_LIMIT", "30")


def test_ai_provider_openai_with_key_loads_successfully(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")

    settings = load_settings(env_file=_MISSING_ENV_FILE)

    assert settings.ai_provider == "openai"
    assert settings.openai_api_key == "sk-fake-test-key"
    assert settings.openai_model == "gpt-4o-mini"


def test_ai_provider_openai_without_key_raises_clear_config_error(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=_MISSING_ENV_FILE)

    message = str(excinfo.value)
    assert "OPENAI_API_KEY" in message
    assert "AI_PROVIDER=openai" in message


def test_ai_provider_openai_with_blank_key_raises_config_error(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")  # whitespace-only

    with pytest.raises(ConfigError):
        load_settings(env_file=_MISSING_ENV_FILE)


def test_ai_provider_mock_does_not_require_openai_api_key(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = load_settings(env_file=_MISSING_ENV_FILE)

    assert settings.ai_provider == "mock"
    assert settings.openai_api_key == ""


def test_unsupported_ai_provider_fails_clearly(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openia")  # typo, must not silently work

    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=_MISSING_ENV_FILE)

    assert "openia" in str(excinfo.value)


def test_unsupported_ai_provider_never_silently_falls_back_to_mock(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigError):
        settings = load_settings(env_file=_MISSING_ENV_FILE)
        # If this line were ever reached, it must not have quietly become "mock".
        assert settings.ai_provider != "mock"


def test_missing_openai_model_falls_back_to_project_default(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = load_settings(env_file=_MISSING_ENV_FILE)

    assert settings.openai_model == "gpt-4o-mini"


def test_custom_openai_model_is_respected_not_hardcoded(monkeypatch):
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    settings = load_settings(env_file=_MISSING_ENV_FILE)

    assert settings.openai_model == "gpt-4.1-mini"


def test_config_error_for_missing_key_never_contains_a_real_looking_secret(monkeypatch):
    # Defensive: the error message construction must never accidentally
    # interpolate an actual (even partial) key value.
    _set_base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=_MISSING_ENV_FILE)

    assert "sk-" not in str(excinfo.value)
