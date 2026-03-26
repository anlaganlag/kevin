"""Load Blueprint YAML and extract an ordered list of executable blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Validator:
    """A single machine-executable validation check."""

    type: str                 # git_diff_check | command | file_exists
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Block:
    """A single executable unit within a Blueprint."""

    block_id: str
    name: str
    assigned_to: str
    dependencies: list[str]
    runner: str               # claude_cli | shell | api_call
    runner_config: dict[str, Any]
    timeout: int              # seconds
    max_retries: int
    prompt_template: str      # for claude_cli blocks
    output: str
    validators: list[Validator]
    acceptance_criteria: list[str]
    pre_check: str            # shell command to run before block (idempotency reset)
    raw: dict[str, Any]       # original YAML dict for extensions


@dataclass(frozen=True)
class Blueprint:
    """Parsed Blueprint with ordered block list."""

    blueprint_id: str
    blueprint_name: str
    version: str
    blocks: list[Block]       # topologically sorted
    raw: dict[str, Any]


def load(blueprint_path: Path) -> Blueprint:
    """Load a Blueprint YAML file and return a parsed Blueprint."""
    with blueprint_path.open() as f:
        data = yaml.safe_load(f)

    bp = data.get("blueprint", data)
    metadata = bp.get("metadata", {})

    raw_blocks = _extract_blocks(bp)
    blocks = [_parse_block(b) for b in raw_blocks]
    sorted_blocks = _topological_sort(blocks)

    return Blueprint(
        blueprint_id=metadata.get("blueprint_id", ""),
        blueprint_name=metadata.get("blueprint_name", ""),
        version=metadata.get("version", "1.0.0"),
        blocks=sorted_blocks,
        raw=bp,
    )


def find_blueprint(blueprints_dir: Path, blueprint_id: str) -> Path:
    """Locate a Blueprint YAML by its ID in the blueprints directory.

    Tries: {id}.yaml, then glob for matching files.
    """
    # Direct match: bp_coding_task.1.0.0 → bp_coding_task.1.0.0.yaml
    direct = blueprints_dir / f"{blueprint_id}.yaml"
    if direct.exists():
        return direct

    # Glob fallback
    candidates = list(blueprints_dir.glob(f"{blueprint_id}*.yaml"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"Blueprint '{blueprint_id}' not found in {blueprints_dir}"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_blocks(bp: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk the Blueprint YAML to find the blocks list."""
    workflow = bp.get("workflow", {})
    ralph_loop = workflow.get("ralph_loop", {})
    step_3 = ralph_loop.get("step_3", {})
    dep_graph = step_3.get("dependency_graph", {})
    return dep_graph.get("blocks", [])


def _parse_block(raw: dict[str, Any]) -> Block:
    """Convert a raw YAML block dict into a Block dataclass."""
    validators = [
        Validator(type=v.get("type", ""), params={k: v2 for k, v2 in v.items() if k != "type"})
        for v in raw.get("validators", [])
    ]

    runner_config = raw.get("runner_config", {})
    # Normalize command to string
    if "command" in runner_config and isinstance(runner_config["command"], str):
        runner_config["command"] = runner_config["command"].strip()

    return Block(
        block_id=raw.get("block_id", ""),
        name=raw.get("name", ""),
        assigned_to=raw.get("assigned_to", ""),
        dependencies=raw.get("dependencies", []),
        runner=raw.get("runner", "claude_cli"),
        runner_config=runner_config,
        timeout=int(raw.get("timeout", 300)),
        max_retries=int(raw.get("max_retries", 1)),
        prompt_template=raw.get("prompt_template", ""),
        output=raw.get("output", ""),
        validators=validators,
        acceptance_criteria=raw.get("acceptance_criteria", []),
        pre_check=raw.get("pre_check", ""),
        raw=raw,
    )


def _topological_sort(blocks: list[Block]) -> list[Block]:
    """Sort blocks by dependency order (Kahn's algorithm)."""
    block_map = {b.block_id: b for b in blocks}
    in_degree: dict[str, int] = {b.block_id: 0 for b in blocks}
    adj: dict[str, list[str]] = {b.block_id: [] for b in blocks}

    for block in blocks:
        for dep in block.dependencies:
            if dep in adj:
                adj[dep].append(block.block_id)
                in_degree[block.block_id] += 1

    queue = [bid for bid, deg in in_degree.items() if deg == 0]
    result: list[Block] = []

    while queue:
        bid = queue.pop(0)
        result.append(block_map[bid])
        for neighbor in adj[bid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(blocks):
        raise ValueError("Circular dependency detected in Blueprint blocks")

    return result
