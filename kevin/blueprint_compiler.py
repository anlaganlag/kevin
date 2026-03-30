"""Compile Blueprint YAML into a structured Executor Prompt.

Extracts semantic information (goal, criteria, constraints, context) from
a Blueprint and compiles it into a ~2-4KB prompt that an agentic executor
(Claude CLI) can autonomously follow to completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kevin.prompt_template import render
from kevin.workers.interface import WorkerPermissions, WorkerTask, WorkspacePolicy


@dataclass(frozen=True)
class SemanticBlueprint:
    """Blueprint content organized by semantic purpose, not execution mechanics."""

    blueprint_id: str
    blueprint_name: str
    goal: str
    acceptance_criteria: list[str]
    constraints: list[str]
    context_sources: list[str]
    sub_agents: list[dict[str, Any]]
    verification_commands: list[str]
    workflow_steps: list[str]
    artifacts: list[str]
    task_timeout: int
    raw: dict[str, Any]


def load_semantic(bp_path: Path) -> SemanticBlueprint:
    """Load Blueprint YAML and extract semantic sections.

    Walks the YAML structure to extract goal, acceptance criteria,
    constraints, sub-agents, verification commands, and workflow steps.
    Block execution details (runner, dependencies, timeout per block)
    are intentionally discarded — the agentic executor decides its own approach.
    """
    with bp_path.open() as f:
        data = yaml.safe_load(f)

    bp = data.get("blueprint", data)
    metadata = bp.get("metadata", {})
    configuration = bp.get("configuration", {})
    input_sec = bp.get("input", {})
    execution = bp.get("execution", {})
    completion = bp.get("completion", {})
    config = bp.get("config", {})
    blocks = _extract_blocks_raw(bp)

    return SemanticBlueprint(
        blueprint_id=metadata.get("blueprint_id", ""),
        blueprint_name=metadata.get("blueprint_name", ""),
        goal=_extract_goal(metadata, execution),
        acceptance_criteria=_extract_acceptance_criteria(blocks, completion),
        constraints=_extract_constraints(configuration),
        context_sources=_extract_context_sources(input_sec),
        sub_agents=_extract_sub_agents(execution),
        verification_commands=_extract_verification_commands(blocks),
        workflow_steps=_extract_workflow_steps(blocks),
        artifacts=_extract_artifacts(completion),
        task_timeout=_extract_timeout(blocks, config),
        raw=bp,
    )


def compile(semantic: SemanticBlueprint, variables: dict[str, str]) -> str:
    """Compile a SemanticBlueprint into an Executor Prompt string.

    The prompt is structured for autonomous execution by Claude CLI.
    Variables (issue_number, issue_title, etc.) are rendered into the output.
    """
    sections: list[str] = []

    # Role
    sections.append(
        "You are Kevin Executor, an autonomous software development agent.\n"
        "Complete the following task end-to-end. You have full tool access "
        "(Read, Write, Edit, Bash, Glob, Grep).\n"
        "You MUST create files and execute commands. Do NOT ask questions or wait "
        "for confirmation. Just execute."
    )

    # Goal
    goal = render(semantic.goal, variables)
    sections.append(f"# GOAL\n\n{goal}")

    # Task (issue context)
    issue_number = variables.get("issue_number", "")
    issue_title = variables.get("issue_title", "")
    issue_body = variables.get("issue_body", "")
    if issue_number and issue_title:
        task_lines = [f"# TASK\n\n## Issue #{issue_number}: {issue_title}"]
        if issue_body:
            task_lines.append(issue_body)
        sections.append("\n\n".join(task_lines))

    # Historical context (from Learning Agent)
    learning = variables.get("learning_context", "")
    if learning:
        sections.append(f"# HISTORICAL CONTEXT\n\n{learning}")

    # Constraints
    if semantic.constraints:
        constraint_lines = "\n".join(f"- {c}" for c in semantic.constraints)
        sections.append(f"# CONSTRAINTS\n\n{constraint_lines}")

    # Sub-agents
    if semantic.sub_agents:
        agent_lines: list[str] = []
        for sa in semantic.sub_agents:
            role = sa.get("role", sa.get("agent_type", ""))
            responsibilities = sa.get("responsibilities", [])
            resp_str = ", ".join(responsibilities) if responsibilities else ""
            agent_lines.append(f"- **{role}**: {resp_str}")
        sections.append(
            "# AVAILABLE SUB-AGENTS\n\n"
            "You may invoke these specialists by including their perspective in your work:\n"
            + "\n".join(agent_lines)
        )

    # Acceptance criteria
    if semantic.acceptance_criteria:
        criteria_lines = "\n".join(f"- [ ] {c}" for c in semantic.acceptance_criteria)
        sections.append(
            f"# ACCEPTANCE CRITERIA\n\n"
            f"Your work is complete ONLY when ALL of these are true:\n{criteria_lines}"
        )

    # Workflow guidance
    if semantic.workflow_steps:
        step_lines = "\n".join(
            f"{i}. {s}" for i, s in enumerate(semantic.workflow_steps, 1)
        )
        sections.append(
            f"# WORKFLOW GUIDANCE\n\n"
            f"Suggested approach (adapt as needed):\n{step_lines}"
        )

    # Verification
    if semantic.verification_commands:
        verify_lines = "\n".join(f"- {v}" for v in semantic.verification_commands)
        sections.append(
            f"# VERIFICATION\n\n"
            f"Before declaring completion, verify:\n{verify_lines}"
        )

    # Artifacts
    if semantic.artifacts:
        artifact_lines = "\n".join(f"- {a}" for a in semantic.artifacts)
        sections.append(f"# EXPECTED ARTIFACTS\n\n{artifact_lines}")

    prompt = render("\n\n---\n\n".join(sections), variables)
    return prompt


def compile_task(
    semantic: SemanticBlueprint,
    variables: dict[str, str],
    *,
    task_id: str,
    cwd: Path,
) -> WorkerTask:
    """Compile Blueprint into a WorkerTask — runtime-agnostic.

    The instruction field contains the structured task description
    (goal, criteria, constraints). No runtime-specific framing.
    Each Worker adapter adds its own framing in translate().
    """
    instruction = compile(semantic, variables)

    # Extract context_filter from blocks if present
    blocks = _extract_blocks_raw(semantic.raw)
    context_filter: list[str] = []
    for block in blocks:
        cf = block.get("runner_config", {}).get("context_filter", [])
        context_filter.extend(f for f in cf if f not in context_filter)

    return WorkerTask(
        task_id=task_id,
        instruction=instruction,
        workspace=WorkspacePolicy(
            cwd=cwd,
            context_filter=context_filter,
        ),
        permissions=WorkerPermissions(
            git_write=True,
            git_push=True,
        ),
        timeout=semantic.task_timeout,
        metadata={
            "blueprint_id": semantic.blueprint_id,
            "issue_number": variables.get("issue_number", ""),
        },
    )


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_blocks_raw(bp: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk Blueprint YAML to find the blocks list."""
    workflow = bp.get("workflow", {})
    ralph_loop = workflow.get("ralph_loop", {})
    step_3 = ralph_loop.get("step_3", {})
    dep_graph = step_3.get("dependency_graph", {})
    return dep_graph.get("blocks", [])


