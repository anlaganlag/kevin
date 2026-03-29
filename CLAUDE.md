# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AgenticSDLC** (codename: **Kevin**) is a blueprint-driven orchestrator that turns GitHub Issues into autonomous AI agent workflows. It classifies issues by label, selects a Blueprint YAML, and executes Blocks via Claude Code CLI, shell commands, or HTTP calls — with wave-based parallel scheduling, validation, and Teams notifications.

The repo has two layers:
- **Design docs & architecture specs** (`design_doc.md`, `agents/`, `agentic_sdlc_*.md`) — the original v2.0 vision
- **Working implementation** (`kevin/`, `blueprints/`, `.github/workflows/`) — the Kevin Planning Agent

## Build & Development Commands

```bash
# CLI commands (run from repo root)
python -m kevin run --issue 42 --repo owner/repo [--target-repo ./path] [--dry-run]
python -m kevin run-block --block B2 --run-id <id>
python -m kevin resume --run-id <id>
python -m kevin list-runs
python -m kevin debug --run-id <id> --block B2    # Replay failed prompt in interactive Claude CLI
python -m kevin harvest                           # Backfill knowledge.db from historical runs

# Executor-as-a-Service mode
python -m kevin run --run-id <id> --instruction <task> --blueprint <id> --context <json>

# Tests (uses pytest)
python -m pytest kevin/tests/ -v                  # Run all tests
python -m pytest kevin/tests/test_cli_executor.py -v  # Single test file
python -m pytest kevin/tests/ -k "test_executor" -v   # Run tests matching name

# Dashboard (optional deps)
pip install -e ".[dashboard]"
streamlit run kevin/dashboard/app.py

# E2E test for Supabase executor service
bash scripts/test_executor_e2e.sh  # Requires EXECUTOR_API_KEY, EXECUTOR_BASE_URL

# Python version: >=3.11
# Core dependency: pyyaml>=6.0
```

## Kevin Architecture

### Execution Flow

```
GitHub Issue (label: "kevin") → GitHub Actions → kevin run
  → classify labels → select Blueprint → create Run state
  → compute dependency waves → execute Blocks (parallel within waves)
  → validate each Block → harvest learning → post results
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `kevin/cli.py` | CLI entry point; orchestrates the full run lifecycle |
| `kevin/agent_runner.py` | Block execution via pluggable runners + validators |
| `kevin/blueprint_loader.py` | Parses Blueprint YAML, resolves dependencies, topological sort |
| `kevin/scheduler.py` | Groups Blocks into parallel execution waves (by dependency level + cwd conflict) |
| `kevin/state.py` | File-based run state persistence in `.kevin/runs/{run_id}/` |
| `kevin/config.py` | Runtime config; label→blueprint intent map with aliases |
| `kevin/intent.py` | Classifies GitHub labels to Blueprint IDs |
| `kevin/learning/` | SQLite knowledge base; harvests run data, advises future runs |
| `kevin/teams_bot/cards.py` | Microsoft Teams Adaptive Cards for real-time notifications |
| `kevin/dashboard/` | Streamlit monitoring dashboard |

### Three Runner Types

- **`claude_cli`** (default): Invokes `claude -p <prompt> --cwd <dir>` with a rendered prompt template
- **`shell`**: Runs a shell command; exit code 0 = success
- **`api_call`**: HTTP request via urllib; status 2xx = success

### Three Validator Types

- **`git_diff_check`**: Confirms Block produced file changes (min_files_changed)
- **`command`**: Runs shell command; exit 0 = pass
- **`file_exists`**: Checks file/glob exists

### State Management

Each run creates `.kevin/runs/{run_id}/` containing:
- `run.yaml` — overall run metadata and block states
- `{B1,B2,...}.yaml` — per-block execution state
- `blueprint_snapshot.yaml` — immutable copy for reproducibility
- `logs/{block_id}.log` — full prompt + stdout + stderr per block

### Template Variables

Prompt templates use `{{variable}}` syntax. Available variables include:
`issue_number`, `issue_title`, `issue_body`, `issue_labels`, `target_repo`, `owner`, `repo`, `repo_full`, `pr_number`, `learning_context`

### Intent Classification

GitHub labels map to Blueprints via `kevin/config.py:DEFAULT_INTENT_MAP`. Alias labels (e.g., "enhancement"→"coding-task") resolve first through the exact map, then through aliases. The `kevin` label triggers execution.

### Wave-Based Scheduling

Blocks are grouped by dependency level (topological sort), then split within each level by resolved `cwd` to prevent parallel writes to the same directory. Blocks in the same wave with different cwds run concurrently.

## Blueprint Structure

Blueprints live in `blueprints/` as YAML files named `bp_{domain}_{type}_{name}.{version}.yaml`.

Each Blueprint contains ordered Blocks with:
- `block_id` (B1, B2, ...), `dependencies`, `runner`, `runner_config`
- `timeout` (seconds), `max_retries`, `pre_check` (shell command for idempotent reset on retry)
- `validators` (machine-checkable), `acceptance_criteria` (human-readable)
- `prompt_file` or inline `prompt_template` (Jinja-style `{{var}}` substitution)

Templates: `blueprints/templates/blueprint_template.yaml`, `blueprints/blocks/block_template.yaml`

## Design Architecture (v2.0 Spec)

The design documents describe a five-layer EDA architecture:
1. **Infra Dependency Layer (EEF)** — static/dynamic constraints shaping agent behavior
2. **Standard Interfaces** — Issues, Tasks, Commits, Pipelines, Artifacts
3. **Event-Driven Architecture** — event bus, routing, pub/sub
4. **Agent Orchestration** — Ralph Loop 5-step framework
5. **Governance & Audit** — cross-cutting oversight at multiple points

Governance separation: execution agents create changes, audit agents report facts, governance layer decides, humans resolve ambiguity.

Two HITL gates: Blueprint Approval (before implementation), Release Approval (before merge to main).

Key design docs: `design_doc.md` (comprehensive), `agentic_sdlc_architecture.md` (diagrams), `agentic_sdlc_workflow.md` (sequences), `agents/agent_*.md` (11 agent specs).

## CI/CD

GitHub Actions workflows (`.github/workflows/`):
- **kevin.yaml**: Triggered by adding "kevin" label to any Issue
- **kevin-executor.yaml**: Executor-as-a-Service for external callers
- **kevin-dispatch.yaml**: Manual workflow dispatch
- **kevin-reusable.yaml**: Reusable workflow template

Required secrets: `ANTHROPIC_API_KEY`, `CHECKOUT_TOKEN`. Optional: `TEAMS_BOT_URL`, `TEAMS_BOT_SECRET`.

## Conventions

- State directories (`.kevin/`, `knowledge.db`) are gitignored — never commit run state
- Learning system degrades silently — never let knowledge DB issues block execution
- Blueprint snapshots are immutable after run creation — ensures reproducibility
- All GitHub operations use the `gh` CLI (no token management in code)
- Agent-completed events use fenced ` ```eda ` JSON blocks in issue comments
- Chinese comments are used throughout design docs and blueprint templates
