from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from models.request_models import ScrapeRequest, ResearchQuery, MarketResearchReport
from services.scraper import scrape_core_content
from services.chunker import chunk_text
from services.vector_db import store_documents
from services import jobs, store
from services.research import run_research
from config import get_settings
from fastapi.concurrency import run_in_threadpool
import uvicorn
import logging
import sys
import asyncio
import json

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure basic logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    interrupted = await run_in_threadpool(store.mark_interrupted_runs)
    if interrupted:
        logging.info(f"Marked {interrupted} unfinished research runs as interrupted")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Markey API",
    description="Researches any market topic from the web and returns reports where every claim cites its source.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to the Markey API. POST /research (or /research/stream) with a topic to get a cited report."}

@app.post("/scrape")
async def scrape_endpoint(request: ScrapeRequest):
    """
    Takes a target URL, loads the page (waiting for network idle to handle JS-rendered content), 
    and extracts the raw text. Strips out all HTML tags, navbars, and footers.
    """
    try:
        # Convert HttpUrl to string for the scraper
        content = await scrape_core_content(str(request.url))
        
        # Offload synchronous CPU-bound chunking to threadpool
        chunks = await run_in_threadpool(chunk_text, content)
        logging.info(f"Generated {len(chunks)} chunks for {request.url}")
        
        # Store chunks in vector DB
        await store_documents(chunks, str(request.url))
        
        return {
            "url": str(request.url), 
            "content": content,
            "chunk_count": len(chunks)
        }
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _sse(events):
    async def encode():
        async for event in events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(encode(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/research", response_model=MarketResearchReport)
async def research_endpoint(request: ResearchQuery):
    """
    Researches any topic: finds sources on the web, reads them and returns a report
    in which every statement cites the sources it came from. The report is also saved to history.
    """
    job = jobs.start_job(request.query, run_research)
    await asyncio.shield(job.task)
    final = job.events[-1]
    if final["type"] == "error":
        raise HTTPException(status_code=final["status"], detail=final["detail"])
    return final["report"]


@app.post("/research/jobs", status_code=202)
async def start_research_job(request: ResearchQuery):
    """Starts researching a topic in the background. Follow it with GET /research/jobs/{id}/events."""
    job = jobs.start_job(request.query, run_research)
    return {"id": job.id, "topic": job.topic}


@app.get("/research/jobs/{job_id}/events")
async def research_job_events(job_id: str):
    """
    Server-sent events for a job, replayed from the start so a client can reconnect at any time.
    Events are JSON objects with a `type` of "job", "progress", "report" or "error".
    """
    if not jobs.job_exists(job_id):
        raise HTTPException(status_code=404, detail="No research job with this id.")
    return _sse(jobs.follow(job_id))


@app.post("/research/stream")
async def research_stream_endpoint(request: ResearchQuery):
    """Starts a job and streams its events in one request. The first event carries the job id."""
    job = jobs.start_job(request.query, run_research)
    return _sse(jobs.follow(job.id))


@app.get("/reports")
async def list_reports(limit: int = Query(50, ge=1, le=200)):
    """Recent research runs, newest first."""
    return await run_in_threadpool(store.list_runs, limit)


@app.get("/reports/{report_id}")
async def get_report(report_id: str):
    run = await run_in_threadpool(store.get_run, report_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return run


@app.delete("/reports/{report_id}", status_code=204)
async def delete_report(report_id: str):
    if not await run_in_threadpool(store.delete_run, report_id):
        raise HTTPException(status_code=404, detail="Report not found.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
