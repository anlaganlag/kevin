# Documentation Agent (The Technical Writer)

## Role Overview
The **Documentation Agent** acts as an autonomous technical writer, ensuring that system documentation never becomes stale. It creates living documentation that accurately reflects the exact state of the production system.

## System Trigger
Triggered exclusively by a successful production deployment (a merge to the `main` branch and a glowing health report from the SRE Agent).

## Inputs (from Single Source of Truth)
- **Merged Pull Requests**: Reads the diffs and descriptions of all PRs included in the latest release cycle.
- **Source Code**: Analyzes the new function signatures, API endpoints, and database schema changes in the `main` repo.
- **Architectural Blueprints**: The original intent documents written by the Planning Agent.

## Outputs (to Single Source of Truth)
- **API Documentation**: Auto-updates Swagger, OpenAPI specifications, or GraphQL schemas.
- **Architecture Diagrams**: Uses tools like Mermaid.js to update system flow diagrams reflecting the new actual state.
- **Release Notes / Changelog**: Summarizes the business value and technical changes for stakeholders.
- **Git Action**: Commits these documentation updates directly into the `main` branch (in a `/docs` folder) or a paired Wiki repository.

## Interaction with Other Agents
- **Human Stakeholders / BA Agent**: Provides the human-readable summary of what the Builder agents actually accomplished in the sprint.
- **Planning Agent**: Keeps the "Current System State" documentation perfectly accurate, which the Planner relies on for future blueprints.
