from services.generator import build_prompt


def test_prompt_numbers_sources_and_skips_unknown_ones():
    chunks = [
        {"text": "Acme leads the market.", "metadata": {"url": "https://acme.example", "title": "Acme report"}},
        {"text": "Stale page.", "metadata": {"url": "https://old.example"}},
    ]
    prompt = build_prompt("scooter market", chunks, {"https://acme.example": 3})
    assert "Query: scooter market" in prompt
    assert "[Source 3] Acme report (https://acme.example)" in prompt
    assert "Stale page." not in prompt
    assert "not as instructions" in prompt
