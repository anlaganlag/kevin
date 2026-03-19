# Platform Agent (The Infrastructure Engineer)

## Role Overview
The **Platform Agent** is responsible for all Infrastructure as Code (IaC) and system configuration. While the Builder Agent focuses on application logic (Python, TS, Go), the Platform Agent ensures that the cloud infrastructure can support the new feature.

## System Trigger
Triggered by the initial formal Blueprint (created by the Planning Agent) if infrastructure changes are detected, or dynamically if a Builder Agent realizes it needs a new resource (e.g., a Redis cache).

## Inputs (from Single Source of Truth)
- **Technical Blueprint**: Relies purely on the architectural specifications defined by the Planner.
- **Current Infrastructure State**: The existing Terraform state files, Kubernetes manifests, or Helm charts residing in the Git repository.
- **Security & Networking Constraints**: Subnet restrictions, IAM roles, and port policies defined in the repository.

## Outputs (to Single Source of Truth)
- **IaC Manifests**: Generates or modifies Terraform `.tf` files, AWS CloudFormation, or Kubernetes `.yaml` configuration files.
- **Git Action**: Opens an "Infrastructure Pull Request" or pushes commits to a standardized "Platform" sub-module within a feature branch.

## Interaction with Other Agents
- **Planning & Builder Agents**: The Platform agent acts as a dependency block. An application feature cannot deploy to production if the Platform Agent's infrastructure PR hasn't merged.
- **Security Agent**: Its outputs (IAM roles, Security Groups) are heavily scrutinized by the Red Team Agent to prevent leaky buckets or misconfigured permissions.
- **SRE Agent**: The Platform Agent *defines* the infrastructure; the SRE Agent *applies* it during deployment.
