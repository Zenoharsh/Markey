import httpx
import asyncio
import json

async def run_test():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("1. Testing /scrape endpoint...")
        # Scrape a simple page, e.g., example.com
        scrape_payload = {"url": "https://example.com"}
        resp = await client.post("http://localhost:8000/scrape", json=scrape_payload)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Scrape Success! Chunk count: {data.get('chunk_count')}")
        else:
            print(f"Scrape Failed: {resp.status_code} - {resp.text}")
            return

        print("\n2. Testing /research endpoint...")
        research_payload = {"query": "What is the domain established to be used for?"}
        resp = await client.post("http://localhost:8000/research", json=research_payload)
        if resp.status_code == 200:
            data = resp.json()
            print("Research Success!")
            print(json.dumps(data, indent=2))
        else:
            print(f"Research Failed: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    asyncio.run(run_test())
