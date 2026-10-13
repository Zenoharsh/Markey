from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings, read from environment variables or a local .env file.
    See .env.example for every option.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Which LLM writes the reports: a local Ollama model or the hosted Claude API
    llm_provider: Literal["ollama", "anthropic"] = "ollama"

    # Ollama (local) - also used for embeddings regardless of llm_provider
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    # Anthropic (hosted)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Storage and API
    chroma_path: str = "./chroma_db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    llm_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
