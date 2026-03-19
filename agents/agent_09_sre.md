# SRE & Operations Agent (The Operator)

## Role Overview
The **SRE Agent** is the guardian of production reliability. Following the GitOps model, it manages the deployment of code and infrastructure, monitors system health in real-time, and takes autonomous remedial action if production metrics degrade.

Beyond real-time response, the SRE Agent also contributes to post-incident learning through an RL-style replay environment. That environment is used conceptually to model failure progression, compare recovery choices, and turn incidents into reusable operational guidance rather than static postmortem narratives.

## System Trigger
Triggered by a "Release PR" merging into the `main` branch, or by real-time alerts from the cloud production monitoring suite.

## Inputs (from Single Source of Truth)
- **Main Branch State**: The approved code, configurations, and IaC manifests.
- **Canary Policies**: Defined in a `.reliability` file (e.g., error rate thresholds, latency limits).
- **Production Telemetry**: Real-time streams of logs, traces, and metrics from the runtime environment.
- **Deployment Metadata**: Release identifiers, rollout steps, prior rollback history, and incident timelines needed for replay and postmortem analysis.

## Outputs (to Single Source of Truth)
- **Deployment Status**: Updates the Git repository with the current version hash deployed to production.
- **Rollback Feedback**: If a release is aborted, it writes a detailed RCA log back to the repository.
- **Health Reports**: Continuous summary of production availability and performance.
- **Git Action**: Commits deployment meta-data or triggers a "Git revert" on the `main` branch if an autonomous rollback occurs.
- **Replay Lessons**: Produces structured incident-replay findings describing which recovery strategies, rollback timing, or escalation patterns appeared strongest in the sandboxed postmortem environment.

## Interaction with Other Agents
- **Platform Agent**: Coordinates on the execution of IaC changes during the rollout phase.
- **Learning Agent**: Feeds production rollback RCA, replay-derived lessons, and effective recovery patterns into the knowledge base for future planning and execution.
- **Governance Layer**: Reports on the reliability impact of recent changes and provides runtime evidence for audit trails, but governance still does not replace human judgment during ambiguous incidents.
- **Documentation Agent**: Sends the final "All Clear" health signal that triggers the Doc Agent to update system documentation after a successful deployment.
