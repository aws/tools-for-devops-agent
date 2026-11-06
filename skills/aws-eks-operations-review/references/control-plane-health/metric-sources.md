# Metric and log sources the skill consumes

The skill is designed around the reality that customers run EKS observability in multiple shapes. Audit logs alone give you correlation but coarse resolution; Prometheus-style metrics give you fine resolution but no per-request detail. The skill **fans out across whatever sources are available** and merges the answers.

This file documents:

1. The four signal categories the skill cares about.
2. Each source we pull from and which signals it carries.
3. Source-detection logic — how the skill discovers what's enabled in a cluster.
4. Source-specific queries (PromQL for the Prometheus-style sources, CW Insights for audit logs, MetricMath for CloudWatch).

## Contents

- 1. Signal categories
- 2. Source matrix — what each source carries
- 3. Source detection
- 4. Source-specific queries (4.1 CW Logs Insights · 4.2 Container Insights / native EKS · 4.3 AMP / in-cluster Prometheus · 4.4 Datadog · 4.5 New Relic, Dynatrace, Splunk · 4.6 `metrics.eks.amazonaws.com` API group)
- 5. Source-cross-validation rules
- 6. What's *not* a source
- 7. Configuration

## 1. Signal categories

Every check in [`thresholds.md`](thresholds.md) maps to one of these categories. Different sources surface them with different latency and granularity.

| Category | Headline question | Primary risk if breached |
|----------|------------------|--------------------------|
| **etcd pressure** | Is etcd close to its 8 GB ceiling? Is something filling it? | Cluster goes read-only — full-stop outage. |
| **API server throttling (APF)** | Are requests being rejected? Is the rejection in `system`/`leader-election` priority? | Operators fail, controllers fall behind, cluster appears flaky. |
| **API server health** | 5xx rate, healthz, p99 LIST latency. | Customer kubectl / CI/CD breaks. |
| **KCM / scheduler backpressure** | Are controllers being client-side throttled at `kubeAPIQPS=20`? Are pods unschedulable? | Deployments stall, autoscaling fails. |

## 2. Source matrix — what each source carries

| Source | etcd | APF | API health | KCM/scheduler | How the agent reads it |
|--------|:----:|:---:|:----------:|:-------------:|------------------------|
| **CloudWatch Logs Insights** (audit log) | partial — write rate per resource (CP10) | partial — 429 counts (CP7, CP13) | yes — 5xx (CP8), healthz (CP12), LIST latency (CP2/CP3/CP4) | yes — per-controller QPS (CP14), unscheduled pods (CP18) | `logs:StartQuery` |
| **CloudWatch Container Insights** (enhanced observability for EKS) | yes — `apiserver_storage_db_total_size_in_bytes` | yes — `apiserver_flowcontrol_*` | yes — `apiserver_request_*` | yes — `kube_*` metrics | `cloudwatch:GetMetricData` |
| **CloudWatch native control-plane metrics** (EKS 1.28+, free) | yes — control-plane etcd metrics | yes | yes | yes | `cloudwatch:GetMetricData` |
| **Amazon Managed Service for Prometheus** | yes — full etcd metric set | yes — full APF metric set | yes — full request metric set | yes | PromQL via AMP query API |
| **In-cluster Prometheus + Grafana** | yes | yes | yes | yes | PromQL via the customer's Prometheus endpoint |
| **Datadog** | yes — `kubernetes.apiserver.*`, etcd dashboard | yes | yes | yes | DevOps Agent's existing Datadog connector |
| **New Relic** | yes — Kubernetes integration | yes | yes | yes | DevOps Agent's existing New Relic connector |
| **Dynatrace** | yes — Kubernetes monitoring | yes | yes | yes | DevOps Agent's existing Dynatrace connector |
| **Splunk Observability Cloud** | yes — Kubernetes Navigator | yes | yes | yes | DevOps Agent's existing Splunk connector |
| **EKS `/metrics` raw endpoint** (`kubectl get --raw /metrics`) | yes — apiserver storage metrics | yes — full APF metric set | yes — full request metric set | API server only (scheduler/KCM run in the AWS-managed account) | escape hatch for the customer to verify a finding |
| **`metrics.eks.amazonaws.com` API group** (EKS **1.28+**) | no | no | no | yes — `kube-scheduler` (`/v1/ksh/...`) and `kube-controller-manager` (`/v1/kcm/...`) | `kubectl get --raw` against the ksh/kcm endpoints — the public path for scheduler/KCM metrics that were previously audit-log-only |

