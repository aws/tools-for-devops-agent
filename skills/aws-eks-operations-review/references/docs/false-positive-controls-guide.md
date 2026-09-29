# False-positive controls

## Contents

- Controls FP1–FP12 (trigger → disallowed conclusion → required evidence)
- Evidence confidence model (high / medium / low + rules)

When grading checks, apply these guards to prevent unsupported conclusions. Each entry lists:
- **Trigger** — the observed signal that might lead to a false conclusion.
- **Disallowed conclusion** — what you must NOT conclude from this signal alone.
- **Required evidence** — what you need before the conclusion is valid.

## Controls

### FP1 — Pending pods ≠ scheduler failure

| | |
|---|---|
| **Trigger** | `pods_pending > 0` |
| **Disallowed conclusion** | "The scheduler is broken" or "Add more nodes immediately" |
| **Required evidence** | Determine which of these applies: insufficient capacity (no nodes can fit the request), resource fragmentation (capacity exists but not contiguous), taints/tolerations mismatch, node selector miss, affinity/anti-affinity conflict, topology spread constraint, volume topology (EBS AZ mismatch), scheduling gates (1.26+), Karpenter/CAS provisioning failure (check provisioner logs), or an actual scheduler error (CP18 + scheduler error logs). Each has a different fix. |

### FP2 — High CPU ≠ needs more nodes

| | |
|---|---|
| **Trigger** | `node_cpu_utilization > 80%` |
| **Disallowed conclusion** | "Add more capacity" without investigating why |
| **Required evidence** | Check: (a) are requests/limits set correctly? (b) is one workload dominating? (c) is it a temporary spike or sustained? (d) does the autoscaler have room to scale? High utilization with correct limits and scaling configured may be **healthy efficiency**, not a problem. |

### FP3 — OOMKilled ≠ memory leak

| | |
|---|---|
| **Trigger** | Container terminated with `OOMKilled` |
| **Disallowed conclusion** | "The application has a memory leak" |
| **Required evidence** | Distinguish: memory limit set too low (container always uses near-limit), legitimate burst (occasional spikes), application growth (gradual increase over days/weeks — may be a leak), sidecar memory not accounted for, node memory pressure causing kernel OOM (not container limit), or runtime/JVM behavior (GC not reclaiming before limit). A memory leak requires evidence of **sustained growth over time**, not a single OOMKill. |

### FP4 — HTTP 403 ≠ authentication failure

| | |
|---|---|
| **Trigger** | `responseStatus.code = 403` in audit logs |
| **Disallowed conclusion** | "Authentication is broken" |
| **Required evidence** | 403 is an **authorization** failure (authenticated but not permitted). Authentication failures manifest as 401. Check: RBAC binding missing, access policy not attached (AX2), namespace mismatch, or intentional deny (policy engine). A spike in 403s from a known service account → check if its RBAC binding was removed. |

### FP5 — HTTP 409 may be normal

| | |
|---|---|
| **Trigger** | `responseStatus.code = 409` (Conflict) |
| **Disallowed conclusion** | "The cluster is unhealthy" or "There's a bug" |
| **Required evidence** | 409 is normal **optimistic concurrency** — Kubernetes uses resource versions for conflict resolution. Controllers intentionally retry on 409. Only flag as a problem if: (a) a single resource has sustained 409s blocking convergence, (b) `workqueue_retries_total` is growing unbounded, or (c) a controller is logging errors about inability to update. |

### FP6 — Brief 429 spike ≠ sustained API saturation

| | |
|---|---|
| **Trigger** | `apiserver_request_total_429` has a spike |
| **Disallowed conclusion** | "The API server is saturated — upgrade the control plane" |
| **Required evidence** | Check: (a) duration — a 1-minute spike during a deployment is APF working correctly; sustained > 5 min is a problem; (b) priority level — `workload-low` 429s are expected behavior; `system`/`leader-election` 429s are critical; (c) identify the caller (CP5/CP6) — a single noisy client should be fixed at the client, not by adding API capacity. |

### FP7 — Missing PDB ≠ always high severity

