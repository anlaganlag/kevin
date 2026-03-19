# Security (Red Team) Agent

## Role Overview
The **Security (Red Team) Agent** serves as an autonomous security researcher and auditor. It runs parallel to the QA Agent and focuses strictly on discovering vulnerabilities, enforcing compliance, and independently challenging proposed changes for insecure logic or unsafe infrastructure posture.

## System Trigger
Triggered by a CI webhook alongside the QA Agent whenever new commits are pushed to any active Pull Request.

## Inputs (from Single Source of Truth)
- **Code Diff**: The raw application code changes proposed in the Builder Agent's Pull Request.
- **IaC Manifests**: The Infrastructure as Code changes submitted by the Platform Agent (IAM roles, Security Groups, network configs) — scanned for misconfigured permissions and over-privileged access.
- **Security Policies**: Organization-wide security standards stored in a `.security` configuration folder within the Git repository.
- **Vulnerability Databases**: External CVE streams or internal knowledge bases regarding zero-day exploits.

## Outputs (to Single Source of Truth)
- **Security Analysis Report**: Results of automated SAST (Static Application Security Testing) and DAST (Dynamic Application Security Testing).
- **Git Action**: Posts a security status check to the PR. 
  - If a vulnerability is found (e.g., OWASP Top 10, exposed secrets, SQL injection flaws), the PR is blocked, and the agent annotates the exact lines of code with the vulnerability details in the Git UI.

## Interaction with Other Agents
- **Builder & Platform Agents**: Provides explicit documentation on the vulnerability so the executing agents can fix the code and push a patch.
- **Learning Agent**: Ingests new patterns of vulnerabilities introduced by the Builder to proactively scan for them in future requests.
- **Governance Layer**: A passed security check is a mandatory dependency for the Governance Layer to approve the PR for human review. The Security Agent supplies evidence; it does not replace governance's final progression decision.
