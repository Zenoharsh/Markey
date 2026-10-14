import httpx
import pytest

from services import search
from services.search import BraveSearch, FallbackSearch, SearchError, SearchResult, TavilySearch, get_search_provider


def mock_http(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        search.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


def test_no_keys_means_no_search_provider():
    assert get_search_provider() is None


def test_providers_are_ordered_tavily_then_brave(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    assert [p.name for p in get_search_provider().providers] == ["tavily", "brave"]


async def test_tavily_parses_results_and_raw_content(monkeypatch):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer key"
        return httpx.Response(200, json={"results": [
            {"url": "https://a.example", "title": "A", "content": "snippet", "raw_content": "full text"},
            {"title": "no url"},
        ]})

    mock_http(monkeypatch, handler)
    results = await TavilySearch("key", 5).search("scooters", 5)
    assert results == [SearchResult("https://a.example", "A", "snippet", "full text")]


async def test_brave_parses_web_results(monkeypatch):
    def handler(request):
        assert request.headers["X-Subscription-Token"] == "key"
        assert request.url.params["q"] == "scooters"
        return httpx.Response(200, json={"web": {"results": [
            {"url": "https://b.example", "title": "B", "description": "desc"},
        ]}})

    mock_http(monkeypatch, handler)
    results = await BraveSearch("key", 5).search("scooters", 5)
    assert results == [SearchResult("https://b.example", "B", "desc")]


class FailingProvider:
    name = "failing"

    async def search(self, query, max_results):
        raise httpx.ConnectError("down")


class StaticProvider:
    name = "static"

    async def search(self, query, max_results):
        return [SearchResult("https://ok.example", "OK", "")]


async def test_fallback_uses_next_provider_when_first_fails():
    results = await FallbackSearch([FailingProvider(), StaticProvider()]).search("q", 5)
    assert results[0].url == "https://ok.example"


async def test_fallback_raises_when_all_fail():
    with pytest.raises(SearchError, match="failing"):
        await FallbackSearch([FailingProvider()]).search("q", 5)
