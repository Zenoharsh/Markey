from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings, read from environment variables or a local .env file.
    See .env.example for every option.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Which LLM writes the reports: a local Ollama model, or the hosted Claude or Gemini API
    llm_provider: Literal["ollama", "anthropic", "gemini"] = "ollama"

    # Ollama (local) - also used for embeddings regardless of llm_provider
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_num_ctx: int = 16384

    # Anthropic (hosted)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Google Gemini (hosted, has a free tier) - key from https://aistudio.google.com/apikey
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # Source discovery - set at least one key to research any topic from the live web.
    # Tavily is tried first, Brave is the fallback. With neither, reports use only pages stored via /scrape.
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    research_max_sources: int = 8
    research_min_sources: int = 2
    search_timeout_seconds: float = 20.0
    # Long pages are cut to this many characters before chunking, which keeps local embedding fast
    max_page_chars: int = 20000
    page_fetch_timeout_seconds: float = 45.0

    # Storage and API
    # Saved reports and research history
    database_path: str = "./markey.db"
    chroma_path: str = "./chroma_db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    llm_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
