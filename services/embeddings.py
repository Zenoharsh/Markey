import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

# Chunks sent to Ollama per request; one request per batch is far faster than one per chunk
BATCH_SIZE = 32


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Embeds the texts with the configured Ollama model, in order, using as few requests as possible."""
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/embed"
    embeddings: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            response = await client.post(url, json={"model": settings.ollama_embed_model, "input": batch})
            response.raise_for_status()
            vectors = response.json().get("embeddings") or []
            if len(vectors) != len(batch):
                logger.error("Ollama returned %d embeddings for %d texts", len(vectors), len(batch))
                raise ValueError("Ollama returned the wrong number of embeddings")
            embeddings.extend(vectors)
    return embeddings


async def generate_embedding(text: str) -> list[float]:
    return (await generate_embeddings([text]))[0]
