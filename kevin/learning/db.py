"""SQLite schema, connection, and CRUD operations for the knowledge database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VARIABLES_WHITELIST = frozenset({
    "issue_number", "issue_title", "issue_labels",
    "repo_full", "owner", "repo",
})

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run_history (
    run_id          TEXT PRIMARY KEY,
    blueprint_id    TEXT NOT NULL,
    issue_number    INTEGER,
    issue_title     TEXT,
    repo            TEXT,
    status          TEXT NOT NULL,
    total_blocks    INTEGER,
    passed_blocks   INTEGER,
    failed_block_id TEXT,
    failure_reason  TEXT,
    elapsed_seconds REAL,
    created_at      TEXT,
    variables_json  TEXT
);

CREATE TABLE IF NOT EXISTS block_history (
    run_id          TEXT NOT NULL,
    block_id        TEXT NOT NULL,
    blueprint_id    TEXT NOT NULL,
    block_name      TEXT,
    runner          TEXT,
    status          TEXT NOT NULL,
    exit_code       INTEGER,
    retries         INTEGER DEFAULT 0,
    elapsed_seconds REAL,
    error           TEXT,
    validator_json  TEXT,
    PRIMARY KEY (run_id, block_id)
);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS block_logs_fts USING fts5(
    run_id,
    block_id,
    blueprint_id,
    status,
    issue_title,
    issue_body,
    prompt,
    output_summary,
    tokenize='porter unicode61'
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open or create the knowledge database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.Connection(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and FTS if they don't exist."""
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_FTS_SQL)


def upsert_run(conn: sqlite3.Connection, *, run_id: str, blueprint_id: str,
               issue_number: int | None, issue_title: str | None,
               repo: str | None, status: str,
               total_blocks: int, passed_blocks: int,
               failed_block_id: str | None, failure_reason: str | None,
               elapsed_seconds: float | None, created_at: str | None,
               variables_json: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO run_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, blueprint_id, issue_number, issue_title, repo, status,
         total_blocks, passed_blocks, failed_block_id, failure_reason,
         elapsed_seconds, created_at, variables_json),
    )
    conn.commit()


def upsert_block(conn: sqlite3.Connection, *, run_id: str, block_id: str,
                 blueprint_id: str, block_name: str | None, runner: str | None,
                 status: str, exit_code: int | None, retries: int,
                 elapsed_seconds: float | None, error: str | None,
                 validator_json: str | None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO block_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, block_id, blueprint_id, block_name, runner, status,
         exit_code, retries, elapsed_seconds, error, validator_json),
    )
    conn.commit()


def delete_fts(conn: sqlite3.Connection, *, run_id: str, block_id: str) -> None:
    conn.execute(
        "DELETE FROM block_logs_fts WHERE run_id = ? AND block_id = ?",
        (run_id, block_id),
    )


def upsert_fts(conn: sqlite3.Connection, *, run_id: str, block_id: str,
               blueprint_id: str, status: str, issue_title: str,
               issue_body: str, prompt: str, output_summary: str) -> None:
    conn.execute(
        "INSERT INTO block_logs_fts VALUES (?,?,?,?,?,?,?,?)",
        (run_id, block_id, blueprint_id, status, issue_title,
         issue_body, prompt, output_summary),
    )
    conn.commit()


def safe_variables_json(variables: dict[str, str]) -> str:
    return json.dumps({k: v for k, v in variables.items() if k in VARIABLES_WHITELIST})
