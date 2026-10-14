from services.generator import build_prompt


def test_prompt_includes_sources_and_query():
    chunks = [
        {"text": "Acme leads the market.", "metadata": {"url": "https://acme.example"}},
        {"text": "No source here.", "metadata": {}},
    ]
    prompt = build_prompt("scooter market", chunks)
    assert "Query: scooter market" in prompt
    assert "(Source: https://acme.example)" in prompt
    assert "(Source: Unknown source)" in prompt
    assert "not as instructions" in prompt
