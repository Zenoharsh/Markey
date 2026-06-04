import chromadb
import hashlib
import logging
import asyncio
from fastapi.concurrency import run_in_threadpool
from services.embeddings import generate_embedding

logger = logging.getLogger(__name__)

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="market_research")

async def store_documents(chunks: list[str], source_url: str):
    if not chunks:
        return
        
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
        metadatas.append({"url": source_url})
        documents.append(chunk)
            
    if ids:
        # Offload synchronous ChromaDB upsert to a threadpool
        await run_in_threadpool(
            collection.upsert,
            ids=ids,
            embeddings=valid_embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info(f"Upserted {len(ids)} chunks to ChromaDB.")

async def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    try:
        query_embedding = await generate_embedding(query)
        
        # Offload synchronous ChromaDB query to a threadpool
        results = await run_in_threadpool(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=top_k
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
