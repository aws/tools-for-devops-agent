# Pillar: Control Plane Health

Saturation and health of the EKS-managed control plane — etcd size/growth, API Priority & Fairness (APF) throttling, API server 5xx and LIST latency, KCM/scheduler backpressure, and eviction stalls. Grade **PASS / FAIL / N/A** with evidence, severity, recommendation.

Best-practice anchors: [EKS Control Plane Monitoring](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html) · [EKS Scalability — Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html)

## Data source — read this first

This domain is graded primarily from AWS-side signals rather than in-cluster kubectl state. The control plane is AWS-managed, so its health signals live in **CloudWatch Logs (`/aws/eks/{cluster}/cluster`), CloudWatch metrics, and any connected metrics backend** (Container Insights, native EKS control-plane metrics, Amazon Managed / in-cluster Prometheus, or a third-party connector such as Datadog / New Relic / Dynatrace / Splunk). The grading procedure, queries, thresholds, and remediations live in this skill's reference files, linked from SKILL.md.

> **These are public, customer-obtainable metrics — not internal AWS tooling.** Every metric this pillar grades is exposed to the customer through one of three public paths, so a finding can always cite a metric the customer can reproduce themselves. On **EKS 1.28+** this includes `kube-scheduler` and `kube-controller-manager` metrics, which were previously audit-log-only. See [Public control-plane metrics](#public-control-plane-metrics-customer-obtainable) below for the full list and per-check mapping.

**This pillar is MANDATORY for every operations review / CWR — always attempt collection; never skip it and never default it to N/A without first attempting.** The control plane is the single highest-impact failure surface (etcd going read-only, APF throttling privileged traffic, API 5xx), so a review that omits it is incomplete. Produce a detailed CP review, not a one-line deferral.

### What to collect (do this every run — do NOT defer with "pending query")

1. **Detect available sources first** (`metric-sources.md` §3): probe CloudWatch (`ListMetrics` in `ContainerInsights` / `AWS/EKS`), the audit log group (`DescribeLogStreams` on `/aws/eks/{cluster}/cluster` for a `kube-apiserver-audit` stream), any AMP workspace, and the agent space's third-party connectors (Datadog / New Relic / Dynatrace / Splunk). Record `sources_detected` / `sources_missing`.
2. **Is control-plane logging enabled?**
   - **Yes →** run the CloudWatch Logs Insights queries (**the full CP1–CP18 set**, `queries.md`) via the DevOps Agent's CloudWatch access (`logs:StartQuery` → poll → `logs:GetQueryResults`) **and** pull the control-plane metrics (`GetMetricData`). Grade the complete CP1–CP11 scorecard from both.
   - **No →** raise a FAIL finding that control-plane logging is disabled (recommend enabling [EKS control-plane logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)), then **still collect the metrics** — native EKS control-plane metrics (EKS 1.28+, free) and Container Insights carry etcd size, APF, request-latency, and scheduler signals without the audit log. Grade every check you can from metrics; only the audit-log-only signals (write concentration CP3, per-caller latency, throttling detail) stay N/A.
3. **Metrics-backend routing:** if a third-party connector (Datadog etc.) or Prometheus (AMP / in-cluster) is present, run the equivalent queries there too (`metric-sources.md` §4.3–4.5) and cross-validate (`metric-sources.md` §5). Prefer whichever source carries the signal; fan out when more than one is available.
4. **N/A only as a last resort:** mark a check N/A **only after attempting** and finding that no source (logs, metrics, Prometheus, or connector) carries that specific signal. Its evidence must state the actual reason (e.g. "logging disabled and no control-plane metrics namespace present"), not "pending."

**Do not abort claiming a CloudWatch/query tool is unavailable.** Attempt the `StartQuery` / `GetMetricData` calls through the DevOps Agent's AWS access; if a call genuinely errors, report the actual error (access denied / no log group) as the check's N/A evidence — never skip silently.

> This is a point-in-time review pillar. The same queries/thresholds can also run on a recurring schedule for continuous monitoring — that is a separate operating mode, not a reason to skip the pillar during this Discover→Review pass.

## What this pillar watches

Four signal categories, all anchored in the [EKS Control Plane Monitoring guide](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html):

| Signal | Headline question | What goes wrong if you miss it |
|--------|------------------|-------------------------------|
| **etcd pressure** | Is etcd close to the 8 GB ceiling? Is something filling it faster than it should? | Cluster goes read-only — full outage. |
| **APF throttling** | Are 429s landing in `system` or `leader-election`? | Operators fail, controllers fall behind, cluster appears flaky. |
| **API server health** | Sustained 5xx? avg LIST latency over 1 s? | kubectl breaks, CI/CD breaks. |
| **KCM & scheduler backpressure** | Any controller running > 18 QPS? Pods unschedulable > 10 min? | Deployments stall, autoscaling fails. |

Single-metric CloudWatch alarms catch the symptom (5xx, latency) after a slow burn has already run. This pillar investigates the slow burn directly — reading the audit log, correlating with recent deploys, and applying remediations the moment a threshold trips.

## Public control-plane metrics (customer-obtainable)

All control-plane signals this pillar grades are exposed to the customer through three public delivery paths. Prefer citing the Prometheus metric name (reproducible with `kubectl get --raw`) in findings.

| Path | Availability | Carries | How to read |
|------|-------------|---------|-------------|
| **API server `/metrics`** | All versions | apiserver, APF, and etcd-via-apiserver metrics | `kubectl get --raw /metrics` |
| **`metrics.eks.amazonaws.com` API group** | **EKS 1.28+** | `kube-scheduler` and `kube-controller-manager` metrics (run in the AWS-managed account, otherwise not scrapable) | `kubectl get --raw "/apis/metrics.eks.amazonaws.com/v1/ksh/container/metrics"` (scheduler) · `.../v1/kcm/container/metrics` (KCM) |
| **`AWS/EKS` CloudWatch namespace** | EKS 1.28+ (free) | Core control-plane metrics, no scraping | `cloudwatch:GetMetricData` |

Sources: [Fetch control plane raw metrics](https://docs.aws.amazon.com/eks/latest/userguide/view-raw-metrics.html) · [EKS Control Plane best practices](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html) · [EKS Provisioned Control Plane](https://docs.aws.amazon.com/eks/latest/userguide/eks-provisioned-control-plane.html).

### Metric names by component

**API server** (`/metrics`, all versions): `apiserver_request_total` · `apiserver_request_duration_seconds*` (by `verb` for CP-M7) · `apiserver_current_inflight_requests` · `apiserver_response_sizes*` · `apiserver_storage_objects` · `apiserver_registered_watchers` (CP-M9) · `apiserver_admission_controller_admission_duration_seconds*` · `apiserver_admission_webhook_admission_duration_seconds*` · `apiserver_admission_webhook_rejection_count` · `rest_client_requests_total` (CP-M8) · `rest_client_request_duration_seconds*` (CP-M8)

**API Priority & Fairness** (`/metrics`, all versions): `apiserver_flowcontrol_rejected_requests_total` · `apiserver_flowcontrol_current_inqueue_requests` · `apiserver_flowcontrol_nominal_limit_seats` · `apiserver_flowcontrol_current_executing_seats` · `apiserver_flowcontrol_dispatched_requests_total` · `apiserver_flowcontrol_request_execution_seconds` · `apiserver_flowcontrol_request_wait_duration_seconds`

**etcd** (via apiserver `/metrics` — the etcd servers themselves are not directly scrapable, but the API server exposes its own etcd-client view): `etcd_request_duration_seconds*` (per `operation` — separates read/range from write/txn latency) · `apiserver_storage_objects` (object counts per resource — a cheap "what is in etcd" signal) · `apiserver_storage_size_bytes` (EKS 1.28+) or `apiserver_storage_db_total_size_in_bytes` (older name). CloudWatch equivalent: `etcd_mvcc_db_total_size_in_use_in_bytes` (planned to also ship as a Prometheus metric ~2H 2026).

**kube-scheduler** (`metrics.eks.amazonaws.com/v1/ksh`, EKS 1.28+): `scheduler_pending_pods` · `scheduler_schedule_attempts_total` · `scheduler_preemption_attempts_total` · `scheduler_preemption_victims` · `scheduler_pod_scheduling_attempts` · `scheduler_scheduling_attempt_duration_seconds` · `scheduler_pod_scheduling_sli_duration_seconds` · `kube_pod_resource_limit` · `kube_pod_resource_request` (the last two on the `/resourcemetrics` endpoint)

**kube-controller-manager** (`metrics.eks.amazonaws.com/v1/kcm`, EKS 1.28+): `workqueue_depth` · `workqueue_adds_total` · `workqueue_queue_duration_seconds` · `workqueue_work_duration_seconds` · `cronjob_controller_job_creation_skew_duration_seconds`

> **Version caveat:** the [EKS Control Plane Monitoring guide](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html) states scheduler/KCM cannot be scraped "(the API server being the exception)". That is now **stale for EKS 1.28+** — the newer [raw-metrics userguide](https://docs.aws.amazon.com/eks/latest/userguide/view-raw-metrics.html) supersedes it via the `metrics.eks.amazonaws.com` API group. On pre-1.28 clusters, fall back to the audit-log queries (CP14 for KCM, CP18 for scheduler).

## How to grade

1. Detect available observability sources ([`metric-sources.md`](metric-sources.md)).
2. Walk the procedures in [`procedures.md`](procedures.md): run `health_overview` first, then drill into any non-`ok` signal using the decision tree below.
3. Run the queries the procedures call for ([`queries.md`](queries.md), CP1–CP18) — for a full operations review / CWR run the **complete CP1–CP18 set plus the control-plane metrics** (`GetMetricData`), not a subset. Run CP19–CP25 only when a matching auth / write-path / change-correlation / WATCH / mutation-attribution / anonymous-access signal appears — they are diagnostic, not scorecard rows.
4. Evaluate against [`thresholds.md`](thresholds.md), and apply the grading guards in [`grading-guards.md`](grading-guards.md) — **before fixing any verdict**, check whether an FP guard blocks the naive conclusion (empty query ≠ healthy is FP11; a 429 spike ≠ scale the control plane is FP6). Record the applied guard ID with the status, and attach a confidence level per the confidence contract.
5. For each FAIL, pull the remediation from the split control-plane remediation files — [`remediations-etcd.md`](remediations-etcd.md) (R-ETCD-*), [`remediations-apf.md`](remediations-apf.md) (R-APF-*), and [`remediations-apiserver.md`](remediations-apiserver.md) (R-API-*, R-KCM-*, R-SCHED-*, R-EVICT-*, R-CP-*) — into the report's detailed-findings section. Customer-facing alert/finding copy is in [`alerting.md`](alerting.md).

### Investigation decision tree

```
health_overview                         ← which signals are red?
   │
   ├─ apf red ───── apf_health           ← which priority is rejecting?
   │                  ├─ system / leader-election → critical (R-APF-2)
   │                  └─ workload-low only → informational (R-APF-1)
   │
   ├─ etcd red ──── etcd_pressure        ← which resource type dominates writes?
   │                  ├─ jobs        → R-ETCD-1      ├─ secrets → R-ETCD-4
   │                  ├─ replicasets → R-ETCD-2      ├─ leases  → R-ETCD-6
   │                  ├─ events      → R-ETCD-3      └─ csrs    → R-ETCD-5
   │
   ├─ 5xx red ───── 5xx_recent           ← URI + verb + userAgent (R-API-3)
   ├─ kcm red ───── kcm_qps              ← which controller is throttled? (R-KCM-1)
   └─ scheduler red ─ scheduler_lag      ← top failure reasons (R-SCHED-1)
```

The agent's value-add is correlation: cross-reference each finding with the customer's recent deploys/changes (e.g. "etcd growth started 6 days ago, dominated by `applications.argoproj.io`" paired with "the ArgoCD operator was upgraded 6 days ago").

### Remediation principle — prefer the least disruptive option that resolves the finding

1. **Drop runaway / leaked objects first** — a leaked CronJob is almost always cheaper to fix than tuning APF.
2. **Tune APF before scaling the control plane** — a FlowSchema costs nothing.
3. **Scale the control plane (Provisioned mode) only when workload-side fixes are exhausted** — see R-CP-1.
4. **Never delete in production without user approval** — destructive operations always require explicit confirmation, even when the resource is "obviously" leaked.

## Checks (CP-series)

These roll the headline alert conditions into the review's PASS/FAIL/N/A scorecard. Evidence is the CloudWatch-observed value (query IDs CP1–CP18 in [`queries.md`](queries.md)).

| ID | Check | Pass criteria | Severity | Applicability / N/A predicate | Guards | Playbook |
|----|-------|---------------|----------|-------------------------------|--------|----------|
| CP1 | etcd database size | db < 75% of quota (8 GB Standard; 16 GB Provisioned Control Plane) | High | N/A only when no size metric after attempting all sources. | FP10, FP11 | R-ETCD-1…7 |
| CP2 | etcd growth rate | 7-day growth < 10% | High | Needs comparable 7-day datapoints; otherwise N/A. | FP10, FP11 | R-ETCD-1…7 |
| CP3 | etcd write concentration | no single resource type > 40% of writes | High | Audit-log-only; N/A when logging unavailable after attempt. | FP10, FP11 | R-ETCD-1…6 |
| CP4 | APF throttling (privileged tiers) | no 429s in `system` or `leader-election` | Critical | Metrics or audit; identify priority/reason/caller. | FP6, FP11 | R-APF-2 |
| CP5 | APF throttling (workload tiers) | no sustained 429s in workload priority levels | Medium | Metrics or audit; isolated low-tier rejection may be healthy APF. | FP6, FP11 | R-APF-1 |
| CP6 | API server 5xx | no sustained 5xx for > 5 min | High | N/A only after metric/log attempt. | FP5, FP11 | R-API-3 |
| CP7 | API server LIST latency | avg LIST latency < 1 s and max < 20 s | High | Never average across API servers; N/A if no duration source. | FP5, FP11 | R-API-1 / R-API-2 |
| CP8 | KCM QPS | no controller sustained > 18 QPS | Medium | Native KCM metrics need EKS 1.28+; else audit or N/A. | FP11 | R-KCM-1 |
| CP9 | Scheduler backpressure | no pods unschedulable > 10 min | Medium | Distinguish capacity vs constraints; native metrics need 1.28+. | FP1, FP11 | R-SCHED-1 |
| CP10 | Eviction stalls | no pod failing eviction > 30 min | Medium | Log/event-only; N/A after both unavailable. | FP7, FP11 | R-EVICT-1 |
| CP11 | Control-plane capacity mode | not running saturated after workload-side fixes exhausted | High | Provisioned-mode recommendation only after noisy-client/APF fixes. | FP6, FP11 | R-CP-1 (consider Provisioned mode) |

Guards column references [`grading-guards.md`](grading-guards.md). Apply the listed guard before fixing the verdict — most rows carry FP11 (an empty query/no-datapoint result is *unknown*, never an automatic PASS).

### Public metric mapping (cite these in findings)

Each check maps to a customer-obtainable metric where one exists. `✅` = a direct public metric; `⚠️` = no direct metric, use the audit-log query; version note marks 1.28+-only sources.

| ID | Public metric | Direct? | Notes |
|----|---------------|:------:|-------|
| CP1 | `apiserver_storage_size_bytes` (Prom) / `etcd_mvcc_db_total_size_in_use_in_bytes` (CW) | ✅ | 8 GB ceiling (Standard); 16 GB on Provisioned Control Plane. AWS-recommended alarm: 80% (~6.4 GB) |
| CP2 | rate of the CP1 metric over 7d | ✅ | Growth derived from the same series |
| CP3 | — (`apiserver_request_total` by resource is a proxy) | ⚠️ | True write concentration needs the audit log (CP10) |
| CP4 | `apiserver_flowcontrol_rejected_requests_total{priority_level=~"system\|leader-election", reason=~"queue-full\|concurrency-limit\|time-out"}` | ✅ | Privileged-tier throttling. The `reason` label picks the fix (queue length vs concurrency shares) |
| CP5 | `apiserver_flowcontrol_rejected_requests_total{flow_schema,priority_level,reason}` + `current_inqueue_requests` + `nominal_limit_seats` + `current_executing_seats` | ✅ | Workload-tier throttling; queue wait time graded by CP-M6 |
| CP6 | `apiserver_request_total{code=~"5.."}` | ✅ | Plus CW `APIServer Total Requests 5XX` |
| CP7 | `apiserver_request_duration_seconds{verb="LIST"}` | ✅ | Never `avg()` across API servers |
| CP8 | `workqueue_depth` / `workqueue_adds_total` (KCM, 1.28+) | ✅/⚠️ | Per-caller QPS still best from audit log (CP14) |
| CP9 | `scheduler_pending_pods{queue="unschedulable"}` (1.28+) | ✅ | Was audit-log-only pre-1.28 (CP18) |
| CP10 | — | ⚠️ | Eviction stalls: events / audit log only |
| CP11 | `apiserver_flowcontrol_current_executing_seats` vs `apiserver_flowcontrol_nominal_limit_seats` | ✅ | Provisioned-mode saturation signal |

## Metric-native checks (CP-M series)

These are graded **directly from public metrics** — no audit-log query. Every metric here is a standard upstream Kubernetes / etcd metric exposed on the public API server `/metrics` endpoint (scrapable with `kubectl get --raw /metrics`) and, where noted, mirrored into the `AWS/EKS` CloudWatch namespace. Metric names follow the [Kubernetes Metrics Reference](https://kubernetes.io/docs/reference/instrumentation/metrics/) and the [EKS Control Plane best practices](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html). They extend CP1–CP11 with signals those checks don't cover.

> **ID namespaces:** `CP-M*` are scorecard checks graded from metrics. They are separate from the `CP1–CP18` **query** IDs in [`queries.md`](queries.md) (which are CloudWatch Logs Insights audit-log queries). Don't conflate the two.

| ID | Check | Pass criteria | Public metric | Severity | Applicability / N/A predicate | Guards | Playbook |
|----|-------|---------------|---------------|----------|-------------------------------|--------|----------|
| CP-M1 | etcd object counts by resource | no single resource type's object count growing abnormally or dominating the store | `apiserver_storage_objects{resource=...}` | High | Metrics-only; N/A if unavailable; correlate with CP1 size. | FP10, FP11 | R-ETCD-1…6 |
| CP-M2 | API server inflight saturation | read-only / mutating inflight not sustained near the concurrency limit | `apiserver_current_inflight_requests{request_kind="readOnly\|mutating"}` | High | Metrics-only; N/A if unavailable. | FP5, FP11 | R-API-1 / R-CP-1 |
| CP-M3 | Large LIST response sizes | p99 LIST response size per resource stable, not driving apiserver/etcd memory pressure | `apiserver_response_sizes` (p99 by `resource`) | Medium | Metrics-only; N/A if unavailable; correlate CP1/CP7. | FP11 | R-API-1 / R-ETCD-3 |
| CP-M4 | Admission webhook health | no sustained webhook rejections; webhook p99 duration < 1 s | `apiserver_admission_webhook_rejection_count`, `apiserver_admission_webhook_admission_duration_seconds` | High | Metrics-only; N/A if unavailable; correlate webhook inventory. | FP11 | R-API-2 |
| CP-M5 | etcd request latency | p99 etcd request duration < 1 s (separates "API slow" from "etcd slow") | `etcd_request_duration_seconds` (p99 by `operation`) | High | Metrics-only; N/A if unavailable. | FP11 | R-ETCD-7 / R-API-1 |
| CP-M6 | APF queue wait time | negligible request wait in `system` / `leader-election`; no rising wait in workload tiers | `apiserver_flowcontrol_request_wait_duration_seconds` (p99 by `priority_level`) | High | Metrics-only; N/A if unavailable. | FP6, FP11 | R-APF-1 / R-APF-2 |
| CP-M7 | API request latency by verb (write path) | p99 < 1 s for GET / CREATE / UPDATE / DELETE (non-LIST/WATCH) | `apiserver_request_duration_seconds` (p99 by `verb`, excluding LIST/WATCH) | High | Metrics-only; N/A if unavailable; CP7 covers LIST — this covers the write path. | FP5, FP11 | R-API-1 / R-API-2 |
| CP-M8 | API server outbound client errors | no sustained 5xx/timeout on the apiserver's calls to aggregated APIs / webhooks | `rest_client_requests_total{code=~"5.."}`, `rest_client_request_duration_seconds` | High | Metrics-only; N/A if unavailable; correlate with CP-M4 and the aggregated-API inventory. | FP5, FP11 | R-API-2 |
| CP-M9 | Watch pressure | registered watchers per resource stable, not growing unbounded | `apiserver_registered_watchers` (by `resource`/`group`) | Medium | Metrics-only; N/A if unavailable; the audit-log companion is the CP23 WATCH-volume query. | FP11 | R-API-1 |

These are pure metrics — no logging dependency — so they can be graded on any cluster with a metrics source (Container Insights, native `AWS/EKS` metrics, Amazon Managed / in-cluster Prometheus, or a third-party connector), even when control-plane audit logging is disabled. CP-M1–CP-M9 all read from the API server `/metrics` endpoint, so they are customer-obtainable on managed EKS — see the AWS [EKS essential metrics guide](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/).

> **CP-M collection order — always query Prometheus when present; do NOT mark N/A after checking CloudWatch only.** CloudWatch (`AWS/EKS` / `ContainerInsights`) vends only a **curated subset** of the API server `/metrics`. Several CP-M metrics are deliberately not in that subset — `apiserver_response_sizes` (CP-M3), `etcd_request_duration_seconds` (CP-M5), `apiserver_flowcontrol_request_wait_duration_seconds` (CP-M6), `rest_client_requests_total` (CP-M8), and `apiserver_registered_watchers` (CP-M9) — but they **are** on the raw API server `/metrics` endpoint and in any full Prometheus scrape. For every CP-M check, attempt sources in this order and only mark ⚪ N/A after **all** are exhausted:
>
> 1. CloudWatch `ListMetrics`/`GetMetricData` in `AWS/EKS` then `ContainerInsights`.
> 2. **If an AMP workspace or in-cluster Prometheus is detected, you MUST query it — every time, for every CP-M metric CloudWatch didn't return.** Prometheus carries the full apiserver metric set (including the histograms CloudWatch omits), so it is the primary source for CP-M3/M5/M6/M7/M8/M9. Run the exact PromQL in [`metric-sources.md` §4.3](metric-sources.md); do not skip Prometheus because CloudWatch already returned *some* CP-M values. If a Prometheus query returns empty for a metric that should exist, that is a **scrape-coverage gap** (histograms dropped / apiserver job not scraped), not a healthy PASS — record it and carry the pipeline recommendation below.
> 3. **Raw API server `/metrics`** via `use_kubectl get --raw /metrics` (grep the metric name) — a primary source when Prometheus is absent; carries the same five metrics CloudWatch omits.
> 4. Only then ⚪ N/A — and the evidence MUST state each source attempted, including the Prometheus query and the raw-`/metrics` result. If step 2 failed on permissions, say "attempted `kubectl get --raw /metrics`, RBAC denied (needs `get` on the `/metrics` nonResourceURL)"; if the runtime tool refused the call, say "`use_kubectl get --raw /metrics` not permitted by the tool" — never "not queried in this pass" (that is a forbidden pending-N/A per FP11).
>
> **A CP-M N/A must carry an actionable coverage recommendation — not a dead end.** When a CP-M metric is absent from every source, the finding is an *observability gap*, and its recommendation states how to close it (pick what fits the cluster's stack):
> - **AMP / Prometheus present but returning nothing for the metric (common for histograms):** the ADOT/Prometheus scrape is dropping the apiserver histogram/high-cardinality series (`apiserver_request_duration_seconds_bucket`, `apiserver_response_sizes_bucket`, `apiserver_admission_webhook_admission_duration_seconds_bucket`, `apiserver_flowcontrol_request_wait_duration_seconds_bucket`) or not scraping the `kubernetes-apiservers` job. Recommend extending the scrape config / relabel keep-list to retain them.
> - **CloudWatch only:** recommend the CloudWatch Observability EKS add-on with enhanced control-plane metrics (still a curated subset — for the five it omits, the raw `/metrics` endpoint or Prometheus is required).
> - **Raw `/metrics` blocked (tool or RBAC):** recommend granting the agent identity `get` on the `/metrics` nonResourceURL, or enabling a Prometheus scrape of the apiserver, so the CP-M set becomes gradable.
>
> Do not gauge-substitute a histogram check to PASS: e.g. `apiserver_flowcontrol_rejected_requests_total = 0` is supporting context for CP-M6 but is **not** the wait-duration metric — grade CP-M6 N/A (with the gap recommendation) and note the zero-rejections as corroborating evidence, don't upgrade it to PASS.

### etcd observability boundary on managed EKS

Only the API server's **etcd-client view** is reachable on managed EKS — `apiserver_storage_size_bytes` / `apiserver_storage_db_total_size_in_bytes` (CP1/CP2), `apiserver_storage_objects` (CP-M1), and `etcd_request_duration_seconds` (CP-M5). The **etcd server internals** — `etcd_server_*` (Raft proposals, leader changes, heartbeat/slow-apply), `etcd_disk_*` (WAL fsync, backend commit), `etcd_mvcc_*` (put/delete/range/keys), `etcd_network_peer_*` (peer RTT), and `etcd_snap_*` (snapshots) — are exposed only on etcd's own `:2379` endpoint, which runs in the AWS-managed account and is **not customer-reachable**. They are intentionally **out of scope** (the same boundary that makes CP-M5 N/A when unavailable); do not add them as checks — they would only ever render N/A. For the etcd leak-detection intent they'd serve, use CP-M1 (object counts), CP3/CP10 (write concentration), and NH-P10 (Failed-pod accumulation) instead. On self-managed or Provisioned control planes, or via an AWS Support engagement, these surface through AWS-side tooling, not this dashboard.

## Manual / AWS-API checks (CPM)

| ID | Check | Severity | Why not from cluster metrics | How to verify / N/A predicate |
|----|-------|----------|----------------------|-------------------------------|
| CPM1 | Control-plane log types enabled | High | AWS-API | `aws eks describe-cluster --query cluster.logging` — at minimum `api` + `audit` for this pillar. AWS read unavailable → N/A citing the required permission. |
| CPM2 | CloudWatch read access | High | IAM | agent role can `logs:StartQuery` / `cloudwatch:GetMetricData` against the cluster log group. Access denial → N/A with the exact error and required permissions. |
| CPM3 | `metrics.eks.amazonaws.com` reachable (EKS 1.28+) | Medium | in-cluster API | `kubectl get --raw "/apis/metrics.eks.amazonaws.com/v1/ksh/container/metrics"` returns data. A webhook blocking the `v1.metrics.eks.amazonaws.com` `APIService` disables scheduler/KCM metrics — check the audit log for that keyword. N/A on unsupported EKS version or explicit API/access error. |

## Relationship to other pillars

- **Observability (O-series)** grades whether a metrics/logging/tracing stack exists; this pillar grades whether the **control plane itself** is saturated. O4/OM4 cross-reference here.
- **Scalability** grades workload/cluster scale limits; control-plane scale limits (APF, etcd, API latency) are graded here.
