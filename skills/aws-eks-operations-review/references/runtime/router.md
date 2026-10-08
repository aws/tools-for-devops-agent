# Runtime router

Load only in S5. Discovery always attempts all 49 areas; routing selects grading units and extra evidence, never a reduced sweep. Canonical definitions own predicates; [`check-manifest.md`](check-manifest.md) owns membership.

| Unit | Canonical definition | Primary discovery evidence | Additional required sources |
|---|---|---|---|
| Operations | `../pillars/operations.md` | 1,2,16,27,28,33,44 | AX1/4/5/10 and version/nodegroup/add-on/logging facts |
| Resilience & HA | `../pillars/resilience.md` | 4,5,7,14,35,36 | [`metrics-thresholds.md`](metrics-thresholds.md): 7-day health/restarts/EC2 status |
| Security | `../pillars/security.md` | 21,22,24,34,39,42,43,46 | AX3/10/11/12 auth/logging/KMS/endpoint facts |
| Scalability | `../pillars/scalability.md` | 2,8,9,18,24,26,27,37,41 | pending/API metrics and applicable AWS limits |
| Performance | `../pillars/performance.md` | 4,5,11,12,13,35,36,47 | utilization/throttling metrics and Compute Optimizer |
| Observability | `../pillars/observability.md` | 7,19,29 | metrics/logs and alarm inventory |
| Networking | `../pillars/networking.md` | 8,10,25,26,41 | AX7/9, target health, ENA/DNS/NAT metrics |
| Cost / Architecture | `../pillars/cost-architecture.md` | 4,5,8,10–13,20,23,28,29,32,36,47 | utilization, cross-AZ, Compute Optimizer |
| Control Plane Health | `../pillars/control-plane.md` | public logs/metrics, not normal kubectl inventory | staged `../control-plane-health/` source/query/threshold files |
| AWS API / Insights | `../aws-api-checks.md` | audited read-only EKS/EC2/IAM APIs and Cluster Insights | This unit is the AWS-side source. |

## Scope and gates

- Named pillar: grade that unit; add AX only when AWS-side facts are required.
- Full operations/best-practices/readiness/CWR: all nine pillars plus AX.
- Pre-upgrade/pre-migration or Extended Support: `../upgrade-readiness.md`, `../k8s-deprecated-apis.md`, AX1.
- Windows only when `windows_nodes > 0`; Hybrid only when `hybrid_nodes > 0`; AI/ML only when `gpu_nodes > 0 || neuron_nodes > 0`.
- Evaluate [`cluster-gates.md`](cluster-gates.md) for Auto Mode, IPv6, Fargate, CNI, mixed OS, and EKS Anywhere. Gates change applicability, not membership.

## Shared grading references

Load [`grading-guards.md`](grading-guards.md) once in S6. Load [`common-checks-coverage.md`](common-checks-coverage.md) only for a full review/CWR or S7 QA. Human material under `../docs/` is not normal runtime authority; `../docs/minimum-rbac.md` is allowed only for an access-policy question/denial. Do not load remediation or decision trees in S5.

Unavailable evidence leaves every selected canonical row present as N/A with the exact error. Never reduce membership because a source is absent.
