import sys
from pathlib import Path

import pytest

# Make the backend modules importable when pytest runs from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402
from services.llm import get_llm_provider  # noqa: E402
from services.search import get_search_provider  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """Each test gets default settings, a throwaway Chroma path and fresh cached singletons."""
    for var in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "OLLAMA_BASE_URL", "TAVILY_API_KEY", "BRAVE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    caches = (get_settings, get_llm_provider, get_search_provider)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()