> **Why fan out instead of pick one?** Customers rarely have just one. A typical SaaS team has Container Insights *and* Datadog, or Managed Prometheus *and* in-cluster Prom. Each source has different lag, different retention, and different gaps. Reading multiple lets the skill cross-check (an etcd spike that shows up in Datadog but not Container Insights is usually a collector problem, not a real spike).

## 3. Source detection

When the agent starts, it probes each source and records which are usable for this cluster. This is part of `cp_health_overview`.

```
detect_sources(cluster_arn, region):
  sources = []

  # CloudWatch — always check
  if cloudwatch:ListMetrics returns metrics in namespace "ContainerInsights"
       with dimension {ClusterName: <name>}:
    sources.append("container_insights")

  if cloudwatch:ListMetrics returns metrics in namespace "AWS/EKS"
       with metric "apiserver_storage_db_total_size_in_bytes":
    sources.append("cloudwatch_native_eks_metrics")

  # CW Logs — confirm log group + audit stream exist
  if logs:DescribeLogStreams("/aws/eks/{cluster}/cluster") includes
       "kube-apiserver-audit":
    sources.append("cloudwatch_logs_insights")

  # Managed Prometheus — check workspace association tag or env config
  if AMP workspace is configured for this cluster:
    sources.append("amp")

  # Third-party — check the agent space's connector registry
  for connector in agent_space.connectors():
    if connector.type in (datadog, newrelic, dynatrace, splunk):
      sources.append(connector.type)

  return sources
```

Source detection results are surfaced in the `cp_health_overview` response so the agent can tell the user which sources contributed to the verdict and which were missing.

```json
{
  "sources_detected": ["cloudwatch_logs_insights", "container_insights", "datadog"],
  "sources_missing": ["amp", "in_cluster_prom"],
  "coverage": {
    "etcd": "container_insights, datadog (cross-validated)",
    "apf": "container_insights, datadog",
    "api_health": "cloudwatch_logs_insights, container_insights, datadog",
    "kcm_scheduler": "cloudwatch_logs_insights, datadog"
  }
}
```

## 4. Source-specific queries

### 4.1 CloudWatch Logs Insights

The CW Insights queries are staged to keep source detection, core execution, and diagnostics out of context at the same time: [`queries-cp01-cp09.md`](queries-cp01-cp09.md), [`queries-cp10-cp13.md`](queries-cp10-cp13.md), and [`queries-cp14-cp18.md`](queries-cp14-cp18.md) are the ordered core; [`queries-cp19-cp25-diagnostics.md`](queries-cp19-cp25-diagnostics.md) loads only when triggered. They run against `/aws/eks/{cluster}/cluster`.

### 4.2 CloudWatch Container Insights / native EKS metrics

