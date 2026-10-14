import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    # Full page text when the provider returns it, so the page needn't be scraped
    content: str | None = None


class SearchError(Exception):
    """No search provider could answer the query."""


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str, timeout: float):
        self.api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": query, "max_results": max_results, "include_raw_content": True},
            )
            response.raise_for_status()
        return [
            SearchResult(
                url=r["url"],
                title=r.get("title") or r["url"],
                snippet=r.get("content") or "",
                content=r.get("raw_content"),
            )
            for r in response.json().get("results", [])
            if r.get("url")
        ]


class BraveSearch:
    name = "brave"

    def __init__(self, api_key: str, timeout: float):
        self.api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
                params={"q": query, "count": max_results},
            )
            response.raise_for_status()
        return [
            SearchResult(url=r["url"], title=r.get("title") or r["url"], snippet=r.get("description") or "")
            for r in response.json().get("web", {}).get("results", [])
            if r.get("url")
        ]


class FallbackSearch:
    """Tries each provider in order and returns the first successful answer."""

    name = "fallback"

    def __init__(self, providers: list[SearchProvider]):
        self.providers = providers

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        errors = []
        for provider in self.providers:
            try:
                return await provider.search(query, max_results)
            except (httpx.HTTPError, KeyError, ValueError) as e:
                logger.warning(f"{provider.name} search failed for {query!r}: {e}")
                errors.append(f"{provider.name}: {e}")
        raise SearchError("All search providers failed: " + "; ".join(errors))


@lru_cache
def get_search_provider() -> FallbackSearch | None:
    """Returns the configured search chain, or None when no search API key is set."""
    settings = get_settings()
    providers: list[SearchProvider] = []
    if settings.tavily_api_key:
        providers.append(TavilySearch(settings.tavily_api_key, settings.search_timeout_seconds))
    if settings.brave_api_key:
        providers.append(BraveSearch(settings.brave_api_key, settings.search_timeout_seconds))
    return FallbackSearch(providers) if providers else None
