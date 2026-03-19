# Business Analyst (BA) Agent

## Role Overview
The **Business Analyst (BA) Agent** acts as the Requirements Engineer. Its primary function is to bridge the gap between unstructured human intent and the highly structured technical requirements needed by the rest of the Agentic SDLC pipeline.

## System Trigger
Invoked manually by a Human Orchestrator via a direct chat interface, an issue tracker comment, or a draft Pull Request containing raw ideas.

## Inputs (from Single Source of Truth)
- **Raw User Input**: Unstructured text, high-level feature requests, or vague business goals submitted via Git Issues or draft PR descriptions.
- **Project Context**: Existing repository documentation to understand the current product domain and system vocabulary.
- **Historical Context**: (Via the **Learning Agent**) Past feature requests, requirement gaps, and known pitfalls from previous requirement cycles stored in the knowledge base.

## Outputs (to Single Source of Truth)
- **Structured Artifacts**: Epics, Features, User Stories, Acceptance Criteria (BDD format like Gherkin), or Business Requirement Documents (BRDs).
- **Git Action**: Commits requirements to a designated `/requirements` folder and creates or updates the repository Issues/Epics that initiate the lifecycle. Any GitHub Project usage is a coordination view derived from those repository artifacts.
- **Handoff**: Tags the Planning Agent to begin blueprinting based on the newly merged requirements.

## Interaction with Other Agents
- **Human Orchestrator**: Clarifies intent through back-and-forth Q&A if the initial Git Issue description is too vague.
- **Learning Agent**: Queries for past requirement gaps or misalignments before finalizing the BRD to prevent known failure modes from repeating.
- **Planning Agent**: Provides the foundational requirements that the Planner will turn into technical architecture (`task.md`).
