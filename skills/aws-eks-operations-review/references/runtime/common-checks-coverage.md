# Common-check coverage (review-common baseline)

The shared **`review-common`** skill defines a small set of checks that apply to **every** AWS
service (tagging, encryption, IAM least-privilege, alarms, logging, cost). An EKS operations review
must cover that baseline too. This file is the **crosswalk**: it maps each `review-common` common
check to the EKS check(s) that already satisfy it, so the coverage gate can confirm the baseline is
met without adding a parallel check set.

The EKS review keeps its own richer check IDs (Op*, S*, SM*, O*, OM*, A*, AX*, …); it does **not**
renumber to the common `C*` IDs. This table shows the mapping. When a common check maps to an
AWS-API-only fact, it is graded by the AWS-API component (AX-series) and stays ⚪ N/A in kubectl-only
mode (flagged for follow-up) — same as every other AWS-API check.

## Crosswalk

| Common check (review-common) | Baseline severity | Covered by (EKS) | Notes |
|------------------------------|-------------------|------------------|-------|
| **COp1** — Resource tagging (`Environment`, `Owner`, `CostCenter`) | Low | **AX13** (AWS resource tags on cluster/nodegroups/EBS) + **Op5** (in-cluster namespace org labels) | AX13 grades the AWS resource tags the common check means; Op5 is the kubectl-side namespace-label complement. |
| **COp2** — IaC / CloudFormation managed | Low | **Op6** (IaC / GitOps management — ArgoCD/Flux or IaC evident) | Direct match. |
| **CS1** — Encryption at rest (KMS) | High | **SM1 / AX11** (secrets KMS envelope encryption) + **SM4** (EBS/EFS at-rest encryption) | Secrets + persistent-volume encryption together satisfy at-rest. |
| **CS2** — Encryption in transit (TLS) | High | **SM6** (mTLS between workloads) | API-server traffic is TLS by default (EKS-managed); SM6 covers in-cluster workload-to-workload mTLS where required. |
| **CS3** — IAM least privilege (no wildcards) | High | **S11** (no wildcard RBAC) + **SM7** (node IAM least privilege) + **OpM5** (autoscaler IAM) + **AX9** (controller IAM) | RBAC wildcards (in-cluster) and IAM-role scoping (AWS-side) together cover least-privilege. |
| **CO1** — CloudWatch alarms exist | Critical | **O6** (alerting present) + **O21 / AX-none** (recommended-alarm coverage via `describeAlarms`) | O21 enumerates the base recommended alarms and flags which are missing. |
| **CO2** — Logging enabled | High | **O4** (logging pipeline) + **OM1 / AX10** (control-plane log types) + **SM2** (audit logging) | Data-plane log pipeline + control-plane logging together satisfy logging-enabled. |
| **CA1** — Cost optimization review (not over-provisioned / idle) | Low | **A6** (right-sizing signal) + **A13** (HPA/VPA coverage) + **AM3** (node utilization / idle spend) | Right-sizing + idle-capacity review satisfy the cost baseline. |

## How to use during a review

- For a full operations review / CWR, the eight common checks above are **already graded** through
  their EKS equivalents — no separate pass is needed. Cite the EKS check ID as the evidence.
- **COp1 is the only one that needed a dedicated EKS check** (AX13) because AWS resource tags are an
  AWS-API fact that no prior kubectl check covered. Grade AX13 when AWS-API access is available;
  otherwise ⚪ N/A with the `aws eks describe-cluster --query tags` follow-up.
- The report's §5 scorecards use the EKS IDs. If a customer explicitly asks for the CWR common-check
  view, present this crosswalk so they can see each `C*` baseline check maps to a graded EKS check.

## Coverage-gate addition

An EKS operations review / CWR is not complete unless all eight `review-common` baseline checks are
accounted for — either graded via their EKS equivalent above, or ⚪ N/A with a reason (e.g. AX13 in
kubectl-only mode). Confirm this crosswalk is satisfied alongside the pillar coverage gate.
