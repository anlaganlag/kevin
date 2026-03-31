# Blueprint Versioning — Implementation Tasks

> Parent Issue: #70
> Architecture: [blueprint_versioning.md](blueprint_versioning.md)
> API Spec: [blueprint_versioning_openapi.yaml](blueprint_versioning_openapi.yaml)

## Wave 1: Core Infrastructure (P0)

### T1: Implement `VersionedBlueprintLoader`
- **Module**: `kevin/blueprint_loader.py`
- **Description**: Extend `find_blueprint()` with SemVer-aware resolution: parse version from filename, sort candidates by version descending, filter deprecated/prerelease, select latest stable.
- **Dependencies**: None
- **Acceptance**: `find_blueprint("bp_coding_task")` returns highest stable version when multiple exist.

### T2: Add version lifecycle metadata fields
- **Module**: `kevin/blueprint_loader.py` (Blueprint dataclass), blueprint YAML schema
- **Description**: Add `status`, `sunset_date`, `superseded_by`, `min_kevin_version`, `deprecation_notice` to Blueprint metadata. Default `status` to `"stable"` for backward compat.
- **Dependencies**: None
- **Acceptance**: Existing blueprints load without changes; new fields parsed when present.

## Wave 2: CLI Commands (P1)

### T3: `kevin blueprint list` and `kevin blueprint versions`
- **Module**: `kevin/cli.py`
- **Description**: Add subcommands to list blueprints (grouped by base ID with latest version) and list all versions for a specific blueprint.
- **Dependencies**: T1
- **Acceptance**: Output matches expected format; `--all` flag shows deprecated/prerelease.

### T4: `kevin blueprint diff`
- **Module**: `kevin/blueprint_diff.py` (new)
- **Description**: YAML structural diff between two blueprint versions. Identify added/removed/modified blocks, changed runners, removed template variables. Output breaking change summary.
- **Dependencies**: T1
- **Acceptance**: Correctly detects block removal as breaking, timeout change as non-breaking.

### T5: `kevin blueprint validate`
- **Module**: `kevin/cli.py`, `kevin/blueprint_loader.py`
- **Description**: Validate YAML structure, required fields, and optionally compare with previous version for breaking changes.
- **Dependencies**: T1, T2
- **Acceptance**: Invalid YAML returns errors; breaking changes detected and reported.

### T8: Deprecation warnings in `kevin run`
- **Module**: `kevin/cli.py`, `kevin/agent_runner.py`
- **Description**: When loading a deprecated blueprint, emit a warning with sunset date and migration pointer.
- **Dependencies**: T2
- **Acceptance**: Warning printed to stderr; run proceeds normally.

## Wave 3: Tooling and CI (P2)

### T6: `kevin blueprint deprecate` command
- **Module**: `kevin/cli.py`
- **Description**: Set `status: deprecated` and `sunset_date` in blueprint metadata YAML.
- **Dependencies**: T2
- **Acceptance**: YAML file updated in-place; `kevin blueprint list` reflects change.

### T7: Auto-generate `blueprints/index.yaml`
- **Module**: `kevin/cli.py` or pre-commit hook
- **Description**: Scan `blueprints/` directory, build version index YAML with latest_stable pointers.
- **Dependencies**: T1
- **Acceptance**: `index.yaml` generated correctly; regenerates on blueprint changes.

### T9: CI breaking change detection
- **Module**: `.github/workflows/` (new or existing)
- **Description**: On PR that modifies `blueprints/*.yaml`, run `kevin blueprint diff` against main branch and comment results.
- **Dependencies**: T5
- **Acceptance**: PR comment shows breaking/non-breaking change summary.

### T10: Migration guide template
- **Module**: `docs/migration/` (new directory), template file
- **Description**: Create migration guide template and example for MAJOR version bumps.
- **Dependencies**: None
- **Acceptance**: Template exists; example guide covers breaking changes, steps, rollback.
