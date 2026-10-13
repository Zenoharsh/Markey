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
