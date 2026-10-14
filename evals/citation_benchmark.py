"""
Runs the research pipeline on a fixed set of topics and scores how well each report's citations hold up.

    python -m evals.citation_benchmark            # all 10 topics
    python -m evals.citation_benchmark --limit 2  # a quick check

For every statement that survives in the report, it measures how many of the statement's content words
appear in the pages it cites. That is a cheap, automatic proxy for "the source actually says this";
low scores point at statements worth reading by hand. Results go to evals/results/.
"""

import argparse
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from models.request_models import MarketResearchReport
from services import research
from services.vector_db import get_collection

TOPICS = [
    "electric scooter sharing",
    "AI note-taking apps",
    "plant-based protein",
    "cloud gaming",
    "pet insurance",
    "home solar batteries",
    "online language learning",
    "meal kit delivery",
    "cybersecurity for small businesses",
    "smart rings",
]

# A statement counts as supported when this share of its content words appears in its cited sources
SUPPORT_THRESHOLD = 0.6
STOPWORDS = set(
    "about above after again against also among because been before being between both but could does doing "
    "down during each from further have having here into itself just more most must only other over same "
    "should some such than that their them then there these they this those through under until very were "
    "what when where which while will with within would your".split()
)
RESULTS_DIR = Path(__file__).parent / "results"


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in STOPWORDS}


def support_score(statement: str, source_text: str) -> float:
    """Share of the statement's content words found in the cited source text (1.0 when it has none)."""
    words = content_words(statement)
    if not words:
        return 1.0
    return len(words & content_words(source_text)) / len(words)


def statements(report: MarketResearchReport) -> list[tuple[str, list[int]]]:
    items = [(report.executive_summary, report.executive_summary_source_ids)]
    for section in (
        report.key_trends, report.growth_drivers, report.challenges, report.customer_segments,
        report.whitespace_opportunities, report.recommendations,
    ):
        items += [(t.text, t.source_ids) for t in section]
    items += [(f.rationale, f.source_ids) for f in report.competitive_forces]
    items += [
        (f"{c.name} {c.core_value_proposition}", c.source_ids)
        for c in report.competitors
    ]
    return [(text, ids) for text, ids in items if ids]


async def source_texts(report: MarketResearchReport) -> dict[int, str]:
    texts = {}
    for source in report.sources:
        stored = await run_in_threadpool(get_collection().get, where={"url": source.url})
        texts[source.id] = " ".join(stored.get("documents") or [])
    return texts


async def score_topic(topic: str) -> dict:
    started = time.perf_counter()
    try:
        report = await research.run_research(topic)
    except Exception as e:
        return {"topic": topic, "error": f"{type(e).__name__}: {e}", "seconds": round(time.perf_counter() - started, 1)}

    texts = await source_texts(report)
    scored = [
        {"text": text, "source_ids": ids, "support": round(support_score(text, " ".join(texts.get(i, "") for i in ids)), 2)}
        for text, ids in statements(report)
    ]
    supports = [s["support"] for s in scored]
    return {
        "topic": topic,
        "seconds": round(time.perf_counter() - started, 1),
        "sources": len(report.sources),
        "statements": len(scored),
        "dropped": report.removed_statements,
        "dropped_figures": report.removed_figures,
        "figures": len(report.key_figures),
        "mean_support": round(sum(supports) / len(supports), 2) if supports else 0.0,
        "supported_share": round(sum(s >= SUPPORT_THRESHOLD for s in supports) / len(supports), 2) if supports else 0.0,
        "weakest": sorted(scored, key=lambda s: s["support"])[:3],
    }


def to_markdown(results: list[dict], started_at: str) -> str:
    lines = [
        f"# Citation benchmark, {started_at}",
        "",
        f"Supported means at least {SUPPORT_THRESHOLD:.0%} of a statement's content words appear in its cited sources.",
        "",
        "| Topic | Sources | Statements | Dropped | Figures kept / dropped | Mean support | Supported | Seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['topic']} | failed: {r['error']} | | | | | | {r['seconds']} |")
        else:
            lines.append(
                f"| {r['topic']} | {r['sources']} | {r['statements']} | {r['dropped']} | "
                f"{r.get('figures', 0)} / {r.get('dropped_figures', 0)} | {r['mean_support']:.2f} | {r['supported_share']:.0%} | {r['seconds']} |"
            )
    ok = [r for r in results if "error" not in r]
    if ok:
        lines += [
            "",
            f"**Overall:** {len(ok)} of {len(results)} topics finished, mean support "
            f"{sum(r['mean_support'] for r in ok) / len(ok):.2f}, "
            f"{sum(r['supported_share'] for r in ok) / len(ok):.0%} of statements supported.",
        ]
    return "\n".join(lines) + "\n"


async def main(limit: int | None) -> None:
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    results = []
    for topic in TOPICS[:limit]:
        print(f"Researching {topic!r}...", flush=True)
        results.append(await score_topic(topic))
        print(json.dumps({k: v for k, v in results[-1].items() if k != "weakest"}), flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (RESULTS_DIR / f"{stamp}.json").write_text(json.dumps(results, indent=2))
    (RESULTS_DIR / f"{stamp}.md").write_text(to_markdown(results, started_at))
    print(f"\nSaved evals/results/{stamp}.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None, help="only run the first N topics")
    asyncio.run(main(parser.parse_args().limit))
