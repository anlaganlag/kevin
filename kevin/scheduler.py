"""Wave-based parallel scheduler for Blueprint Blocks.

Groups Blocks by dependency level, then splits within each level
by resolved cwd to prevent parallel Blocks from writing the same directory.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from kevin.blueprint_loader import Block
from kevin.utils import resolve_cwd


@dataclass(frozen=True)
class Wave:
    """A group of Blocks that can execute concurrently."""

    index: int
    subindex: int
    blocks: tuple[Block, ...]

    @property
    def label(self) -> str:
        return f"Wave {self.index + 1}.{self.subindex}"


def compute_waves(blocks: list[Block], variables: dict[str, str]) -> list[Wave]:
    """Compute execution waves from a topologically sorted Block list.

    Algorithm:
    1. Compute level for each block:
       level[b] = 0 if no dependencies
       level[b] = 1 + max(level[dep] for dep in b.dependencies)
    2. Group blocks by level
    3. Within each level, split by resolved cwd conflict
    4. Return flat list of Wave objects in execution order
    """
    if not blocks:
        return []

    block_map = {b.block_id: b for b in blocks}
    levels: dict[str, int] = {}
    for block in blocks:
        _compute_level(block.block_id, block_map, levels)

    level_groups: dict[int, list[Block]] = defaultdict(list)
    for block in blocks:
        level_groups[levels[block.block_id]].append(block)

    waves: list[Wave] = []
    for level_idx in sorted(level_groups.keys()):
        group = level_groups[level_idx]
        sub_waves = _split_by_cwd(group, variables)
        for sub_idx, sub_blocks in enumerate(sub_waves, start=1):
            waves.append(
                Wave(index=level_idx, subindex=sub_idx, blocks=tuple(sub_blocks))
            )

    return waves


def _compute_level(
    block_id: str,
    block_map: dict[str, Block],
    levels: dict[str, int],
    _visiting: frozenset[str] = frozenset(),
) -> int:
    """Recursively compute the dependency level for a block."""
    if block_id in levels:
        return levels[block_id]
    if block_id in _visiting:
        raise ValueError(f"Cyclic dependency detected: {block_id}")
    block = block_map[block_id]
    if not block.dependencies:
        levels[block_id] = 0
        return 0
    next_visiting = _visiting | {block_id}
    dep_levels = [
        _compute_level(dep, block_map, levels, next_visiting)
        for dep in block.dependencies
        if dep in block_map
    ]
    level = 1 + max(dep_levels) if dep_levels else 0
    levels[block_id] = level
    return level


def _split_by_cwd(
    blocks: list[Block], variables: dict[str, str]
) -> list[list[Block]]:
    """Split blocks into sub-waves where no two blocks share the same resolved cwd."""
    if len(blocks) <= 1:
        return [blocks]

    sub_waves: list[list[Block]] = [[]]
    cwd_sets: list[set[str]] = [set()]

    for block in blocks:
        resolved = str(resolve_cwd(block.runner_config, variables))
        placed = False
        for i, cwd_set in enumerate(cwd_sets):
            if resolved not in cwd_set:
                cwd_set.add(resolved)
                sub_waves[i].append(block)
                placed = True
                break
        if not placed:
            cwd_sets.append({resolved})
            sub_waves.append([block])

    return [sw for sw in sub_waves if sw]