def _extract_goal(
    metadata: dict[str, Any], execution: dict[str, Any]
) -> str:
    """Synthesize goal from metadata and execution sections."""
    name = metadata.get("blueprint_name", "")
    primary = execution.get("primary_agent", {})
    responsibilities = primary.get("responsibilities", [])
    if responsibilities:
        resp_str = "; ".join(responsibilities)
        return f"{name}: {resp_str}"
    return name


def _extract_acceptance_criteria(
    blocks: list[dict[str, Any]], completion: dict[str, Any]
) -> list[str]:
    """Merge block-level and completion-level acceptance criteria."""
    criteria: list[str] = []
    seen: set[str] = set()

    # Block-level criteria
    for block in blocks:
        for c in block.get("acceptance_criteria", []):
            normalized = c.strip()
            if normalized and normalized not in seen:
                criteria.append(normalized)
                seen.add(normalized)

    # Completion-level criteria (can be nested dict or list)
    completion_ac = completion.get("acceptance_criteria", {})
    if isinstance(completion_ac, dict):
        for _category, items in completion_ac.items():
            if isinstance(items, list):
                for c in items:
                    normalized = c.strip()
                    if normalized and normalized not in seen:
                        criteria.append(normalized)
                        seen.add(normalized)
    elif isinstance(completion_ac, list):
        for c in completion_ac:
            normalized = c.strip()
            if normalized and normalized not in seen:
                criteria.append(normalized)
                seen.add(normalized)

    return criteria


