import httpx
import logging

logger = logging.getLogger(__name__)

async def generate_embedding(text: str) -> list[float]:
    """
    Connects to a local Ollama instance and uses the nomic-embed-text model
    to generate embeddings for a given text chunk.
    """
    url = "http://localhost:11434/api/embed"
    payload = {
        "model": "nomic-embed-text",
        "input": text
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            # The API returns 'embeddings' which is a list of lists.
            # Since we provide a single string input, we return the first embedding.
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
            elif "embedding" in data:
                # Fallback for /api/embeddings standard (older Ollama format)
                return data["embedding"]
            else:
                logger.error("Unexpected response structure from Ollama: %s", data)
                raise ValueError("Could not find embedding in response from Ollama")
                
    except Exception as e:
        logger.error(f"Error generating embedding from Ollama: {str(e)}")
        raise e
