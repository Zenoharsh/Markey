import chromadb
import hashlib
import logging
import asyncio
from fastapi.concurrency import run_in_threadpool
from functools import lru_cache

from config import get_settings
from services.embeddings import generate_embedding

logger = logging.getLogger(__name__)


@lru_cache
def get_collection():
    # Opened on first use so importing this module doesn't create a database on disk
    client = chromadb.PersistentClient(path=get_settings().chroma_path)
    return client.get_or_create_collection(name="market_research")

async def store_documents(chunks: list[str], source_url: str, title: str = ""):
    if not chunks:
        return

    # Replace any chunks stored from an earlier fetch of this page, so a shorter page leaves no stale chunks
    await run_in_threadpool(get_collection().delete, where={"url": source_url})
        
    # Generate embeddings concurrently for speed
    tasks = [generate_embedding(chunk) for chunk in chunks]
    embeddings = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid_embeddings = []
    ids = []
    metadatas = []
    documents = []
    
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        if isinstance(emb, Exception):
            logger.error(f"Failed to generate embedding for chunk {i}: {emb}")
            continue
            
        valid_embeddings.append(emb)
        # Deterministic chunk ID prevents duplicates on re-scrape
        chunk_id = hashlib.sha256(f"{source_url}_{i}".encode()).hexdigest()
        ids.append(chunk_id)
        metadatas.append({"url": source_url, "title": title})
        documents.append(chunk)
            
    if ids:
        # Offload synchronous ChromaDB upsert to a threadpool
        await run_in_threadpool(
            get_collection().upsert,
            ids=ids,
            embeddings=valid_embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info(f"Upserted {len(ids)} chunks to ChromaDB.")

async def retrieve_context(query: str, top_k: int = 5, urls: list[str] | None = None) -> list[dict]:
    """Returns the chunks closest to the query, optionally only from the given source URLs."""
    try:
        query_embedding = await generate_embedding(query)
        where = {"url": {"$in": urls}} if urls else None

        # Offload synchronous ChromaDB query to a threadpool
        results = await run_in_threadpool(
            get_collection().query,
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        
        context_chunks = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            for doc, meta in zip(docs, metas):
                context_chunks.append({
                    "text": doc,
                    "metadata": meta
                })
        return context_chunks
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}")
        return []
