# Market Researcher RAG Pipeline - Architecture Map

This document outlines the architecture, data flow, setup commands, and requirements for the FastAPI Market Research RAG System.

## Architecture Overview

The system is a fully local, robust Retrieval-Augmented Generation (RAG) pipeline designed for asynchronous web scraping and market research.

```mermaid
graph TD
    subgraph Client
        A1[Client Request]
    end

    subgraph API_Layer [API Layer main.py]
        A[FastAPI Server]
        B[/scrape POST]
        C[/research POST]
    end

    subgraph Ingestion [Data Ingestion Pipeline]
        D[Scraper Service <br/> playwright + bs4]
        E[Chunker Service <br/> Langchain]
        F[Embeddings Service <br/> Ollama / nomic]
        G[(ChromaDB Persistent <br/> Vector Store)]
    end

    subgraph Generation [Generation Pipeline]
        H[Context Retrieval <br/> ChromaDB]
        I[Generator Service <br/> Ollama llama3.2 or Claude API]
        J[Structured Output <br/> Pydantic]
    end

    A1 -->|1. Submit URL| B
    B --> D
    D -->|Raw HTML/Text| E
    E -->|Text Chunks| F
    F -->|Vector Embeddings| G
    
    A1 -->|2. Submit Query| C
    C --> H
    H -->|Query Embeddings| F
    F -->|Nearest Neighbors| G
    G -->|Top 5 Chunks| H
    H -->|Context + Query| I
    I -->|JSON Generation| J
    J -->|ResearchReport| A1
```

## Research pipeline (`POST /research`, `POST /research/stream`)

`services/research.py` runs each report with a team of agents, the way a consultancy splits an engagement. Their prompts and section schemas live in `services/agents.py`.

1. **Scope:** one web search for the topic, then the scoping agent names the market precisely, defines what it includes, picks the geography, lists adjacent markets, and writes three searches for each workstream (`MarketScope`). The top results are read as the first sources while it works.
2. **Research in parallel:** four analysts run at the same time, one per workstream: market sizing, competitive landscape, customers and demand, and trends and risks. Each one runs its searches (Tavily, falling back to Brave), reads up to `SOURCES_PER_AGENT` new pages, retrieves the passages for its workstream from every page any agent has read, and writes its section with source ids.
3. **Fill gaps:** an analyst whose section misses something essential (no market size, fewer than three described competitors, fewer than two customer segments or trends) runs the follow-up searches it proposed and writes its section again, once.
4. **Verify:** `apply_citations` checks the combined findings against the passages the analysts saw.
5. **Synthesise:** the strategist reads only the verified findings and writes the executive summary, whitespace opportunities and recommendations, citing the sources behind the findings it used.

All agents share one numbered source list (`SourceLibrary`), capped at `REPORT_MAX_SOURCES` pages, so a source has the same number everywhere in the brief. Pages are claimed before reading, so two analysts never read the same page. Fewer than `RESEARCH_MIN_SOURCES` usable pages stops the run with a 422. With a local Ollama model, LLM calls run one at a time; hosted models run the four analysts at once. A failed analyst leaves its section empty and is noted in the data gaps instead of failing the report.

Without a search API key, the searches are skipped and the analysts use pages stored earlier with `/scrape`.

## What a report contains

`ReportDraft` (models/request_models.py) follows a consultancy brief: executive summary, key figures (market size, forecasts, growth rates, shares), trends, growth drivers, challenges, customer segments, competitors, Porter's five forces, whitespace opportunities, recommendations and data gaps. Each analyst retrieves its own passages (`gather_evidence`), so every section has evidence.

`apply_citations` drops any item without a valid source, and drops any number (key figure or market share) that doesn't appear in the text of a passage it cites. The report counts what was removed and shows it in its method note.

## Jobs and saved reports

Every run is a background job (`services/jobs.py`) saved in SQLite (`services/store.py`, `DATABASE_PATH`, default `./markey.db`).

