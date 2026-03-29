# Kevin Dashboard — Design Spec

## Overview

Streamlit-based dashboard for visualizing Kevin Planning Agent runs. Reads `.kevin/runs/` YAML state files and `blueprints/` YAML directly from the filesystem. Targets technical team demos.

## Tech Stack

- **Streamlit** — UI framework
- **PyYAML** — YAML parsing (already a Kevin dependency)
- **streamlit-mermaid** — Block dependency graph visualization
- **Plotly** — Gantt chart for block execution timeline

## File Structure

```
kevin/dashboard/
├── app.py                # Entry point + page routing
├── data_loader.py        # Data access layer (reuses kevin.state + kevin.blueprint_loader)
├── seed.py               # Sample data generator for demo without real runs
├── components/
│   ├── run_list.py       # Page 1: Run list with summary metrics
│   ├── run_detail.py     # Page 2: Run detail with block pipeline + logs
│   └── blueprint_view.py # Page 3: Blueprint viewer with dependency graph
└── requirements.txt      # streamlit, pyyaml, streamlit-mermaid, plotly
```

## Pages

### Page 1: Run List

- **Top**: Summary metric cards (total runs / passed / failed / running)
- **Body**: Table with columns:
  - Run ID | Blueprint | Issue # | Status (icon) | Block Progress (2/3) | Started At | Elapsed
- Click row → navigate to Run Detail

### Page 2: Run Detail

- **Top**: Run metadata (run_id, blueprint_id, issue_number, repo, status)
- **Middle**: Block pipeline visualization
  - Mermaid flowchart: `B1 --> B2 --> B3` with color-coded status
  - Green = passed, Red = failed, Grey = pending, Blue = running
- **Bottom**: Block detail panel (expandable per block)
  - Status, runner type, exit code, retries, elapsed time
  - Validator results list
  - Expandable log viewer (prompt + stdout + stderr)
- **Timeline**: Plotly Gantt chart showing each block's execution duration

### Page 3: Blueprint Viewer

- **Left**: Blueprint list (from `blueprints/` directory)
- **Right**:
  - Blueprint metadata (id, name, version, tags)
  - Block dependency graph (Mermaid flowchart)
  - Block table: block_id | name | runner | timeout | max_retries | validators

## Data Layer

### Interfaces

```python
# Run data
def list_runs(state_dir: Path) -> list[RunSummary]
def load_run(state_dir: Path, run_id: str) -> RunDetail
def load_block_log(state_dir: Path, run_id: str, block_id: str) -> str

# Blueprint data
def list_blueprints(blueprints_dir: Path) -> list[BlueprintSummary]
def load_blueprint(blueprints_dir: Path, blueprint_id: str) -> BlueprintDetail
```

### Data Models

```python
@dataclass(frozen=True)
class RunSummary:
    run_id: str
    blueprint_id: str
    issue_number: int
    repo: str
    status: str              # completed | failed | running
    blocks_passed: int
    blocks_total: int
    started_at: str
    elapsed_seconds: float | None

@dataclass(frozen=True)
class BlockDetail:
    block_id: str
    name: str
    status: str              # pending | running | passed | failed
    runner: str
    exit_code: int | None
    retries: int
    started_at: str
    completed_at: str
    validator_results: list[dict]
    error: str

@dataclass(frozen=True)
class BlueprintSummary:
    blueprint_id: str
    blueprint_name: str
    version: str
    tags: list[str]
    block_count: int
```

### Key Decisions

- **Reuse Kevin code**: `data_loader.py` imports `kevin.state.StateManager` and `kevin.blueprint_loader` internally
- **Read-only**: Dashboard never writes to any file
- **Fault-tolerant**: Skip runs with unparseable YAML, show warning in sidebar

## Seed Script

`python -m kevin.dashboard.seed --target-repo .` generates sample `.kevin/runs/` data with:
- 1 completed run (3 blocks all passed)
- 1 failed run (B1 passed, B2 failed)
- 1 running run (B1 passed, B2 running)

This ensures demo works without running Kevin against a real GitHub Issue.

## Launch

```bash
pip install streamlit pyyaml streamlit-mermaid plotly
python -m kevin.dashboard.seed --target-repo .    # optional
streamlit run kevin/dashboard/app.py -- --kevin-root . --blueprints-dir blueprints
```

## Scope Boundaries

- No write operations
- No authentication
- No WebSocket/real-time updates (can add later)
- No deployment config (local dev only)
