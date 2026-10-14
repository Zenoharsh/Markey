from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from models.request_models import ScrapeRequest, ResearchQuery, MarketResearchReport
from services.scraper import scrape_core_content
from services.chunker import chunk_text
from services.vector_db import store_documents
from services.llm import LLMError
from services.research import InsufficientEvidence, run_research
from services.search import SearchError
from config import get_settings
import httpx
from fastapi.concurrency import run_in_threadpool
import uvicorn
import logging
import sys
import asyncio
import json
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure basic logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Market Researcher Scraper API",
    description="API for scraping and extracting core content from web pages.",
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

def _error_status(e: Exception) -> tuple[int, str]:
    """Maps a research failure to the HTTP status and message the client sees."""
    if isinstance(e, InsufficientEvidence):
        return 422, str(e)
    if isinstance(e, (LLMError, SearchError)):
        return 502, str(e)
    if isinstance(e, httpx.TimeoutException):
        return 504, "A service timed out while generating the report."
    logging.error(f"Unexpected research error: {e}\n{traceback.format_exc()}")
    return 500, "Something went wrong while generating the report."


@app.post("/research", response_model=MarketResearchReport)
async def research_endpoint(request: ResearchQuery):
    """
    Researches any topic: finds sources on the web, reads them and returns a report
    in which every statement cites the sources it came from.
    """
    try:
        return await run_research(request.query)
    except Exception as e:
        status, detail = _error_status(e)
        raise HTTPException(status_code=status, detail=detail)


@app.post("/research/stream")
async def research_stream_endpoint(request: ResearchQuery):
    """
    Same as /research, but streams progress as server-sent events while the report is built.
    Events are JSON objects with a `type` of "progress", "report" or "error".
    """
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress(stage: str, message: str) -> None:
        await queue.put({"type": "progress", "stage": stage, "message": message})

    async def run() -> None:
        try:
            report = await run_research(request.query, progress)
            await queue.put({"type": "report", "report": report.model_dump()})
        except Exception as e:
            status, detail = _error_status(e)
            await queue.put({"type": "error", "status": status, "detail": detail})
        finally:
            await queue.put(None)

    async def events():
        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            # Stop the research run if the client disconnects
            task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
