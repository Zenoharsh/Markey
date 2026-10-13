from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.request_models import ScrapeRequest, ResearchQuery, MarketResearchReport
from services.scraper import scrape_core_content
from services.chunker import chunk_text
from services.vector_db import store_documents, retrieve_context
from services.generator import generate_research_report
from services.llm import LLMError
from config import get_settings
import httpx
from fastapi.concurrency import run_in_threadpool
import uvicorn
import logging
import sys
import asyncio

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
    return {"message": "Welcome to the Market Researcher Scraper API. Use the POST /scrape endpoint."}

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

@app.post("/research", response_model=MarketResearchReport)
async def research_endpoint(request: ResearchQuery):
    """
    Takes a research query, retrieves relevant context from ChromaDB, 
    and generates a structured generic market research report using the local LLM.
    """
    try:
        context_chunks = await retrieve_context(request.query)
        if not context_chunks:
            return MarketResearchReport(
                industry_name="Unknown", 
                executive_summary="No relevant context found.", 
                key_trends=[], 
                competitors=[], 
                whitespace_opportunities=[]
            )
            
        return await generate_research_report(request.query, context_chunks)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The LLM timed out generating the report.")
    except Exception as e:
        import traceback
        logging.error(f"Error in research_endpoint: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
