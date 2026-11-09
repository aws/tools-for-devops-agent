# Investigation procedures

The procedures the agent walks during a control-plane health investigation. Each procedure is a sequence: which queries to run from `queries.md`, which metrics to pull, what threshold from `thresholds.md` to apply, and which playbook in the `remediations-*.md` files (`remediations-etcd.md` / `remediations-apf.md` / `remediations-apiserver.md`) to recommend.

The agent runs only the procedures the symptom calls for.

> **Naming note:** other reference files may cite these procedures with a `cp_` prefix (e.g. `cp_health_overview`, `cp_etcd_pressure`) — those are the same procedures defined here. A typical investigation walks `health_overview` first, then drills into one or two signals — not all eight every time.

## Contents

- Procedure inventory
- Common output shape
- Procedure: `health_overview`
- Procedure: `etcd_pressure`
- Procedure: `apf_health`
- Procedure: `top_callers`
- Procedure: `kcm_qps`
- Procedure: `scheduler_lag`
- Procedure: `5xx_recent`
- Procedure: `eviction_stalls`
- Tool selection guidance for the agent
- What the agent MUST NOT do

## Procedure inventory

| Name | When the agent runs it | Output |
|------|------------------------|--------|
| `health_overview` | Always first. The cheapest call. | One-line status per signal: `etcd`, `apf`, `api_server`, `kcm`, `scheduler`, `eviction`. |
| `etcd_pressure` | When `health_overview.etcd` is non-`ok`. | etcd db size, % of quota, growth rate, top-growth resource types, likely controller offenders, recommendations. |
| `apf_health` | When `health_overview.apf` is non-`ok`. | Per-priority rejection rate, hot/cold instances, 429 rate by user agent. |
| `top_callers` | Always safe; useful as a baseline. | Top usernames / service accounts by call volume *with* P99 latency. |
| `kcm_qps` | When `health_overview.kcm` is non-`ok`, or as a controller backpressure check. | Per-controller QPS vs the `kubeAPIQPS=20` ceiling. |
| `scheduler_lag` | When `health_overview.scheduler` is non-`ok`. | Unschedulable pod count, top failure reasons, recent affected pods. |
| `5xx_recent` | When `health_overview.api_server` shows 5xx. | Recent 5xx and `healthz` failures, with offending requestURI/verb/userAgent. |
| `eviction_stalls` | When `health_overview.eviction` is non-`ok`, or during a node drain / scale-down. | Pods stuck in eviction (usually missing PDB or stuck finalizer). |

## Common output shape

Every procedure returns the same shape so the agent can format alerts and reports consistently:

```json
{
  "status": "ok",
  "tier": "informational",
  "customer_facing_label": "Healthy — informational",
  "observation": "...",
  "evidence": {
    "queries": ["CP10"],
    "metrics": ["apiserver_storage_db_total_size_in_bytes"],
    "log_group": "/aws/eks/prod-cluster/cluster",
    "window_start": "<ISO8601-UTC>",
    "window_end":   "<ISO8601-UTC>"
  },
  "remediation": {
    "playbook_id": "R-ETCD-1",
    "headline": "...",
    "next_steps": ["..."],
    "references": ["..."]
  },
  "confidence": "high",
  "sources_used": ["cloudwatch_logs_insights", "container_insights"],
  "sources_missing": ["amp"]
}
```

`status` is one of `ok`, `degraded`, or `error`. `tier` is one of `critical`, `high`, `medium`, `informational`. `confidence` reflects source agreement (see `metric-sources.md` §5).

## Procedure: `health_overview`

**When.** Always first. Used as a triage gate so the agent only drills into red signals.

**Steps.**

1. Validate `cluster_arn` resolves to an EKS cluster the agent has read access to.
2. Detect observability sources per `metric-sources.md` §3.
3. For each of the six signals, do the cheapest possible check:
   - `etcd` — read `apiserver_storage_db_total_size_in_bytes` from Container Insights or CloudWatch native metrics.
   - `apf` — count 429s in CP7 over the time window.
   - `api_server` — count 5xx in CP8 over the time window; check CP12 for healthz failures.
   - `kcm` — sample CP14 across the standard controller list, take the max QPS.
   - `scheduler` — count unscheduled-pod events in CP18.
   - `eviction` — count distinct pods in CP17.
