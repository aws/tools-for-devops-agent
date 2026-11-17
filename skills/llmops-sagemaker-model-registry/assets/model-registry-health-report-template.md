# SageMaker Model Registry Governance — Health Report
> Read-only governance review of customized / fine-tuned GenAI artifacts in the SageMaker Model
> Registry: registration, approval, lineage, and package-group boundary.
> Every finding carries an `LLM-SM-REG-*` check-id, a catalog severity, and the observed evidence.
> No package or group was mutated. Account IDs and secret values are redacted.
## Scope
- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Model package groups / customized artifacts reviewed:** `<count and names>`
- **Not covered (disclosed):** `<packages / groups / regions / checks skipped, with reason — permissions, budget, region-unsupported>`
## Registration Coverage (LLM-SM-REG-001)
| Customized artifact (S3 location, account masked) | Source training job | Registered as a model package? |
|---|---|---|
| `<s3://.../model.tar.gz>` | `<training-job name>` | `<yes: group/version / no>` |
## Per-Package State
| Model package group | Version | `ModelApprovalStatus` | Deployed or staged? (resolved, not assumed) | Lineage to training job / dataset? | check-id |
|---|---|---|---|---|---|
| `<group>` | `<n>` | `<Approved / PendingManualApproval / Rejected>` | `<yes: endpoint name / no>` | `<yes / none found>` | `<LLM-SM-REG-002 / 003 as applicable>` |
> An `Approved` package in the group ≠ the deployed version is approved (api-quirks §2). Resolve which
> version is live before clearing a group. A deployed endpoint lacking registry lineage is LLM-SM-011,
> owned by the endpoints skill, not a REG-* finding.
## Group Boundary (LLM-SM-REG-004)
| Model package group | Resource policy | Principals granted (account segment masked) | Artifact S3 location CMK-encrypted? |
|---|---|---|---|
| `<group>` | `<present / absent>` | `<arn:aws:iam::<account>:role/...>` | `<yes / no>` |
## Findings
| check-id | severity | group / package | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-REG-00X` | `<catalog severity>` | `<name/version>` | `<concrete observed value>` | `<exact CLI command>` |
Only findings backed by an observed value appear here (evidence or silence). Registry posture comes
from describe/list calls, not CloudWatch; no datapoints is not a measured zero (api-quirks §1). Each
severity is the catalog severity; a threshold AWS does not publish is marked `workload-specific`.
## Prioritized Recommendations
1. `<HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`
