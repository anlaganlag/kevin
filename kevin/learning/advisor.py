"""Pre-run context query — generates learning context from historical runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kevin.utils import extract_keywords


@dataclass(frozen=True)
class FailurePattern:
    block_id: str
    reason: str
    count: int


@dataclass(frozen=True)
class SimilarSnippet:
    run_id: str
    issue_title: str
    output_summary: str


@dataclass(frozen=True)
class LearningContext:
    """Structured learning context (machine-readable)."""
    success_rate: float | None
    total_runs: int
    common_failures: list[FailurePattern] = field(default_factory=list)
    similar_snippets: list[SimilarSnippet] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)


_EMPTY_CONTEXT = LearningContext(success_rate=None, total_runs=0)


def advise(db_path: Path, blueprint_id: str, issue_title: str, issue_body: str) -> LearningContext:
    """Query SQLite and generate historical context. Silent degradation on ANY error (C1)."""
    try:
        return _advise_impl(db_path, blueprint_id, issue_title, issue_body)
    except Exception:
        return _EMPTY_CONTEXT


def _advise_impl(db_path: Path, blueprint_id: str, issue_title: str, issue_body: str) -> LearningContext:
    if not db_path.exists():
        return _EMPTY_CONTEXT

    from kevin.learning.db import connect, ensure_schema

    conn = connect(db_path)
    ensure_schema(conn)
    try:
        stats = _query_stats(conn, blueprint_id)
        if stats is None:
            return _EMPTY_CONTEXT
        success_rate, total_runs = stats
        failures = _query_common_failures(conn, blueprint_id)
        similar = _query_similar_runs(conn, blueprint_id, issue_title, issue_body)
        warnings = _build_risk_warnings(conn, blueprint_id)
        return LearningContext(
            success_rate=success_rate, total_runs=total_runs,
            common_failures=failures, similar_snippets=similar, risk_warnings=warnings,
        )
    finally:
        conn.close()


def _query_stats(conn, blueprint_id: str) -> tuple[float, int] | None:
    row = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) "
        "FROM run_history WHERE blueprint_id = ?", (blueprint_id,)
    ).fetchone()
    total = row[0] or 0
    if total == 0:
        return None
    completed = row[1] or 0
    return completed / total, total


def _query_common_failures(conn, blueprint_id: str) -> list[FailurePattern]:
    rows = conn.execute(
        "SELECT block_id, error, COUNT(*) as cnt FROM block_history "
        "WHERE blueprint_id = ? AND status = 'failed' AND error IS NOT NULL AND error != '' "
        "GROUP BY block_id, error ORDER BY cnt DESC LIMIT 5", (blueprint_id,)
    ).fetchall()
    return [FailurePattern(block_id=r[0], reason=(r[1] or "")[:200], count=r[2]) for r in rows]


def _query_similar_runs(conn, blueprint_id: str, issue_title: str, issue_body: str) -> list[SimilarSnippet]:
    keywords = extract_keywords(issue_title)
    if not keywords:
        return []
    # FTS5 requires all terms by default; use OR so any matching keyword returns results
    fts_query = " OR ".join(keywords.split())
    try:
        rows = conn.execute(
            "SELECT run_id, issue_title, output_summary, rank FROM block_logs_fts "
            "WHERE block_logs_fts MATCH ? AND status = 'passed' AND blueprint_id = ? "
            "ORDER BY rank LIMIT 5", (fts_query, blueprint_id)
        ).fetchall()
    except Exception:
        return []
    seen_runs: set[str] = set()
    snippets: list[SimilarSnippet] = []
    for r in rows:
        rid = r[0]
        if rid in seen_runs:
            continue
        seen_runs.add(rid)
        snippets.append(SimilarSnippet(
            run_id=rid, issue_title=(r[1] or "")[:200], output_summary=(r[2] or "")[:300]))
        if len(snippets) >= 2:
            break
    return snippets


def _build_risk_warnings(conn, blueprint_id: str) -> list[str]:
    warnings: list[str] = []
    last_run = conn.execute(
        "SELECT status, failed_block_id FROM run_history "
        "WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1", (blueprint_id,)
    ).fetchone()
    if last_run and last_run[0] == "failed" and last_run[1]:
        warnings.append(f"Last run failed at {last_run[1]}")
    return warnings


def format_learning_context(ctx: LearningContext, *, max_chars: int = 1200) -> str:
    """Render to plain ASCII text. No emoji (constraint C5)."""
    sections: list[str] = []
    if ctx.success_rate is not None:
        pct = f"{ctx.success_rate:.0%}"
        sections.append(f"[History] This Blueprint: {pct} success rate ({ctx.total_runs} runs)")
    for fp in ctx.common_failures[:2]:
        sections.append(f"[Warning] {fp.block_id} common failure: {fp.reason} ({fp.count}x)")
    for sn in ctx.similar_snippets[:2]:
        truncated = sn.output_summary[:300]
        sections.append(f"[Reference] Similar issue '{sn.issue_title}': {truncated}")
    for w in ctx.risk_warnings[:2]:
        sections.append(f"[Risk] {w}")
    result = "\n".join(sections)
    return result[:max_chars]
