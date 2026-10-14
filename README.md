# Markey

AI-powered market research: type a topic or product and get a structured brief covering the industry, trends, competitors and whitespace opportunities. Every statement links to the web sources it came from.

The backend is FastAPI. It scrapes pages, stores them in ChromaDB and writes reports with an LLM, either local Ollama or the hosted Claude API. The frontend is a React + Vite dashboard. See [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow.

## Quick start

### Backend

```bash
python -m venv venv
venv\Scripts\activate            # Windows (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python -m playwright install chromium

copy .env.example .env           # macOS/Linux: cp .env.example .env
python main.py                   # http://localhost:8000/docs
```

To research any topic from the live web, set `TAVILY_API_KEY` (and optionally `BRAVE_API_KEY` as a fallback) in `.env`. Without a search key, reports only use pages you've added with `POST /scrape`.

Embeddings always use Ollama, so run `ollama pull nomic-embed-text` and keep `ollama serve` running.

To write reports with Ollama (the default), also run `ollama pull llama3.2`. To write them with Claude instead, set the following in `.env`:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5-5   # or claude-haiku-5-5 for the cheaper tier
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Set `VITE_API_BASE_URL` in `frontend/.env` if the backend isn't at `http://localhost:8000`.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
cd frontend && npm run lint && npm run build
```

CI runs the same checks on every pull request.

To measure citation quality against real search and a real model, run `python -m evals.citation_benchmark` (add `--limit 2` for a quick check). It writes a table to `evals/results/`.
