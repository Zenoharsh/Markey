from evals.citation_benchmark import support_score, to_markdown


def test_support_score_counts_content_words_found_in_sources():
    source = "Lime operates the largest scooter network across European and American cities."
    assert support_score("Lime operates the largest scooter network", source) == 1.0
    assert support_score("Lime is profitable in Asia", source) < 0.5
    assert support_score("it is", source) == 1.0


def test_markdown_summarises_finished_and_failed_topics():
    results = [
        {"topic": "a", "sources": 5, "statements": 10, "dropped": 1, "figures": 4, "dropped_figures": 2, "mean_support": 0.8, "supported_share": 0.9, "seconds": 30},
        {"topic": "b", "error": "InsufficientEvidence: none", "seconds": 4},
    ]
    md = to_markdown(results, "2026-10-14")
    assert "| a | 5 | 10 | 1 | 4 / 2 | 0.80 | 90% | 30 |" in md
    assert "failed: InsufficientEvidence" in md
    assert "1 of 2 topics finished" in md