CloudWatch metric IDs the skill reads. Available with the [Amazon CloudWatch Observability EKS Add-on](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/container-insights-detailed-metrics.html) (Container Insights with enhanced observability) and, on EKS 1.28+, with the [native CloudWatch control-plane metrics](https://aws.amazon.com/blogs/containers/proactive-amazon-eks-monitoring-with-amazon-cloudwatch-operator-and-aws-control-plane-metrics/) at no extra cost.

| Signal | Metric | Namespace | Use |
|--------|--------|-----------|-----|
| etcd db size | `apiserver_storage_db_total_size_in_bytes` | `ContainerInsights` | Compare against the 8 GB ceiling. |
| etcd in-use size | `apiserver_storage_db_total_size_in_use_in_bytes` | `ContainerInsights` | After-compaction size; the gap to the on-disk size shows defrag headroom. |
| API request rate | `apiserver_request_total` | `ContainerInsights` | Total request volume — use `Sum` per minute. |
| API latency histogram | `apiserver_request_duration_seconds_bucket` | `ContainerInsights` | Build a heatmap. **Never `avg()` across instances** — see [Control Plane Monitoring guide](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html). |
| APF concurrency limit | `apiserver_flowcontrol_nominal_limit_seats` | `ContainerInsights` | Per-priority capacity. |
| APF queue depth | `apiserver_flowcontrol_current_inqueue_requests` | `ContainerInsights` | Non-zero in non-`workload-low` priority = warning sign. |
| APF rejection count | `apiserver_flowcontrol_rejected_requests_total` | `ContainerInsights` | Critical when non-zero in `system` or `leader-election`. |
| Unschedulable pods | `scheduler_pending_pods` | `ContainerInsights` | Active / backoff / unschedulable by status. |

### 4.3 Amazon Managed Service for Prometheus / in-cluster Prometheus

PromQL the skill runs against any Prometheus-compatible endpoint. Same metric names work for in-cluster Prom, AMP, and the EKS `/metrics` raw endpoint.

#### etcd

All names below are exposed by the public API server `/metrics` endpoint (`apiserver_storage_*`, `etcd_request_duration_seconds`). The etcd servers themselves are not customer-scrapable on EKS, so `etcd_server_*` / `etcd_disk_*` are **not** used here.

```promql
# Current logical size as % of quota — 8 GB (Standard) or 16 GB (Provisioned Control Plane XL/2XL/4XL)
100 * apiserver_storage_size_bytes / (8 * 1024 * 1024 * 1024)

# 7-day growth rate
100 * (
  apiserver_storage_size_bytes
  - apiserver_storage_size_bytes offset 7d
) / apiserver_storage_size_bytes offset 7d

# CP-M1 — object counts by resource (what is in etcd) + 7-day growth per resource
apiserver_storage_objects
100 * (
  apiserver_storage_objects - apiserver_storage_objects offset 7d
) / apiserver_storage_objects offset 7d

# CP-M5 — etcd request latency p99 by operation (separates read/range from write/txn)
histogram_quantile(0.99,
  sum by (le, operation) (rate(etcd_request_duration_seconds_bucket[5m])))
```

#### APF

```promql
# Non-zero rejections in critical priority levels = page
sum by (priority_level) (
  rate(apiserver_flowcontrol_rejected_requests_total{
    priority_level=~"system|leader-election|workload-high"
  }[5m])
)

# Concurrency utilization per priority
100 *
  apiserver_flowcontrol_current_executing_requests
  / apiserver_flowcontrol_nominal_limit_seats

# Queue depth by priority
sum by (priority_level) (apiserver_flowcontrol_current_inqueue_requests)

# Rejections broken out by reason — reason picks the fix (queue-full vs concurrency-limit vs time-out)
sum by (priority_level, flow_schema, reason) (
  rate(apiserver_flowcontrol_rejected_requests_total[5m])
)

# CP-M6 — request wait time in queue, p99 by priority (early warning before rejections)
histogram_quantile(0.99,
  sum by (le, priority_level) (
    rate(apiserver_flowcontrol_request_wait_duration_seconds_bucket[5m])
  )
)
```

#### API server health

```promql
# 5xx rate
sum(rate(apiserver_request_total{code=~"5.."}[5m]))

# 429 rate by user agent
sum by (user_agent) (
  rate(apiserver_request_total{code="429"}[5m])
)

# LIST p99 latency by resource — Kubernetes SLO breach when > 1s
histogram_quantile(0.99,
  sum by (le, resource) (
    rate(apiserver_request_duration_seconds_bucket{
      verb="LIST", subresource!="status"
    }[5m])
  )
)

# CP-M2 — inflight saturation (read-only vs mutating), watch for sustained highs
apiserver_current_inflight_requests

# CP-M3 — large LIST response sizes, p99 bytes by resource (drives apiserver/etcd memory pressure)
histogram_quantile(0.99,
  sum by (le, resource) (rate(apiserver_response_sizes_bucket[5m])))

# CP-M4 — admission webhook rejections + latency (a slow/failing webhook blocks pod creation)
sum by (name, operation) (rate(apiserver_admission_webhook_rejection_count[5m]))
histogram_quantile(0.99,
  sum by (le, name) (rate(apiserver_admission_webhook_admission_duration_seconds_bucket[5m])))
```

#### KCM / scheduler

```promql
# Per-controller request rate — > 18 / sec = client-side throttled
sum by (controller_name) (
  rate(workqueue_adds_total[5m])
)

# Workqueue depth growing = controller falling behind
sum by (name) (workqueue_depth)

# Scheduler unschedulable pods
scheduler_pending_pods{queue="unschedulable"}

# Scheduler attempt p99
histogram_quantile(0.99,
  sum by (le) (rate(scheduler_scheduling_attempt_duration_seconds_bucket[5m]))
)
```

### 4.4 Datadog

Datadog's Kubernetes integration carries the same control-plane metrics under `kubernetes.apiserver.*` and `kubernetes.etcd.*` ([Datadog Kubernetes integration](https://docs.datadoghq.com/integrations/kubernetes/) — third-party docs, customer-owned).

The agent reads Datadog through DevOps Agent's existing Datadog connector. The skill does not call Datadog APIs directly — it formats the Datadog query and asks the agent to dispatch it.

Example metric mappings the skill emits:

| Signal | Datadog metric |
|--------|---------------|
| etcd db size | `kubernetes.etcd.db.total_size_in_bytes` |
| API request rate | `kubernetes.apiserver.requests.total` |
| 5xx rate | `kubernetes.apiserver.requests.total` filtered by `code:5*` |
| APF rejections | `kubernetes.apiserver.flowcontrol.rejected_requests.total` |
| LIST p99 latency | `kubernetes.apiserver.requests.duration.99percentile` filtered by `verb:list` |

### 4.5 New Relic, Dynatrace, Splunk

DevOps Agent's connector list ([About AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html)) includes New Relic, Dynatrace, and Splunk natively. Each carries the same Kubernetes control-plane metrics under their own naming. The skill emits a query manifest for each and lets the agent's connector handle the actual transport.

The control-plane query set this manifest is built from lives in the staged core and diagnostic query files in this directory; the agent issues the equivalent query through whichever observability connector is configured.

### 4.6 `metrics.eks.amazonaws.com` API group (EKS 1.28+)

`kube-scheduler` and `kube-controller-manager` run in the AWS-managed account, so their metrics are **not** on the API server `/metrics` endpoint. On **EKS 1.28+**, Amazon EKS exposes them under the `metrics.eks.amazonaws.com` API group, scrapable directly with `kubectl get --raw` or a Prometheus scrape job ([raw-metrics userguide](https://docs.aws.amazon.com/eks/latest/userguide/view-raw-metrics.html)). This closes the pre-1.28 gap where checks CP8 (KCM QPS) and CP9 (scheduler backpressure) were gradable only from audit-log queries (CP14/CP18).

```bash
# kube-scheduler
kubectl get --raw "/apis/metrics.eks.amazonaws.com/v1/ksh/container/metrics"
# kube-scheduler pod resource requests/limits (separate, larger endpoint)
kubectl get --raw "/apis/metrics.eks.amazonaws.com/v1/ksh/container/resourcemetrics"
# kube-controller-manager
kubectl get --raw "/apis/metrics.eks.amazonaws.com/v1/kcm/container/metrics"
```

| Signal | Metric | Component |
|--------|--------|-----------|
| Unschedulable pods | `scheduler_pending_pods{queue="unschedulable"}` | scheduler |
| Scheduling throughput | `scheduler_schedule_attempts_total` | scheduler |
| Scheduling latency | `scheduler_scheduling_attempt_duration_seconds*`, `scheduler_pod_scheduling_sli_duration_seconds*` | scheduler |
| Preemption | `scheduler_preemption_attempts_total`, `scheduler_preemption_victims` | scheduler |
| Controller queue depth | `workqueue_depth` | controller-manager |
| Controller throughput | `workqueue_adds_total` | controller-manager |
| Controller queue wait / work time | `workqueue_queue_duration_seconds*`, `workqueue_work_duration_seconds*` | controller-manager |

Scraping requires `get` on the `kcm/metrics` and `ksh/metrics` resources in the `metrics.eks.amazonaws.com` API group. A webhook that blocks creation of the `v1.metrics.eks.amazonaws.com` `APIService` disables the endpoint — verify by searching the `kube-apiserver` audit log for the `v1.metrics.eks.amazonaws.com` keyword.

## 5. Source-cross-validation rules

When two or more sources are available for the same signal, the skill cross-validates and surfaces disagreement as its own finding.

| Rule | Action |
|------|--------|
| Two sources agree within 10% | Use the value, mark `confidence: high`. |
| Two sources disagree by > 10% | Surface both values, mark `confidence: low`, recommend the customer check collector health. |
| One source missing for a signal where it should be present | Note in `sources_missing` and mark the signal `confidence: medium` (still actionable, but lower trust). |
| All sources missing for a signal | Mark the signal `unknown` and recommend enabling at least one source. |

## 6. What's *not* a source

The skill deliberately does not consume:

- Internal AWS service-team tools — these are not customer-accessible.
- Cluster autoscaler / Karpenter logs at the data-plane level — out of scope for control-plane health.
- Application logs — a different skill's responsibility.

## 7. Configuration

Source enablement is automatic — no config required. To force a subset (e.g., for cost reasons during a long backfill), use the `sources_override` input on `cp_health_overview`:

```json
{
  "cluster_arn": "...",
  "region": "...",
  "sources_override": ["container_insights", "cloudwatch_logs_insights"]
}
```
