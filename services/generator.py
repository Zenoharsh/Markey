import httpx
import logging
import json
from models.request_models import MarketResearchReport

logger = logging.getLogger(__name__)

async def generate_research_report(query: str, context_chunks: list[dict]) -> dict:
    """
    Calls local Ollama API to generate a research report strictly formatted as JSON.
    """
    context_text = ""
    for i, chunk in enumerate(context_chunks):
        url = chunk.get("metadata", {}).get("url", "Unknown source")
        context_text += f"--- Chunk {i+1} (Source: {url}) ---\n{chunk['text']}\n\n"
        
    schema = MarketResearchReport.model_json_schema()
    
    prompt = f"""You are an elite, industry-agnostic market research analyst. Analyze the provided context and the user's specific query to identify the industry being discussed. Extract key trends. Identify the competitors mentioned in the context. For each competitor, extract their pricing model, value proposition, and target audience. Assign a `market_strength_score` from 1 to 10 based on their competitive advantage or market share. Finally, identify `whitespace_opportunities` where a new entrant could succeed.

Query: {query}

Context:
{context_text}

CRITICAL RULES:
1. You must return your response strictly as a JSON object exactly matching the template below.
2. Never output null values. If a field's value cannot be determined, output "Unknown" or "N/A" for strings, 0 for integers, and [] for lists.
3. Do not include any explanations, markdown formatting, or text outside the JSON object.

JSON TEMPLATE TO FILL OUT:
{{
  "industry_name": "...",
  "executive_summary": "...",
  "key_trends": ["...", "..."],
  "competitors": [
    {{
      "name": "...",
      "pricing_model": "...",
      "core_value_proposition": "...",
      "target_audience": "...",
      "market_strength_score": 5
    }}
  ],
  "whitespace_opportunities": ["...", "..."]
}}
"""

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3.2",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            response_text = data.get("response", "{}")
            # Parse the JSON to ensure it's valid, and return the dict
            try:
                parsed_json = json.loads(response_text)
                return parsed_json
            except json.JSONDecodeError:
                logger.error(f"Ollama returned invalid JSON: {response_text}")
                return {
                    "industry_name": "Unknown",
                    "executive_summary": "Failed to parse JSON response",
                    "key_trends": [],
                    "competitors": [],
                    "whitespace_opportunities": []
                }
                
    except Exception as e:
        logger.error(f"Error generating report from Ollama: {str(e)}")
        raise e