def _extract_constraints(configuration: dict[str, Any]) -> list[str]:
    """Extract rules and constraints from configuration section."""
    constraints: list[str] = []

    # Inline custom rules (can be {custom_rules: [...]} or directly [...])
    rules = configuration.get("rules", {})
    inline = rules.get("inline", {})
    custom_rules: list[dict[str, Any]] = []
    if isinstance(inline, dict):
        custom_rules = inline.get("custom_rules", [])
    elif isinstance(inline, list):
        custom_rules = inline
    for rule in custom_rules:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name", "")
        rule_text = rule.get("rule", "")
        if rule_text:
            rule_text = rule_text.strip().replace("\n", " ")
            constraints.append(f"{name}: {rule_text}" if name else rule_text)

    # Inline constraints (flatten nested dicts)
    constraint_sec = configuration.get("constraints", {})
    inline_constraints = constraint_sec.get("inline", {})
    _flatten_constraints(inline_constraints, constraints)

    # Rules load_from paths (as reference, not executable)
    load_from = rules.get("load_from", [])
    if load_from:
        paths_str = ", ".join(load_from)
        constraints.append(f"Follow rules defined in: {paths_str}")

    return constraints


def _flatten_constraints(
    obj: Any, result: list[str], prefix: str = ""
) -> None:
    """Recursively flatten nested constraint dicts into readable strings."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                _flatten_constraints(value, result, new_prefix)
            else:
                result.append(f"{new_prefix}: {value}")
    elif isinstance(obj, list):
        for item in obj:
            _flatten_constraints(item, result, prefix)


def _extract_context_sources(input_sec: dict[str, Any]) -> list[str]:
    """Extract context source descriptions from input section."""
    sources: list[str] = []
    context = input_sec.get("context", {})
    for doc in context.get("source_documents", []):
        desc = doc.get("description", doc.get("type", ""))
        if desc:
            sources.append(desc)
    for ds in context.get("data_sources", []):
        if isinstance(ds, str):
            sources.append(ds)
    return sources


def _extract_sub_agents(execution: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract sub-agent definitions from execution section."""
    return execution.get("sub_agents", [])


def _extract_verification_commands(blocks: list[dict[str, Any]]) -> list[str]:
    """Convert block validators into human-readable verification steps."""
    commands: list[str] = []
    seen: set[str] = set()

    for block in blocks:
        for v in block.get("validators", []):
            v_type = v.get("type", "")
            cmd_str = ""
            if v_type == "git_diff_check":
                cmd_str = "Verify: git has changes compared to main branch"
            elif v_type == "command":
                run_cmd = v.get("run", "")
                if run_cmd:
                    cmd_str = f"Run: {run_cmd}"
            elif v_type == "file_exists":
                path = v.get("path", "")
                if path:
                    cmd_str = f"Verify file exists: {path}"

            if cmd_str and cmd_str not in seen:
                commands.append(cmd_str)
                seen.add(cmd_str)

    return commands


