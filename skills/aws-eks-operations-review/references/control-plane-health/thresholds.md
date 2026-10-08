# Default thresholds

Every threshold in this file is anchored to a published source — the [EKS Control Plane Monitoring guide](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html), [EKS Scalability — Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html), the upstream [Kubernetes scalability SLOs](https://github.com/kubernetes/community/blob/master/sig-scalability/slos/slos.md#steady-state-slisslos), or the etcd 8 GB ceiling.

Customer-facing severity uses descriptive labels. Internal tier names (`critical`/`high`/`medium`/`informational`) are mapped to descriptive labels in the report writer.

## Contents

- Tier mapping (internal → customer-facing)
- Signal: etcd pressure
- Signal: API server throttling (APF)
- Signal: API server health
- Signal: kube-controller-manager backpressure
- Signal: scheduler
- Signal: eviction stalls
- Signal: 4xx churn (upgrade-planning)
- Signal: additional diagnostics (CP19–CP25)
- Signal: metric-native checks (CP-M series)
- Override format
- Cross-validation rules (from `metric-sources.md`)

## Tier mapping (internal → customer-facing)

| Internal tier | Customer-facing label |
|--------------|----------------------|
| critical | "Action required — control plane impaired" |
| high | "Action required — control plane saturation risk" |
| medium | "Attention — operational hygiene" |
| informational | "Healthy — informational" |

## Signal: etcd pressure

| Threshold | Tier | Source |
|-----------|------|--------|
| `apiserver_storage_size_bytes > 6.0 GB` (75% of 8 GB) | high | etcd upstream + EKS scalability guide |
| `apiserver_storage_size_bytes > 7.2 GB` (90%) | critical | same |
| 7-day growth rate > 10% | high | rule of thumb — sustained growth eats quota in weeks |
| 7-day growth rate > 25% | critical | runaway controller / CRD leak |
| Single resource type accounts for > 40% of writes (CP10) | high | indicates a controller is leaking objects |

> **⚠️ CRITICAL — Unit conversion (bytes → GB). Get this right or the grade is wrong.**
>
> The metric `apiserver_storage_size_bytes` reports in **bytes**. The thresholds above are in **GB (base-10, i.e. 1 GB = 1,000,000,000 bytes)**. You MUST convert correctly before grading:
>
> | Raw metric value (bytes) | Correct conversion | % of 8 GB quota |
> |---|---|---|
> | 7,798,784 | **7.80 MB** (÷ 1,000,000) | **0.10%** → PASS |
> | 7,798,784,000 | **7.80 GB** (÷ 1,000,000,000) | **97.5%** → CRITICAL |
> | 6,400,000,000 | **6.40 GB** | **80%** → HIGH |
> | 800,000,000 | **800 MB** | **10%** → PASS |
>
> **Common mistake:** confusing MB with GB. If the raw value is in the millions (10⁶), that's megabytes — well under the 8 GB quota. Only values in the billions (10⁹) approach the threshold. Always show the full byte value AND the converted GB value in the evidence so the math is verifiable.
>
> **Formula:** `percentage = (raw_bytes / 8,000,000,000) × 100`

> **Quota (confirmed against current EKS docs):** **Standard** control plane supports **8 GB** of etcd database size ([EKS Provisioned Control Plane](https://docs.aws.amazon.com/eks/latest/userguide/eks-provisioned-control-plane.html)). AWS's own recommended alarm point is **80% ≈ 6.4 GB** ([CloudWatch Operator + control-plane metrics blog](https://aws.amazon.com/blogs/containers/proactive-amazon-eks-monitoring-with-amazon-cloudwatch-operator-and-aws-control-plane-metrics/)); our 75% (6.0 GB) / 90% (7.2 GB) bands bracket it. **Provisioned Control Plane** tiers (XL/2XL/4XL) raise this to **16 GB** — if the cluster is in Provisioned mode, scale the GB thresholds to the tier's 16 GB limit before grading CP1/CP2.
>
> **Detecting Provisioned mode:** Use `DescribeCluster` → `computeConfig` or check the cluster's tier in the EKS console. If the cluster is on a Provisioned tier, replace 8 GB with 16 GB in all etcd thresholds: warn at 75% of 16 GB = **12 GB**, critical at 90% = **14.4 GB**. The growth-rate percentages remain the same.
>
> **Public metric name:** `apiserver_storage_size_bytes` is the current name (EKS 1.28+); older clusters expose `apiserver_storage_db_total_size_in_bytes`. The CloudWatch equivalent is `etcd_mvcc_db_total_size_in_use_in_bytes`. etcd is not directly scrapable — these are surfaced by the API server. See [`metric-sources.md` §4.2](metric-sources.md).

## Signal: API server throttling (APF)

| Threshold | Tier | Source |
|-----------|------|--------|
| Any 429 in priority `system` or `leader-election` for > 5 min | critical | EKS Control Plane Monitoring guide — these levels protect the control plane |
| 429s in `workload-high` > 1% of total | high | indicates real workload pain |
| 429s only in `workload-low` | informational | this is what APF is *for* |
| Single user agent generating > 30% of total LIST volume (CP5/CP6) | high | likely runaway client |

> **Public metric + the `reason` label picks the remediation.** Grade from `apiserver_flowcontrol_rejected_requests_total{flow_schema, priority_level, reason}` ([EKS Scalability — Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html)). `reason="queue-full"` → the priority level's queue is too shallow (raise queue length); `reason="concurrency-limit"` → not enough shares/seats (redistribute shares from an idle priority); `reason="time-out"` → requests aging out (both). Compare `apiserver_flowcontrol_current_executing_seats` against `apiserver_flowcontrol_nominal_limit_seats` per priority to size the change.

## Signal: API server health

| Threshold | Tier | Source |
|-----------|------|--------|
| Any sustained 5xx (CP8) over a 5-min window | critical | server-side failures |
| Any `healthz check failed` event (CP12) | critical | API server unhealthy |
| LIST avg latency > 1 s on any URI (CP2) | high | breaches Kubernetes SLO |
| LIST max latency > 20 s on any URI (CP3) | critical | EKS support engineering rule of thumb |

## Signal: kube-controller-manager backpressure

| Threshold | Tier | Source |
|-----------|------|--------|
| Any controller sustained > 18 QPS (90% of `kubeAPIQPS=20`) | high | EKS Control Plane Monitoring guide explicitly calls this out as client-side throttling territory |
| Per-controller LIST p99 (CP14) > 5 s | high | derivative of the same guidance |
| Growing `workqueue_depth` for any controller | high | controller falling behind — EKS 1.28+ public metric |

> **Public metric (EKS 1.28+):** grade this from `workqueue_depth` / `workqueue_adds_total` via `metrics.eks.amazonaws.com/v1/kcm` instead of the CP14 audit-log query where available. Per-caller QPS attribution still comes from the audit log (CP14). See [`metric-sources.md` §4.6](metric-sources.md).

## Signal: scheduler

| Threshold | Tier | Source |
|-----------|------|--------|
| Any `Unable to schedule pod` event (CP18) sustained > 10 min | high | Cluster Autoscaler / Karpenter is not keeping up |
| > 5 distinct pods unschedulable simultaneously | high | scheduler queue backing up |
| `scheduler_pending_pods{queue="unschedulable"}` sustained > 0 for > 10 min | high | direct metric equivalent (EKS 1.28+) |

> **Public metric (EKS 1.28+):** `scheduler_pending_pods{queue="unschedulable"}` via `metrics.eks.amazonaws.com/v1/ksh` is the direct equivalent of the CP18 audit-log query. On pre-1.28 clusters, fall back to CP18. See [`metric-sources.md` §4.6](metric-sources.md).

## Signal: eviction stalls

| Threshold | Tier | Source |
|-----------|------|--------|
| Any pod failing eviction (CP17) for > 30 min | high | usually missing PDB or stuck finalizer |
| Sustained eviction failures across multiple pods | critical | scale-down or upgrade flow blocked |

## Signal: 4xx churn (informational, but useful for upgrade planning)

| Threshold | Tier | Source |
|-----------|------|--------|
| Recurring 4xx on a deprecated API (CP9) | medium | upgrade-readiness signal — see [EKS upgrade insights](https://repost.aws/knowledge-center/eks-cluster-upgrade-api-errors) |

## Signal: additional diagnostics (CP19–CP25)

| Threshold | Tier | Source |
|-----------|------|--------|
| Sustained/spiking 403 denials or authenticator "denied" (CP19) | high | broken access (controller/workload lost RBAC) or probing — [Retrieve control plane logs](https://repost.aws/knowledge-center/eks-get-control-plane-logs) |
| Mutating (write-path) p99 latency > 1 s (CP20) | high | etcd apply / slow admission webhook — Kubernetes mutating SLO ≈ 1 s |
| Any `system:anonymous` / `system:unauthenticated` API access (CP25) | critical | anonymous access red flag — [GuardDuty AnonymousAccessGranted](https://aws.amazon.com/blogs/security/how-to-detect-security-issues-in-amazon-eks-clusters-using-amazon-guardduty-part-1/) |
| A single user agent dominating WATCH volume (CP23) | high | apiserver connection / watch-cache pressure |
| CP21/CP22/CP24 (change-correlation, attribution) | investigative | RCA context — correlate a recent change with the incident window; not a standalone FAIL |

## Signal: metric-native checks (CP-M series)

All graded directly from public metrics (upstream Kubernetes / etcd names on the API server `/metrics` endpoint). No audit log required. See [`../pillars/control-plane.md`](../pillars/control-plane.md) "Metric-native checks" and the [Kubernetes Metrics Reference](https://kubernetes.io/docs/reference/instrumentation/metrics/).

| Check | Threshold | Tier | Public metric / source | Min EKS version |
|-------|-----------|------|------------------------|-----------------|
| CP-M1 etcd object counts | any single `resource` count with sustained > 25% 7-day growth, or one resource dominating total objects | high | `apiserver_storage_objects{resource=...}` — direct "what is in etcd" companion to CP1/CP3 | 1.26+ |
| CP-M2 inflight saturation | read-only or mutating inflight sustained > 80% of the observed concurrency ceiling | high | `apiserver_current_inflight_requests{request_kind}` — saturation that precedes 429s | All versions (via `/metrics`) |
| CP-M3 LIST response sizes | p99 response size for any `resource` sustained > 10 MB, or trending up week-over-week | medium | `apiserver_response_sizes` — large LISTs drive apiserver/etcd memory pressure | 1.27+ |
| CP-M4 admission webhook health | any sustained `apiserver_admission_webhook_rejection_count` > 0, or webhook p99 duration > 1 s | high | `apiserver_admission_webhook_rejection_count`, `apiserver_admission_webhook_admission_duration_seconds` — a slow/failing webhook blocks pod creation | 1.28+ (CloudWatch); all versions (via `/metrics`) |
| CP-M5 etcd request latency | p99 `etcd_request_duration_seconds` > 1 s for any operation | high | [EKS Control Plane best practices](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html) — separates API-slow from etcd-slow | All versions (via `/metrics`) |
| CP-M6 APF queue wait | any non-trivial p99 wait in `system`/`leader-election`; workload-tier p99 wait trending up | high | `apiserver_flowcontrol_request_wait_duration_seconds{priority_level}` — early warning before rejections | 1.28+ (full seats model: 1.29+) |

> These thresholds are pragmatic defaults, not published SLOs (only CP-M5's 1 s aligns with the etcd/API latency guidance). Treat CP-M1/M2/M3 breaches as **investigate**, not automatic FAIL — pair with CP1 (etcd size) and CP6/CP7 (API health) before grading.

## Override format

Pass a JSON object at the `thresholds_override` input. Override only what you need — everything else falls back to the defaults above.

```json
{
  "etcd_quota_warn_pct": 75,
  "etcd_quota_critical_pct": 90,
  "etcd_growth_warn_pct_7d": 10,
  "etcd_growth_critical_pct_7d": 25,
  "etcd_dominant_resource_share_pct": 40,
  "apf_workload_high_rejection_pct": 1.0,
  "apf_caller_dominance_pct": 30,
  "kcm_qps_warn": 18,
  "kcm_p99_warn_seconds": 5.0,
  "list_avg_latency_warn_seconds": 1.0,
  "list_max_latency_critical_seconds": 20.0,
  "fivexx_window_minutes": 5,
  "scheduler_unsched_window_minutes": 10,
  "scheduler_unsched_pod_count": 5,
  "eviction_stuck_minutes": 30,
  "object_count_growth_warn_pct_7d": 25,
  "inflight_saturation_warn_pct": 80,
  "list_response_size_warn_mb": 10,
  "webhook_p99_warn_seconds": 1.0,
  "etcd_request_p99_warn_seconds": 1.0
}
```

## Cross-validation rules (from `metric-sources.md`)

When two or more sources cover the same signal, the skill cross-validates and surfaces disagreement as its own finding:

| Condition | Action |
|-----------|--------|
| Two sources agree within 10% | Use the value, mark `confidence: high`. |
| Two sources disagree by > 10% | Surface both values, mark `confidence: low`, recommend the customer check collector health. |
| Only one source available | Mark `confidence: medium`. |
| All sources missing | Mark the signal `unknown` and recommend enabling at least one source. |