| | |
|---|---|
| **Trigger** | `workloads_without_pdb > 0` |
| **Disallowed conclusion** | Always marking this Critical/High |
| **Required evidence** | Severity depends on: (a) replica count — a single-replica workload with a PDB would just block updates; (b) environment — non-prod may intentionally skip PDBs; (c) workload type — a CronJob or batch worker may not need disruption protection. Grade High for multi-replica **production** stateful or customer-facing workloads; Medium for stateless; Low for dev/test. |

### FP8 — Low utilization ≠ excess capacity

| | |
|---|---|
| **Trigger** | `node_cpu_utilization < 20%` or `pod_cpu_utilization < 10%` |
| **Disallowed conclusion** | "You're over-provisioned — remove nodes" |
| **Required evidence** | Check: (a) is the cluster sized for a peak that hasn't occurred in the 7-day window? (b) are there resource reservations for disaster recovery or failover? (c) is the low utilization during off-hours and the cluster lacks a scaling schedule? (d) is it a newly provisioned cluster that hasn't received production traffic yet? Low utilization is a **cost finding** (right-sizing opportunity), not automatically "excess capacity that should be removed." |

### FP9 — Permission exists ≠ compromise

| | |
|---|---|
| **Trigger** | RBAC binding grants broad permissions (e.g. `cluster-admin` to a service account) |
| **Disallowed conclusion** | "The cluster is compromised" or "There is active exploitation" |
| **Required evidence** | Excessive permissions are a **security posture** finding (blast-radius risk), not evidence of active compromise. For compromise evidence, look at: audit log anomalies, unexpected pods/containers, unknown service accounts being used, GuardDuty findings, or lateral movement patterns. |

### FP10 — Object growth alone ≠ etcd pressure

| | |
|---|---|
| **Trigger** | Object counts increasing (Secrets, ConfigMaps, Events, Leases) |
| **Disallowed conclusion** | "etcd is about to fill up" |
| **Required evidence** | Object growth must be correlated with `apiserver_storage_size_bytes` (CP1). A cluster can have many objects without pressure if they're small. Check: (a) actual etcd size vs. the 8 GB ceiling, (b) growth **rate** (is it accelerating?), (c) what type dominates (Events are auto-cleaned; Secrets/CRDs are not). Only flag etcd pressure when size > 75% (6 GB) or growth rate > 10%/week. |

### FP11 — Missing logs ≠ health

| | |
|---|---|
| **Trigger** | CloudWatch log queries return empty results |
| **Disallowed conclusion** | "No errors found — the control plane is healthy" |
| **Required evidence** | Empty results may mean: (a) control-plane logging is disabled (check AX10), (b) the log group doesn't exist, (c) the time window is too narrow, (d) log delivery is delayed (up to several minutes), or (e) the query filters are too narrow. Always verify logging is enabled before interpreting empty results as health. Missing telemetry is not evidence of health — it is evidence of a **visibility gap**. |

### FP12 — Deprecated API in source ≠ deployed usage

| | |
|---|---|
| **Trigger** | Source code or Helm charts reference a deprecated API version |
| **Disallowed conclusion** | "The cluster is using deprecated APIs that will break on upgrade" |
| **Required evidence** | Only **deployed** (live in-cluster) usage of removed/deprecated APIs blocks an upgrade. Check: (a) EKS Cluster Insights (AX1) — the authoritative signal, (b) audit logs filtering for the deprecated API (CP9), (c) `kubectl get` of the resource type at the old API version. Source-code references that haven't been deployed are a code-hygiene finding, not an upgrade-blocking finding. |

## Evidence confidence model

When applying these controls, classify each finding's confidence:

| Confidence | Criteria |
|-----------|----------|
| **High** | One authoritative source (e.g. `apiserver_storage_size_bytes` for etcd size) or two independent correlated sources |
| **Medium** | Single non-authoritative source, or inference from related signals |
| **Low** | Partial data, conflicting evidence, or untestable hypothesis |

**Rules:**
- Correlation does not prove root cause.
- Missing telemetry is not evidence of health.
- Partial results cannot prove absence.
- Conflicting evidence **always reduces** confidence to Low.
- Stale evidence (> 7 days old without refresh) must not override newer evidence.