def _extract_workflow_steps(blocks: list[dict[str, Any]]) -> list[str]:
    """Extract actionable workflow steps from block prompt_templates.

    For claude_cli blocks: extracts the Instructions section from prompt_template.
    For shell blocks: extracts the key operations from the command.
    Falls back to acceptance criteria if no instructions found.
    """
    steps: list[str] = []
    for block in blocks:
        name = block.get("name", block.get("block_id", ""))
        runner = block.get("runner", "claude_cli")
        prompt = block.get("prompt_template", "")

        if runner == "shell":
            steps.append(_summarize_shell_block(name, block))
            continue

        # For claude_cli blocks: extract Instructions section from prompt
        instructions = _extract_instructions_from_prompt(prompt)
        if instructions:
            steps.append(f"**{name}**:\n{instructions}")
        else:
            # Fallback to acceptance criteria
            criteria = block.get("acceptance_criteria", [])
            if criteria:
                criteria_summary = "; ".join(criteria[:2])
                steps.append(f"**{name}**: {criteria_summary}")
            else:
                steps.append(name)

    return steps


def _extract_instructions_from_prompt(prompt: str) -> str:
    """Extract the Instructions/steps section from a block prompt_template.

    Looks for '## Instructions' or numbered steps, returns them as-is.
    """
    if not prompt:
        return ""

    lines = prompt.strip().split("\n")
    instructions: list[str] = []
    capturing = False

    for line in lines:
        stripped = line.strip()

        # Start capturing at "## Instructions" or similar headers
        if stripped.lower().startswith("## instructions") or stripped.lower().startswith("## steps"):
            capturing = True
            continue

        # Stop capturing at next header (## Something else)
        if capturing and stripped.startswith("## "):
            break

        # Also capture numbered steps even without a header
        if not capturing and stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            capturing = True

        if capturing and stripped:
            instructions.append(stripped)

    # If no Instructions section found, look for IMPORTANT/MUST lines
    if not instructions:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("IMPORTANT:") or "You MUST" in stripped:
                instructions.append(stripped)

    return "\n".join(instructions)


def _summarize_shell_block(name: str, block: dict[str, Any]) -> str:
    """Summarize a shell block into actionable steps."""
    cmd = block.get("runner_config", {}).get("command", "")
    if not cmd:
        return name

    # Extract key operations from shell script
    operations: list[str] = []
    for line in cmd.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Capture git and gh commands
        if line.startswith("git ") or line.startswith("gh "):
            # Simplify: take the command + first few args
            parts = line.split()
            simplified = " ".join(parts[:4])
            if simplified not in operations:
                operations.append(simplified)

    if operations:
        ops_str = "; ".join(operations[:5])
        return f"**{name}**: {ops_str}"

    # Fallback to criteria
    criteria = block.get("acceptance_criteria", [])
    if criteria:
        return f"**{name}**: {'; '.join(criteria[:2])}"
    return name


def _extract_artifacts(completion: dict[str, Any]) -> list[str]:
    """Extract artifact descriptions from completion section."""
    artifacts: list[str] = []
    artifacts_sec = completion.get("artifacts", {})

    for category in ("code_artifacts", "report_artifacts", "requirement_artifacts"):
        for item in artifacts_sec.get(category, []):
            name = item.get("name", "")
            location = item.get("storage_location", "")
            if name:
                artifacts.append(f"{name} ({location})" if location else name)

    return artifacts


def _extract_timeout(
    blocks: list[dict[str, Any]], config: dict[str, Any]
) -> int:
    """Compute task-level timeout from blocks or config."""
    # Prefer explicit blueprint timeout from config
    timeouts = config.get("timeouts", {})
    bp_timeout_raw = timeouts.get("blueprint_timeout", "")
    if bp_timeout_raw:
        try:
            return _parse_timeout(str(bp_timeout_raw))
        except ValueError:
            pass

    # Fallback: sum of all block timeouts
    total = sum(int(b.get("timeout", 300)) for b in blocks)
    return max(total, 600)  # minimum 10 minutes


def _parse_timeout(value: str) -> int:
    """Parse timeout string like '35m', '1h', '600' into seconds."""
    value = value.strip().lower()
    if value.endswith("m"):
        return int(value[:-1]) * 60
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    return int(value)