- `POST /research/jobs` starts a run and returns its id.
- `GET /research/jobs/{id}/events` streams server-sent events: `job`, then `progress` per stage, then `report` or `error`. Events replay from the start, so a client can reconnect after a reload or dropped connection; the run keeps going either way.
- `POST /research/stream` starts a job and streams it in one request; `POST /research` waits and returns the report.
- `GET /reports`, `GET /reports/{id}` and `DELETE /reports/{id}` serve the history. Runs left unfinished by a server restart are marked failed on startup.

The dashboard gives each run its own address (`#/r/<id>`), so reloading the page reconnects to a running report.

## Citation benchmark

`python -m evals.citation_benchmark` researches 10 fixed topics and scores each statement by how many of its content words appear in the pages it cites. Results are written to `evals/results/` (not committed).

## Application Lifecycle & Components

### 1. Data Ingestion (`/scrape`)
1. **`services/scraper.py`**: Uses headless Playwright to load dynamic JS-heavy websites, waiting for network idle. BeautifulSoup strips out navbars, footers, scripts, and styles to isolate the core article/main tag text.
2. **`services/chunker.py`**: Uses LangChain's `RecursiveCharacterTextSplitter.from_tiktoken_encoder`. Processes text chunks accurately by token limits (500 tokens, 50-token overlap). Runs on a background thread pool to prevent CPU event-loop blocking.
3. **`services/embeddings.py`**: Calls a local Ollama instance (`http://localhost:11434/api/embed`) using the `nomic-embed-text` model. Run concurrently using `asyncio.gather`.
4. **`services/vector_db.py`**: Hashes chunk data deterministically to prevent duplicates and synchronously upserts the text, embeddings, and URL metadata into a local ChromaDB collection (`./chroma_db`), offloaded to a thread pool.

### 2. Research Generation (`/research`)
1. **Context Retrieval**: Queries ChromaDB with the user's research query (converted to an embedding) and fetches the top 5 nearest chunks.
2. **`services/generator.py`**: Injects the context chunks and the strict JSON Schema representation of the `ResearchReport` Pydantic Model into an engineered system prompt.
3. **Structured LLM Call** (`services/llm.py`): The configured provider returns a validated `MarketResearchReport`. Ollama (`llama3.2` by default) uses `format: "json"` and gets one retry on malformed output; the Claude API uses structured outputs, with a server-side fallback model on safety declines. Unusable output becomes a 502 with a clear message instead of a fake report.

## Technical Stack & Packages

| Package | Purpose |
|---------|---------|
| `fastapi`, `uvicorn` | High-performance asynchronous REST API framework and server |
| `playwright`, `beautifulsoup4` | Async headless browser automation and HTML parsing/cleaning |
| `pydantic` | Data validation and JSON schema enforcement |
| `langchain-text-splitters`, `tiktoken` | Token-aware document chunking and splitting |
| `httpx` | Fast, asynchronous HTTP client for calling the local Ollama API |
| `chromadb` | Local, persistent vector database for semantic chunk retrieval |

## Setup & Build Commands

### 1. Environment & Dependencies
```bash
# Create and activate a virtual environment
python -m venv venv

# Windows Activation
venv\Scripts\activate

# Install python dependencies
pip install -r requirements.txt

# Download Playwright Chromium binaries
python -m playwright install chromium
```

### 2. Local LLM Setup (Ollama)
The system relies on Ollama running locally on its default port (`11434`). You must pull the required models:
```bash
# Install the highly optimized embedding model
ollama pull nomic-embed-text

# Install the generation model (set OLLAMA_CHAT_MODEL to use another)
ollama pull llama3.2

# Ensure Ollama is running in the background (or another terminal)
ollama serve
```

### 3. Run the Server
The application includes a safeguard against the Windows `SelectorEventLoop` bug by forcibly applying the `WindowsProactorEventLoopPolicy`.
```bash
# Run the FastAPI server directly
python main.py
```
> The API will be available at `http://localhost:8000`. You can explore the interactive Swagger docs at `http://localhost:8000/docs`.
