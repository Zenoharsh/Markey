"""Saves research runs and their reports so they survive restarts and can be reopened later."""

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from config import get_settings
from models.request_models import MarketResearchReport

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    duration_seconds REAL,
    report TEXT,
    error_status INTEGER,
    error TEXT
)
"""

INTERRUPTED = "The server restarted before this report finished. Please run it again."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def _write(sql: str, params: tuple) -> int:
    with closing(_connect()) as conn, conn:
        return conn.execute(sql, params).rowcount


def create_run(topic: str) -> str:
    run_id = uuid.uuid4().hex
    _write("INSERT INTO reports (id, topic, status, created_at) VALUES (?, ?, 'running', ?)", (run_id, topic, _now()))
    return run_id


def finish_run(run_id: str, report: MarketResearchReport, duration_seconds: float) -> None:
    _write(
        "UPDATE reports SET status = 'done', finished_at = ?, duration_seconds = ?, report = ? WHERE id = ?",
        (_now(), round(duration_seconds, 1), report.model_dump_json(), run_id),
    )


def fail_run(run_id: str, status: int, detail: str, duration_seconds: float) -> None:
    _write(
        "UPDATE reports SET status = 'failed', finished_at = ?, duration_seconds = ?, error_status = ?, error = ? "
        "WHERE id = ?",
        (_now(), round(duration_seconds, 1), status, detail, run_id),
    )


def mark_interrupted_runs() -> int:
    """Runs still marked running when the server starts were cut off by a restart."""
    return _write(
        "UPDATE reports SET status = 'failed', finished_at = ?, error_status = 503, error = ? WHERE status = 'running'",
        (_now(), INTERRUPTED),
    )


def _summary(row: sqlite3.Row) -> dict:
    report = json.loads(row["report"]) if row["report"] else None
    return {
        "id": row["id"],
        "topic": row["topic"],
        "status": row["status"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
        "duration_seconds": row["duration_seconds"],
        "industry_name": report["industry_name"] if report else None,
        "source_count": len(report["sources"]) if report else 0,
        "error": row["error"],
    }


def get_run(run_id: str) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return {
        **_summary(row),
        "error_status": row["error_status"],
        "report": json.loads(row["report"]) if row["report"] else None,
    }


def list_runs(limit: int = 50) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return [_summary(row) for row in rows]


def delete_run(run_id: str) -> bool:
    return _write("DELETE FROM reports WHERE id = ?", (run_id,)) > 0
