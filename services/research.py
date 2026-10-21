import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool

from config import get_settings
from models.request_models import (
    CitedText,
    KeyFigure,
    MarketResearchReport,
    MarketScope,
    ReportDraft,
    Source,
    StrategySection,
)
from services.agents import WORKSTREAMS, Workstream, scope_prompt, section_prompt, strategy_prompt
from services.chunker import chunk_text
from services.llm import get_llm_provider
from services.scraper import scrape_core_content
from services.search import FallbackSearch, SearchError, SearchResult, get_search_provider
from services.vector_db import retrieve_context, store_documents

logger = logging.getLogger(__name__)

# Called with (stage, message), plus the agent's key and whether it finished, as the research run progresses
ProgressCallback = Callable[..., Awaitable[None]]

# Pages whose search result already carries at least this much text aren't scraped again
MIN_CONTENT_CHARS = 500
# Data gaps kept in the final brief, across all workstreams
MAX_DATA_GAPS = 8


class InsufficientEvidence(Exception):
    """Too few usable sources were found to write a trustworthy report."""


async def _no_progress(stage: str, message: str, agent: str | None = None, done: bool = False) -> None:
    pass


async def gather_evidence(queries: list[str], urls: list[str] | None, budget: int | None = None) -> list[dict]:
    """Retrieves passages for each query and merges them without duplicates, up to the budget."""
    budget = budget or get_settings().context_chunks
    per_query = max(2, -(-budget // len(queries)))
    batches = await asyncio.gather(*(retrieve_context(q, top_k=per_query, urls=urls) for q in queries))
    chunks, seen = [], set()
    # Round-robin so each query keeps its best passages if the budget cuts the list
    for rank in range(per_query):
        for batch in batches:
            if rank >= len(batch):
                continue
            key = (batch[rank].get("metadata", {}).get("url"), batch[rank]["text"])
            if key not in seen:
                seen.add(key)
                chunks.append(batch[rank])
    return chunks[:budget]


async def search_all(search: FallbackSearch, queries: list[str]) -> list[SearchResult]:
    """Runs the searches together and interleaves their results, best first, without repeated pages."""
    batches = await asyncio.gather(
        *(search.search(q, get_settings().sources_per_agent) for q in queries), return_exceptions=True
    )
    lists = [b for b in batches if not isinstance(b, Exception)]
    if not lists:
        raise SearchError(f"Every search failed: {batches[0]}")
    seen: set[str] = set()
    results: list[SearchResult] = []
    for rank in range(max((len(b) for b in lists), default=0)):
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


class SourceLibrary:
    """Every page the agents have read, numbered in the order it was added. All agents cite from it."""

    def __init__(self, limit: int):
        self.sources: list[Source] = []
        self.limit = limit
        self._claimed: set[str] = set()
        self._reading = asyncio.Semaphore(3)

    @property
    def urls(self) -> list[str]:
        return [s.url for s in self.sources]

    def ids(self) -> dict[str, int]:
        return {s.url: s.id for s in self.sources}

    def _add(self, url: str, title: str, retrieved_at: str) -> None:
        self.sources.append(Source(id=len(self.sources) + 1, url=url, title=title, retrieved_at=retrieved_at))

    async def read(self, results: list[SearchResult], max_new: int) -> int:
        """Reads up to `max_new` pages no agent has claimed yet and stores them. Returns how many were added."""
        # Claim pages before reading, so agents running in parallel never read the same page twice
        pending = []
        for result in results:
            key = result.url.rstrip("/")
            if key not in self._claimed and len(pending) < max_new * 2:
                self._claimed.add(key)
                pending.append(result)

        async def fetch(result: SearchResult) -> tuple[SearchResult, str | None]:
            async with self._reading:
                return result, await fetch_page_text(result)

        added = 0
        for result, text in await asyncio.gather(*(fetch(r) for r in pending)):
            if added >= max_new or len(self.sources) >= self.limit:
                break
            if not text or len(text) < MIN_CONTENT_CHARS:
                continue
            chunks = await run_in_threadpool(chunk_text, text[: get_settings().max_page_chars])
            await store_documents(chunks, result.url, result.title)
            self._add(result.url, result.title, datetime.now(timezone.utc).isoformat(timespec="seconds"))
            added += 1
        return added

    def add_stored(self, chunks: list[dict]) -> None:
        """Registers previously scraped pages, for research without a search API."""
        known = set(self.urls)
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            url = meta.get("url")
            if url and url not in known:
                known.add(url)
                self._add(url, meta.get("title") or url, "")


def _number_forms(value: float) -> set[str]:
    forms = set()
    if value == int(value):
        forms |= {str(int(value)), f"{int(value):,}"}
    for decimals in (1, 2, 3):
        for text in (f"{value:.{decimals}f}", f"{value:,.{decimals}f}"):
            forms.add(text)
            if "." in text:
                forms.add(text.rstrip("0").rstrip("."))
    return forms


def number_stated(value: float, text: str) -> bool:
    """True when the number appears in the text as written, e.g. 12.5 in "grew 12.5% a year" (but not in "112.5")."""
    return any(
        re.search(rf"(?<![\d.,]){re.escape(form)}(?![\d]|[.,]\d)", text) for form in _number_forms(value)
    )


def apply_citations(draft: ReportDraft, sources: list[Source], evidence: dict[int, str] | None = None) -> MarketResearchReport:
    """
    Keeps only citations that point at real sources and drops statements left without any.
    With `evidence` (the passage text the model saw, by source id), numbers must also appear in a cited passage.
    """
    valid = {s.id for s in sources}
    removed = {"statements": 0, "figures": 0}

    def keep(ids: list[int]) -> list[int]:
        return sorted({i for i in ids if i in valid})

    def verified(value: float, ids: list[int]) -> bool:
        return evidence is None or any(number_stated(value, evidence.get(i, "")) for i in ids)

    def cited(items: list[CitedText]) -> list[CitedText]:
        out = []
        for item in items:
            ids = keep(item.source_ids)
            if ids:
                out.append(CitedText(text=item.text, source_ids=ids))
            else:
                removed["statements"] += 1
                logger.info(f"Dropped unsupported statement: {item.text[:80]!r}")
        return out

    figures: list[KeyFigure] = []
    for figure in draft.key_figures:
        ids = keep(figure.source_ids)
        if ids and verified(figure.value, ids):
            figures.append(figure.model_copy(update={"source_ids": ids}))
        else:
            removed["figures"] += 1
            logger.info(f"Dropped unverified figure: {figure.label} = {figure.value} {figure.unit}")

    competitors = []
    for c in draft.competitors:
        ids = keep(c.source_ids)
        if not ids:
            removed["statements"] += 1
            logger.info(f"Dropped unsupported competitor: {c.name!r}")
            continue
        update: dict = {"source_ids": ids}
        if c.market_share_percent is not None and not verified(c.market_share_percent, ids):
            removed["figures"] += 1
            update["market_share_percent"] = None
        competitors.append(c.model_copy(update=update))

    forces = []
    for force in draft.competitive_forces:
        ids = keep(force.source_ids)
        if ids:
            forces.append(force.model_copy(update={"source_ids": ids}))
        else:
            removed["statements"] += 1

    return MarketResearchReport(
        industry_name=draft.industry_name,
        executive_summary=draft.executive_summary,
        executive_summary_source_ids=keep(draft.executive_summary_source_ids),
        key_figures=figures,
        key_trends=cited(draft.key_trends),
        growth_drivers=cited(draft.growth_drivers),
        challenges=cited(draft.challenges),
        customer_segments=cited(draft.customer_segments),
        competitors=competitors,
        competitive_forces=forces,
        whitespace_opportunities=cited(draft.whitespace_opportunities),
        recommendations=cited(draft.recommendations),
        data_gaps=[gap for gap in draft.data_gaps if gap.strip()],
        sources=sources,
        removed_statements=removed["statements"],
        removed_figures=removed["figures"],
    )




async def run_workstream(
    workstream: Workstream,
    scope: MarketScope,
    library: SourceLibrary,
    search: FallbackSearch | None,
    progress: ProgressCallback,
    llm_slots: asyncio.Semaphore,
):
    """One analyst: searches for its workstream, reads new pages, writes its section, and searches once more for gaps."""
    settings = get_settings()

    async def say(message: str) -> None:
        await progress("researching", message, workstream.key)

    queries = [q for q in getattr(scope, workstream.queries_field) if q.strip()][:3]
    queries = queries or workstream.default_queries(scope.market_name)
    section, chunks = None, []
    for round_ in range(2):
        if search:
            await say(f"Searching for {queries[0]!r}" + (f" and {len(queries) - 1} more" if len(queries) > 1 else ""))
            try:
                results = await search_all(search, queries)
            except SearchError as e:
                logger.warning(f"{workstream.key} searches failed: {e}")
                results = []
            added = await library.read(results, settings.sources_per_agent)
            await say(f"Read {added} new source{'' if added == 1 else 's'}")
            if not library.sources:
                break
        evidence_queries = workstream.evidence_queries(scope.market_name) + queries
        chunks = await gather_evidence(evidence_queries, library.urls if search else None)
        if not search:
            library.add_stored(chunks)
        if not chunks:
            break
        await say(f"Analysing {len(chunks)} passages")
        async with llm_slots:
            section = await get_llm_provider().generate_structured(
                section_prompt(workstream, scope, chunks, library.ids()), workstream.schema
            )
        follow_ups = [q for q in section.follow_up_queries if q.strip()][:3]
        if round_ or not search or not follow_ups or not workstream.incomplete(section):
            break
        queries = follow_ups
        await say("Searching again for what's missing")
    await progress("researching", "Finished" if section else "Found nothing to analyse", workstream.key, True)
    return section, chunks


async def run_research(topic: str, progress: ProgressCallback | None = None) -> MarketResearchReport:
    """
    Produces a cited report for any topic with a team of agents: a scoping agent defines the market, four analysts
    research their workstreams in parallel, and a strategist writes the summary and recommendations.
    Finds sources on the web when a search API is configured, otherwise uses pages previously stored with /scrape.
    """
    progress = progress or _no_progress
    settings = get_settings()
    started = time.perf_counter()
    search = get_search_provider()
    llm = get_llm_provider()
    library = SourceLibrary(settings.report_max_sources)
    # A local model answers one request at a time, so queueing more only causes timeouts
    llm_slots = asyncio.Semaphore(1 if settings.llm_provider == "ollama" else len(WORKSTREAMS))

    initial: list[SearchResult] = []
    if search:
        await progress("scoping", f"Searching the web for {topic!r}")
        initial = await search_all(search, [topic])
    await progress("scoping", "Naming the market and planning each analyst's searches")
    scope, _ = await asyncio.gather(
        llm.generate_structured(scope_prompt(topic, initial), MarketScope),
        library.read(initial, settings.sources_per_agent),
    )
    await progress("scoping", f"{scope.market_name}: {scope.definition}")

    await progress("researching", "Four analysts are researching in parallel")
    outcomes = await asyncio.gather(
        *(run_workstream(w, scope, library, search, progress, llm_slots) for w in WORKSTREAMS),
        return_exceptions=True,
    )
    failures = [o for o in outcomes if isinstance(o, Exception)]
    if len(failures) == len(outcomes):
        raise failures[0]
    if len(library.sources) < settings.research_min_sources:
        if not search:
            raise InsufficientEvidence(
                "No stored sources match this topic. Set TAVILY_API_KEY or BRAVE_API_KEY to research from the web."
            )
        raise InsufficientEvidence(
            f"Only {len(library.sources)} usable sources were found for this topic; at least "
            f"{settings.research_min_sources} are needed. Try a broader or differently worded topic."
        )

    sections, gaps, evidence = {}, [], {}
    ids = library.ids()
    for workstream, outcome in zip(WORKSTREAMS, outcomes):
        if isinstance(outcome, Exception):
            logger.error(f"The {workstream.key} analyst failed: {outcome}")
            gaps.append(f"The {workstream.title.lower()} research could not be completed this time.")
            continue
        section, chunks = outcome
        if section is None:
            continue
        sections[workstream.key] = section
        gaps += section.data_gaps
        for chunk in chunks:
            source_id = ids.get(chunk.get("metadata", {}).get("url"))
            if source_id is not None:
                evidence[source_id] = evidence.get(source_id, "") + "\n" + chunk["text"]

    def part(key: str, field: str) -> list:
        return getattr(sections[key], field) if key in sections else []

    findings = apply_citations(
        ReportDraft(
            industry_name=scope.market_name,
            executive_summary="",
            executive_summary_source_ids=[],
            key_figures=part("sizing", "key_figures"),
            key_trends=part("trends", "key_trends"),
            growth_drivers=part("demand", "growth_drivers"),
            challenges=part("trends", "challenges"),
            customer_segments=part("demand", "customer_segments"),
            competitors=part("competition", "competitors"),
            competitive_forces=part("competition", "competitive_forces"),
            whitespace_opportunities=[],
            recommendations=[],
            data_gaps=list(dict.fromkeys(g.strip() for g in gaps if g.strip()))[:MAX_DATA_GAPS],
        ),
        library.sources,
        evidence,
    )

    await progress("writing", "Writing the summary and recommendations from the verified findings")
    try:
        async with llm_slots:
            strategy = await llm.generate_structured(strategy_prompt(scope, findings), StrategySection)
    except Exception as e:
        # The analysts' verified findings are still worth delivering without the strategist's summary
        logger.error(f"The strategist failed: {e}")
        strategy = StrategySection(
            executive_summary="The summary could not be written this time; the findings below are complete and verified.",
            executive_summary_source_ids=[], whitespace_opportunities=[], recommendations=[],
        )
    report = apply_citations(
        ReportDraft(**findings.model_dump(include=set(ReportDraft.model_fields)) | strategy.model_dump()),
        library.sources,
    )
    logger.info(f"Researched {scope.market_name!r} from {len(library.sources)} sources in {time.perf_counter() - started:.1f}s")
    return report.model_copy(
        update={
            "market_definition": scope.definition,
            "removed_statements": findings.removed_statements + report.removed_statements,
            "removed_figures": findings.removed_figures + report.removed_figures,
        }
    )
