# Quality Assessment (QA) Agent

## Role Overview
The **QA Agent** performs continuous and adversarial testing on new code submissions. It is designed to act independently from the Builder Agent to ensure separation of duties, aggressively assessing edge cases, logic flaws, and breaking changes.

Its distinguishing capability is the use of an RL-style test environment as a controlled exploration sandbox. In that sandbox, the QA function can observe application state, attempt candidate action sequences, and retain the highest-value failure trajectories as reusable regression assets.

## System Trigger
Triggered by a continuous integration (CI) webhook whenever a Builder Agent pushes new commits to an open Pull Request or opens a new one.

## Core Sub-Components

### 1. Environment Setup (RL Env) & Data Management
The QA Agent orchestrates the creation of isolated, ephemeral test environments tailored to the changes in the Pull Request.
- **RL-Driven Exploration**: Utilizes Reinforcement Learning (RL) agents to explore the application's state space. These agents "play" with the new features to discover undocumented side effects or deep-logic bugs that static tests might miss.
- **Conceptual RL Model**: Treats application and test-environment conditions as state, candidate test moves as actions, bug discovery or invariant violations as rewards, and full test trajectories as reusable episode history.
- **Synthetic Data Generation**: Automatically generates high-fidelity, anonymized, or synthetic datasets to simulate realistic production loads and edge cases (e.g., boundary values, malformed inputs).
- **Infrastructure-as-Code (IaC) Integration**: Works with the Platform Agent to spin up mirrored staging environments (containers, serverless functions) that exactly match the PR's infrastructure requirements.
- **Bounded Exploration**: Runs the RL environment within explicit compute, time, and safety limits so exploratory testing does not become an uncontrolled cost or risk surface.

### 2. Test Execution Engine
A multi-layered execution framework that selects and runs the most relevant tests based on the code diff.
- **Dynamic Test Generation**: Uses LLMs to write new integration and unit tests on-the-fly that specifically target the logic changed in the PR.
- **Automated Regression**: Executes the existing global test suite to ensure no breaking changes were introduced to unrelated modules.
- **Trajectory Search**: Uses RL-style exploration to search unusual state transitions and edge-case sequences that deterministic scripts would be unlikely to enumerate exhaustively.
- **Multi-Framework Support**: Supports broad automation tooling including:
  - **Web/UI**: Playwright, Selenium, or Cypress for end-to-end flows.
  - **API/Backend**: Pytest, Mocha, or Jest for unit and integration logic.
  - **Performance**: k6 or JMeter for load and latency verification.
- **Adversarial Fuzzing**: Runs high-frequency random input testing to trigger crashes or memory leaks.

### 3. Test Reporting & Feedback Loop
Converts raw execution logs into actionable intelligence for both humans and other agents.
- **Machine-Readable Reports**: Generates JSON/XML reports consumed by the Governance Layer to enforce quality gates (e.g., "Coverage < 95%").
- **Agentic Feedback**: Posts detailed comments on the GitHub PR, including:
  - Snippets of failing code.
  - Tracebacks and environment logs.
  - Suggested fixes or "repro" steps for the Builder Agent to iterate on.
- **Knowledge Ingestion**: Feeds hard-to-find edge cases, reproducible failure trajectories, and high-value test sequences back to the Learning Agent to update the project's global avoidance and regression knowledge.

## Inputs (from Single Source of Truth)
- **Code Diff**: The specific changes proposed in the Builder Agent's Pull Request.
- **API Contracts & Blueprint**: The original design constraints set by the Planning Agent (to verify the code actually solves the requested problem).
- **Existing Test Suite**: The `main` branch test files.

## Outputs (to Single Source of Truth)
- **Dynamic Test Files**: Auto-generated test files committed to the PR branch, covering integration and edge-case scenarios targeting the new code logic.
- **CI Report**: A structured pass/fail report (JSON/XML) persisted as a CI artifact, consumed by the Governance Layer for policy gate enforcement.
- **PR Status Check**: Posts a pass/fail status check directly on the GitHub PR. On failure, the agent either commits the new failing test file to the branch or posts a structured comment with tracebacks, failure logs, and suggested repro steps.
- **Exploration Artifacts**: Records useful RL-environment trajectories, state/action patterns, and repro sequences as CI artifacts or structured knowledge inputs for future reuse.

## Interaction with Other Agents
- **Builder Agent**: Feeds failure context back into the Execution loop, forcing the Builder to iterate and debug.
- **Learning Agent**: Logs successfully discovered edge cases, failure trajectories, and useful exploration policies so future Builder Agents avoid the same bugs.
- **Governance Layer**: Consumes QA evidence for coverage, process, and quality gates. The Governance Layer can block progression, but it does not direct how QA performs exploration.
