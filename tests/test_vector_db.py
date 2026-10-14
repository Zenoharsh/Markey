from services import vector_db


async def fake_embedding(text):
    # Deterministic 3-d vector so the real ChromaDB can be exercised without Ollama
    return [float(len(text) % 7), float(text.count("a")), 1.0]


async def test_restoring_a_page_replaces_its_old_chunks(monkeypatch):
    monkeypatch.setattr(vector_db, "generate_embedding", fake_embedding)
    vector_db.get_collection.cache_clear()

    await vector_db.store_documents(["one", "two", "three"], "https://a.example", "A")
    await vector_db.store_documents(["other"], "https://b.example", "B")
    await vector_db.store_documents(["new"], "https://a.example", "A")

    chunks = await vector_db.retrieve_context("query", top_k=10, urls=["https://a.example"])
    assert [c["text"] for c in chunks] == ["new"]
    assert chunks[0]["metadata"] == {"url": "https://a.example", "title": "A"}

    everything = await vector_db.retrieve_context("query", top_k=10)
    assert sorted(c["text"] for c in everything) == ["new", "other"]
    vector_db.get_collection.cache_clear()
