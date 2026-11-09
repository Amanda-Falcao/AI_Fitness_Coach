"""Environment-based settings with explicit validation and no import side effects."""

from dataclasses import dataclass
import os


class ConfigurationError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None = None
    tavily_api_key: str | None = None
    chroma_persist_directory: str = "dados/chroma_db"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    groq_model_name: str = "openai/gpt-oss-20b"

    @classmethod
    def from_env(cls, *, require_groq: bool = False, require_tavily: bool = False) -> "Settings":
        """Read settings from the process environment, requiring only active integrations."""
        groq_key = os.getenv("GROQ_API_KEY", "").strip() or None
        tavily_key = os.getenv("TAVILY_API_KEY", "").strip() or None
        missing = []
        if require_groq and not groq_key:
            missing.append("GROQ_API_KEY")
        if require_tavily and not tavily_key:
            missing.append("TAVILY_API_KEY")
        if missing:
            raise ConfigurationError("Missing required environment variable(s): " + ", ".join(missing))

        chroma_path = os.getenv("CHROMA_PERSIST_DIRECTORY", "dados/chroma_db").strip()
        embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2").strip()
        groq_model = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-20b").strip()
        empty_settings = [
            name
            for name, value in (
                ("CHROMA_PERSIST_DIRECTORY", chroma_path),
                ("EMBEDDING_MODEL_NAME", embedding_model),
                ("GROQ_MODEL_NAME", groq_model),
            )
            if not value
        ]
        if empty_settings:
            raise ConfigurationError("Configuration value(s) must not be empty: " + ", ".join(empty_settings))

        return cls(
            groq_api_key=groq_key,
            tavily_api_key=tavily_key,
            chroma_persist_directory=chroma_path,
            embedding_model_name=embedding_model,
            groq_model_name=groq_model,
        )
