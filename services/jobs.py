"""Runs research in the background so a closed tab or dropped connection doesn't lose the report."""

import asyncio
import logging
import time
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

from models.request_models import MarketResearchReport
from services import store
from services.llm import LLMError
from services.research import InsufficientEvidence, ProgressCallback
from services.search import SearchError

logger = logging.getLogger(__name__)

Research = Callable[[str, ProgressCallback], Awaitable[MarketResearchReport]]

# Finished jobs kept in memory for reconnecting clients; older ones are served from the database
MAX_FINISHED_JOBS = 50
TERMINAL = ("report", "error")


def describe_error(e: Exception) -> tuple[int, str]:
    """Maps a research failure to the HTTP status and message the client sees."""
    if isinstance(e, InsufficientEvidence):
        return 422, str(e)
    if isinstance(e, (LLMError, SearchError)):
        return 502, str(e)
    if isinstance(e, httpx.TimeoutException):
        return 504, "A service timed out while generating the report."
    logger.error(f"Unexpected research error: {e}\n{traceback.format_exc()}")
    return 500, "Something went wrong while generating the report."


class Job:
    def __init__(self, job_id: str, topic: str):
        self.id = job_id
        self.topic = topic
        self.events: list[dict] = []
        self.changed = asyncio.Condition()
        self.task: asyncio.Task | None = None

    @property
    def finished(self) -> bool:
        return bool(self.events) and self.events[-1]["type"] in TERMINAL

    async def emit(self, event: dict) -> None:
        async with self.changed:
            self.events.append(event)
            self.changed.notify_all()


_jobs: dict[str, Job] = {}


def _prune() -> None:
    finished = [job_id for job_id, job in _jobs.items() if job.finished]
    for job_id in finished[: max(0, len(finished) - MAX_FINISHED_JOBS)]:
        del _jobs[job_id]


def start_job(topic: str, research: Research) -> Job:
    job = Job(store.create_run(topic), topic)
    _jobs[job.id] = job

    async def progress(stage: str, message: str, agent: str | None = None, done: bool = False) -> None:
        event = {"type": "progress", "stage": stage, "message": message}
        if agent:
            event |= {"agent": agent, "done": done}
        await job.emit(event)

    async def run() -> None:
        started = time.perf_counter()
        try:
            report = await research(topic, progress)
        except asyncio.CancelledError:
            store.fail_run(job.id, 503, store.INTERRUPTED, time.perf_counter() - started)
            raise
        except Exception as e:
            status, detail = describe_error(e)
            store.fail_run(job.id, status, detail, time.perf_counter() - started)
            await job.emit({"type": "error", "status": status, "detail": detail})
        else:
            store.finish_run(job.id, report, time.perf_counter() - started)
            await job.emit({"type": "report", "id": job.id, "report": report.model_dump()})
        _prune()

    job.task = asyncio.create_task(run())
    return job


def job_exists(job_id: str) -> bool:
    return job_id in _jobs or store.get_run(job_id) is not None


async def follow(job_id: str) -> AsyncIterator[dict]:
    """Yields every event of a job from the start, then live ones until it finishes."""
    yield {"type": "job", "id": job_id}
    job = _jobs.get(job_id)
    if job is None:
        # Not running in this process: replay the stored outcome
        run = store.get_run(job_id)
        if run and run["report"]:
            yield {"type": "report", "id": job_id, "report": run["report"]}
        else:
            detail = (run or {}).get("error") or store.INTERRUPTED
            yield {"type": "error", "status": (run or {}).get("error_status") or 503, "detail": detail}
        return

    seen = 0
    while True:
        async with job.changed:
            await job.changed.wait_for(lambda: len(job.events) > seen)
            new = job.events[seen:]
        seen += len(new)
        for event in new:
            yield event
        if job.finished:
            return