4. Apply thresholds to each. Roll up to `overall_status` = worst signal status.

**Output (healthy):**

```json
{
  "status": "ok",
  "overall_status": "ok",
  "sources_detected": ["cloudwatch_logs_insights", "container_insights", "datadog"],
  "sources_missing": ["amp", "in_cluster_prom"],
  "signals": {
    "api_server": {"status": "ok",        "detail": "0 sustained 5xx, P99 LIST 0.3s"},
    "etcd":       {"status": "attention", "detail": "78% of 8 GB quota, +9% in 7 days"},
    "apf":        {"status": "ok",        "detail": "0 rejections in priority system/leader-election"},
    "kcm":        {"status": "ok",        "detail": "max controller QPS 4.2"},
    "scheduler":  {"status": "ok",        "detail": "0 unschedulable pods in last 60 min"},
    "eviction":   {"status": "ok",        "detail": "no eviction stalls"}
  }
}
```

`overall_status` precedence: `ok` < `attention` < `action_required`.

## Procedure: `etcd_pressure`

**When.** `health_overview.etcd` is `attention` or `action_required`.

**Steps.**

1. Pull current size and growth from supporting metrics:
   - `apiserver_storage_db_total_size_in_bytes` (now, 7 days ago, 30 days ago).
   - `apiserver_storage_db_total_size_in_use_in_bytes` if Container Insights is on.
   - PromQL `apiserver_storage_db_total_size_in_bytes` from AMP / in-cluster Prom if present.
2. Run CP10 — top writes to etcd over the time window.
3. Aggregate CP10 results per resource type, compute share of total writes.
4. Look up dominant resource(s) in the resource → controller mapping (`remediations-etcd.md` Playbook index).
5. Apply thresholds (`thresholds.md` — etcd pressure section). Decide tier.
6. Pick the playbook by dominant resource:

   | Dominant resource | Playbook |
   |-------------------|---------|
   | `jobs` / `pods` | R-ETCD-1 |
   | `replicasets` | R-ETCD-2 |
   | `events` | R-ETCD-3 |
   | `secrets` / `configmaps` | R-ETCD-4 |
   | `csrs` | R-ETCD-5 |
   | `leases` | R-ETCD-6 |
   | (none dominant; etcd > 90% anyway) | R-ETCD-7 |

**Sample output.**

```json
{
  "status": "ok",
  "tier": "high",
  "customer_facing_label": "Action required — control plane saturation risk",
  "current_size_bytes": 6442450944,
  "current_size_pct_of_quota": 78.1,
  "growth_7d_pct": 9.1,
  "top_growth_resources": [
    {"resource": "jobs",   "writes_in_window": 124356, "share_pct": 41.2},
    {"resource": "events", "writes_in_window": 88912,  "share_pct": 29.5}
  ],
  "likely_offenders": [
    {"resource": "jobs", "likely_controller": "CronJob without ttlSecondsAfterFinished"}
  ],
  "remediation": {
    "playbook_id": "R-ETCD-1",
    "headline": "Set spec.ttlSecondsAfterFinished on CronJobs",
    "next_steps": [
      "Audit CronJobs cluster-wide.",
      "Patch to add ttlSecondsAfterFinished: 3600 and successfulJobsHistoryLimit: 3.",
      "Bulk-delete completed Jobs older than 7 days, in batches of 200."
    ],
    "references": [
      "https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/",
      "https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html"
    ],
    "estimated_recovery": "etcd size decreases on next defrag (within 24 h)."
  },
  "evidence": {"queries": ["CP10"], "metrics": ["apiserver_storage_db_total_size_in_bytes"]}
}
```

## Procedure: `apf_health`

**When.** `health_overview.apf` is `attention` or `action_required`.

**Steps.**

1. Run CP7 (response code distribution) — find 429 count.
2. Run CP13 (client-side throttling messages).
3. If Container Insights / AMP / in-cluster Prom is available, pull:
   - `apiserver_flowcontrol_rejected_requests_total` by `priority_level`.
   - `apiserver_flowcontrol_current_inqueue_requests` by `priority_level`.
