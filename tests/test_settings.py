import pytest

from app.config.settings import ConfigurationError, Settings


def test_settings_use_safe_defaults_without_loading_secrets(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("CHROMA_PERSIST_DIRECTORY", raising=False)

    settings = Settings.from_env()

    assert settings.groq_api_key is None
    assert settings.tavily_api_key is None
    assert settings.chroma_persist_directory == "dados/chroma_db"


def test_settings_require_only_requested_integrations(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")

    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        Settings.from_env(require_groq=True)

    assert Settings.from_env(require_tavily=True).tavily_api_key == "tavily-test-key"
