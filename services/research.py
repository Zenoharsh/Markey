import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

from fastapi.concurrency import run_in_threadpool

from config import get_settings
from models.request_models import CitedText, MarketResearchReport, ReportDraft, Source
from services.chunker import chunk_text
from services.generator import generate_research_report
from services.scraper import scrape_core_content
from services.search import SearchError, SearchResult, get_search_provider
from services.vector_db import retrieve_context, store_documents

logger = logging.getLogger(__name__)

# Called with (stage, message) as the research run progresses
ProgressCallback = Callable[[str, str], Awaitable[None]]

# Pages whose search result already carries at least this much text aren't scraped again
MIN_CONTENT_CHARS = 500
CONTEXT_CHUNKS = 12


class InsufficientEvidence(Exception):
    """Too few usable sources were found to write a trustworthy report."""


async def _no_progress(stage: str, message: str) -> None:
    pass


def plan_queries(topic: str) -> list[str]:
    """Splits a topic into searches that cover the report's sections."""
    year = date.today().year
    return [
        topic,
        f"{topic} market size and growth",
        f"{topic} competitors and pricing",
        f"{topic} industry trends {year}",
    ]


async def discover_sources(topic: str) -> list[SearchResult]:
    settings = get_settings()
    provider = get_search_provider()
    queries = plan_queries(topic)
    batches = await asyncio.gather(
        *(provider.search(q, settings.research_max_sources) for q in queries), return_exceptions=True
    )

    seen: set[str] = set()
    results: list[SearchResult] = []
    errors = []
    # Interleave the searches so each one contributes its best results first
    lists = []
    for batch in batches:
        if isinstance(batch, Exception):
            errors.append(batch)
        else:
            lists.append(batch)
    if not lists:
        raise SearchError(f"Every search failed: {errors[0]}")
    for rank in range(max(len(b) for b in lists)):
        for batch in lists:
            if rank < len(batch) and batch[rank].url.rstrip("/") not in seen:
                seen.add(batch[rank].url.rstrip("/"))
                results.append(batch[rank])
    return results


async def fetch_page_text(result: SearchResult) -> str | None:
    if result.content and len(result.content) >= MIN_CONTENT_CHARS:
        return result.content
    try:
        return await asyncio.wait_for(
            scrape_core_content(result.url), timeout=get_settings().page_fetch_timeout_seconds
        )
    except Exception as e:
        logger.warning(f"Skipping {result.url}: {e}")
        return None


async def collect_sources(topic: str, progress: ProgressCallback) -> list[Source]:
    """Searches the web for the topic, reads the best pages and stores them. Returns the sources used."""
    settings = get_settings()
    await progress("searching", f"Searching the web for {topic!r}")
    candidates = await discover_sources(topic)
    await progress("reading", f"Found {len(candidates)} candidate pages, reading the best ones")

    sources: list[Source] = []
    semaphore = asyncio.Semaphore(3)

    async def read(result: SearchResult) -> tuple[SearchResult, str | None]:
        async with semaphore:
            return result, await fetch_page_text(result)

    # Read more candidates than needed, since some pages fail or are too thin
    pending = candidates[: settings.research_max_sources * 2]
    for result, text in await asyncio.gather(*(read(r) for r in pending)):
        if len(sources) >= settings.research_max_sources:
            break
        if not text or len(text) < MIN_CONTENT_CHARS:
            continue
        chunks = await run_in_threadpool(chunk_text, text)
        await store_documents(chunks, result.url, result.title)
        sources.append(
            Source(
                id=len(sources) + 1,
                url=result.url,
                title=result.title,
                retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        )
        await progress("reading", f"Read {len(sources)} of up to {settings.research_max_sources} sources")

    if len(sources) < settings.research_min_sources:
        raise InsufficientEvidence(
            f"Only {len(sources)} usable sources were found for this topic; at least "
            f"{settings.research_min_sources} are needed. Try a broader or differently worded topic."
        )
    return sources


def _sources_from_chunks(chunks: list[dict]) -> list[Source]:
    """Builds the source list for reports made only from previously scraped pages."""
    sources: list[Source] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        url = meta.get("url")
        if url and all(s.url != url for s in sources):
            sources.append(Source(id=len(sources) + 1, url=url, title=meta.get("title") or url, retrieved_at=""))
    return sources


def apply_citations(draft: ReportDraft, sources: list[Source]) -> MarketResearchReport:
    """Keeps only citations that point at real sources and drops statements left without any."""
    valid = {s.id for s in sources}

    def keep(ids: list[int]) -> list[int]:
        return sorted({i for i in ids if i in valid})

    def cited(items: list[CitedText]) -> list[CitedText]:
        out = []
        for item in items:
            ids = keep(item.source_ids)
            if ids:
                out.append(CitedText(text=item.text, source_ids=ids))
            else:
                logger.info(f"Dropped unsupported statement: {item.text[:80]!r}")
        return out

    competitors = []
    for c in draft.competitors:
        ids = keep(c.source_ids)
        if ids:
            competitors.append(c.model_copy(update={"source_ids": ids}))
        else:
            logger.info(f"Dropped unsupported competitor: {c.name!r}")

    return MarketResearchReport(
        industry_name=draft.industry_name,
        executive_summary=draft.executive_summary,
        executive_summary_source_ids=keep(draft.executive_summary_source_ids),
        key_trends=cited(draft.key_trends),
        competitors=competitors,
        whitespace_opportunities=cited(draft.whitespace_opportunities),
        sources=sources,
    )


async def run_research(topic: str, progress: ProgressCallback | None = None) -> MarketResearchReport:
    """
    Produces a cited report for any topic: finds sources on the web when a search API is configured,
    otherwise uses pages previously stored with /scrape.
    """
    progress = progress or _no_progress

    if get_search_provider() is not None:
        sources = await collect_sources(topic, progress)
        await progress("analyzing", f"Picking the most relevant passages from {len(sources)} sources")
        chunks = await retrieve_context(topic, top_k=CONTEXT_CHUNKS, urls=[s.url for s in sources])
        if not chunks:
            raise InsufficientEvidence(
                "The sources were found but could not be searched. Check that the embedding service (Ollama) is running."
            )
    else:
        chunks = await retrieve_context(topic, top_k=CONTEXT_CHUNKS)
        if not chunks:
            raise InsufficientEvidence(
                "No stored sources match this topic. Set TAVILY_API_KEY or BRAVE_API_KEY to research from the web."
            )
        sources = _sources_from_chunks(chunks)

    await progress("writing", "Writing the report")
    draft = await generate_research_report(topic, chunks, {s.url: s.id for s in sources})
    return apply_citations(draft, sources)
