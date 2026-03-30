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
    workflow = bp.get("workflow", {})
    blocks = _extract_blocks_raw(bp)

    return SemanticBlueprint(
        blueprint_id=metadata.get("blueprint_id", ""),
        blueprint_name=metadata.get("blueprint_name", ""),
        goal=_extract_goal(metadata, execution, workflow),
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


@dataclass(frozen=True)
class BlueprintValidation:
    """Result of validating a blueprint for agentic execution."""

    valid: bool
    warnings: list[str]
    blueprint_id: str
    prompt_chars: int
    criteria_count: int
    step_count: int


def validate_for_execution(semantic: SemanticBlueprint) -> BlueprintValidation:
    """Check if a SemanticBlueprint has enough content for agentic execution.

    Returns validation result with warnings for thin/empty sections.
    A blueprint is invalid only if it has no goal AND no criteria AND no steps.
    """
    warnings: list[str] = []

    if not semantic.goal or semantic.goal == semantic.blueprint_name:
        warnings.append("goal: no actionable goal extracted (only blueprint name)")
    if not semantic.acceptance_criteria:
        warnings.append("criteria: no acceptance criteria found")
    if not semantic.workflow_steps:
        warnings.append("steps: no workflow steps extracted")
    if not semantic.constraints:
        warnings.append("constraints: no constraints found")
    if not semantic.verification_commands:
        warnings.append("verification: no verification commands found")

    has_substance = bool(
        semantic.acceptance_criteria or semantic.workflow_steps
    )
    has_goal = bool(semantic.goal and semantic.goal != semantic.blueprint_name)
    valid = has_goal or has_substance

    # Estimate prompt size
    test_vars = {"issue_number": "0", "issue_title": "test", "issue_body": ""}
    try:
        prompt = compile(semantic, test_vars)
        prompt_chars = len(prompt)
    except Exception:
        prompt_chars = 0
        warnings.append("compile: failed to compile prompt")
        valid = False

    return BlueprintValidation(
        valid=valid,
        warnings=warnings,
        blueprint_id=semantic.blueprint_id,
        prompt_chars=prompt_chars,
        criteria_count=len(semantic.acceptance_criteria),
        step_count=len(semantic.workflow_steps),
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
    metadata: dict[str, Any],
    execution: dict[str, Any],
    workflow: dict[str, Any] | None = None,
) -> str:
    """Synthesize goal from metadata, execution, and workflow sections.

    Tries (in order): execution.primary_agent.responsibilities,
    workflow.ralph_loop.step_3.description, then falls back to blueprint_name.
    """
    name = metadata.get("blueprint_name", "")
    primary = execution.get("primary_agent", {})
    responsibilities = primary.get("responsibilities", [])
    if responsibilities:
        resp_str = "; ".join(responsibilities)
        return f"{name}: {resp_str}"

    # Fallback: workflow step_3 description (common in design-spec blueprints)
    if workflow:
        step_3 = workflow.get("ralph_loop", {}).get("step_3", {})
        description = step_3.get("description", "").strip()
        if description:
            return f"{name}: {description}"

    return name


def _extract_acceptance_criteria(
    blocks: list[dict[str, Any]], completion: dict[str, Any]
) -> list[str]:
    """Merge block-level and completion-level acceptance criteria."""
    criteria: list[str] = []
    seen: set[str] = set()

    # Block-level criteria (acceptance_criteria + success_criteria)
    for block in blocks:
        for key in ("acceptance_criteria", "success_criteria"):
            for c in block.get(key, []):
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
    """Extract actionable workflow steps from blocks.

    Handles two block patterns:
    1. Execution-ready blocks: have runner + prompt_template → extract Instructions section.
    2. Design-spec blocks: have skills + output (no prompt_template) → synthesize from metadata.

    For shell blocks: extracts key operations from the command.
    """
    steps: list[str] = []
    for block in blocks:
        name = block.get("name", block.get("block_id", ""))
        runner = block.get("runner", "claude_cli")
        prompt = block.get("prompt_template", "")

        if runner == "shell":
            steps.append(_summarize_shell_block(name, block))
            continue

        # Path 1: execution-ready blocks with prompt_template
        instructions = _extract_instructions_from_prompt(prompt)
        if instructions:
            steps.append(f"**{name}**:\n{instructions}")
            continue

        # Path 2: design-spec blocks — synthesize from skills/output/criteria
        summary = _summarize_design_spec_block(name, block)
        if summary:
            steps.append(summary)
            continue

        # Path 3: bare minimum fallback
        criteria = block.get("acceptance_criteria", [])
        if criteria:
            criteria_summary = "; ".join(criteria[:2])
            steps.append(f"**{name}**: {criteria_summary}")
        else:
            steps.append(name)

    return steps


def _summarize_design_spec_block(name: str, block: dict[str, Any]) -> str:
    """Synthesize a workflow step from a design-spec block (skills + output pattern).

    Design-spec blocks lack prompt_template but carry rich metadata:
    skills, output, assigned_to, success_criteria, environments, etc.
    """
    parts: list[str] = []

    # Agent assignment provides role context
    assigned_to = block.get("assigned_to", "")
    if assigned_to:
        parts.append(f"Agent: {assigned_to}")

    # Skills describe capabilities needed
    skills: list[str] = block.get("skills", [])
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    # Output describes the expected deliverable
    output = block.get("output", "")
    if output:
        parts.append(f"Deliverable: {output}")

    # success_criteria provides pass/fail conditions
    success_criteria: list[str] = block.get("success_criteria", [])
    if success_criteria:
        parts.append(f"Success: {'; '.join(success_criteria[:3])}")

    if not parts:
        return ""

    return f"**{name}**:\n" + "\n".join(f"  - {p}" for p in parts)


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