4. Determine which priority level is rejecting:
   - `workload-low` only → tier `informational` → playbook R-APF-1 (no action).
   - `workload-high` > 1% of total → tier `high` → playbook R-APF-2.
   - `system` or `leader-election` for > 5 min → tier `critical` → playbook R-APF-2.
5. Run CP5 / CP6 to find top throttled callers — feeds the playbook's "find the source first" step.

## Procedure: `top_callers`

**When.** Always safe to run; useful as a baseline even when status is `ok`.

**Steps.**

1. Run CP4 (LIST pods latency by user agent) — gives P99 / P90 / P50 per caller.
2. Run CP6 (total request count by user agent) — gives total share.
3. Mark any caller > 30% of total LIST volume OR P99 LIST > 1 s as tier `high`. Otherwise `informational`.

## Procedure: `kcm_qps`

**When.** `health_overview.kcm` is non-`ok`, or proactively to spot client-side throttling.

**Steps.**

1. Run CP14 once for each controller in the standard list:
   `deployment-controller`, `replicaset-controller`, `cronjob-controller`, `job-controller`, `endpoint-controller`, `endpointslice-controller`, `generic-garbage-collector`, `horizontal-pod-autoscaler`, `persistent-volume-binder`.
2. For each, compute QPS over the window.
3. Any controller with sustained QPS > 18 (90% of `kubeAPIQPS=20`) is `high` — playbook R-KCM-1.
4. Any controller with P99 LIST > 5 s is also `high`.

## Procedure: `scheduler_lag`

**When.** `health_overview.scheduler` is non-`ok`.

**Steps.**

1. Run CP18 — `Unable to schedule pod` events from the scheduler log.
2. Aggregate by failure reason (`Insufficient cpu`, `Insufficient memory`, `node(s) had taint X`, etc.).
3. List the top-N affected pods with first-seen timestamps.
4. If unschedulable pods sustained > 10 min → tier `high` → playbook R-SCHED-1.

## Procedure: `5xx_recent`

**When.** `health_overview.api_server` shows 5xx.

**Steps.**

1. Run CP8 (5xx events).
2. Run CP12 (healthz failures).
3. Group by `requestURI`, `verb`, `userAgent`.
4. Cross-check `etcd_pressure` (5xx on writes is often etcd quota or apply latency) and `apf_health` (5xx can be downstream of APF saturation).
5. If neither cross-check explains it, escalate to AWS Support — the EKS service-side SLA covers this case.

## Procedure: `eviction_stalls`

**When.** `health_overview.eviction` is non-`ok`, or during a node drain / scale-down.

**Steps.**

1. Run CP16 (eviction events by EKS node manager).
2. Run CP17 (count of pods failing eviction).
3. For any pod failing for > 30 min, mark `high` and recommend R-EVICT-1: check PDB, finalizers, terminationGracePeriod.

## Tool selection guidance for the agent

| Situation | Procedures to run |
|-----------|------------------|
| Periodic health check (no symptom yet) | `health_overview` only — drill down only when a signal is non-`ok`. |
| Acute incident ("kubectl is slow") | `health_overview` first, then drill into the red signal. |
| Investigating a specific user agent | `top_callers`, then `kcm_qps` if it's a controller. |
| Pre-flight before a load test | All eight procedures, then re-run `health_overview` after the test. |
| Post-incident review | `health_overview` over the incident window, plus the relevant detail procedure. |

## What the agent MUST NOT do

The agent applies this safety guidance:

- **Never auto-execute remediation.** Every playbook is a recommendation; the customer or their account team applies the change.
- **Never delete in production without explicit user confirmation**, even when the resource is "obviously" leaked.
- **Never raise `kubeAPIQPS` as a first response.** Raising QPS pushes load to etcd. The right answer is almost always to reduce demand.
- **Never modify control-plane configuration directly.** EKS does not let you. The right path for control-plane sizing is Provisioned mode (R-CP-1).
- **Never echo Secret values.** Reference Secrets by name only when summarizing findings.
