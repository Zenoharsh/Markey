import json

import httpx

from services import embeddings


async def test_embeds_chunks_in_batches(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body["input"])
        return httpx.Response(200, json={"embeddings": [[float(len(t))] for t in body["input"]]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        embeddings.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    texts = [f"chunk {i}" for i in range(embeddings.BATCH_SIZE + 3)]
    vectors = await embeddings.generate_embeddings(texts)

    assert [len(c) for c in calls] == [embeddings.BATCH_SIZE, 3]
    assert vectors == [[float(len(t))] for t in texts]
