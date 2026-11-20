---
name: prometheus-amp-investigation
description: Use this skill when an incident may be explained by metrics that live in Prometheus or Amazon Managed Service for Prometheus (AMP) rather than CloudWatch, especially for Amazon EKS / Kubernetes, container, or custom application workloads. Activate on symptoms such as elevated service error rate or latency, a pod or node that is saturated or restarting, a throughput drop, an HPA that is not scaling, or any RCA where the operator says the signal is in Prometheus/Grafana. It drives the aws-prometheus-mcp server to discover the workspace, list available metrics, and run bounded PromQL instant and range queries, comparing the incident window against a historical baseline. All tools are read-only.
metadata:
  author: mdsherif
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon Managed Service for Prometheus, Amazon EKS, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Investigate with Prometheus / Amazon Managed Service for Prometheus

Use the tools on the connected `aws-prometheus-mcp` MCP server:
`GetAvailableWorkspaces`, `ListMetrics`, `ExecuteQuery`, `ExecuteRangeQuery`,
`GetServerInfo`. Every tool is read-only; this skill never changes customer
state. Scope is incident root-cause analysis, not dashboard authoring or
alert configuration.

## Step 0: Confirm the scope

Use this skill only when the relevant signal is in Prometheus/AMP. If the
metric the incident needs is natively in CloudWatch, use the agent's built-in
CloudWatch retrieval instead. If both exist, Prometheus is the source of truth
for Kubernetes-internal signals (pod/container/kube-state), CloudWatch for
AWS-service and infrastructure signals; say which you used.

## Step 1: Discover before you query (required order)

Never run a PromQL query against a guessed metric name. Establish the ground
truth first, in this order:

1. `GetAvailableWorkspaces` — identify the workspace to query. If more than one
   is returned and the operator has not named one, ask which workspace rather
   than guessing.
2. `GetServerInfo` — confirm the server/workspace is reachable and note which
   workspace you are bound to.
3. `ListMetrics` — confirm the exact metric names that exist before querying.
   Metric naming differs by exporter and scrape config; the metric you expect
   (for example `http_requests_total` vs `http_server_requests_seconds_count`)
   may not be the one that is actually present. Select from what `ListMetrics`
   returns.

If any step fails (no workspace, unreachable server, empty metric list), stop
and report that as the blocker. Do not fabricate metric names or values.

## Step 2: Choose the method — RED for services, USE for resources

Pick the model that matches what you are investigating. Use the metric names
confirmed in Step 1; the queries below are patterns, not literal names.

### RED — request-driven services (APIs, microservices)

- **Rate**: request throughput, e.g. `sum(rate(<requests_total>[5m])) by (service)`
- **Errors**: error ratio, e.g.
  `sum(rate(<requests_total>{code=~"5.."}[5m])) by (service)
   / sum(rate(<requests_total>[5m])) by (service)`
- **Duration**: latency percentile from a histogram, e.g.
  `histogram_quantile(0.99, sum(rate(<request_duration_seconds_bucket>[5m])) by (le, service))`

### USE — resources (nodes, pods, containers, queues)

- **Utilization**: how busy, e.g. CPU from
  `rate(container_cpu_usage_seconds_total[5m])`, memory from
  `container_memory_working_set_bytes`.
- **Saturation**: queued/throttled work, e.g.
  `rate(container_cpu_cfs_throttled_periods_total[5m])`, run-queue depth, or
  memory pressure approaching the limit.
- **Errors**: resource-level errors, e.g. OOMKills, restart counts
  (`kube_pod_container_status_restarts_total`), failed scheduling.

### Standard EKS / Kubernetes metric sources

Match the exporter to the question (verify presence via `ListMetrics`):

| Source | Prefix / examples | Answers |
| --- | --- | --- |
| kube-state-metrics | `kube_pod_*`, `kube_deployment_*`, `kube_node_*`, `kube_hpa_*` | desired vs ready, restarts, HPA state, scheduling |
| node-exporter | `node_cpu_*`, `node_memory_*`, `node_filesystem_*`, `node_load*` | node utilization and saturation |
| kubelet / cAdvisor | `container_cpu_*`, `container_memory_*`, `container_network_*` | per-container/pod resource use |
| apiserver / control plane | `apiserver_request_*`, `etcd_*` | control-plane latency and errors |
| application exporters | workload-specific | RED signals for the service |

## Step 3: Baseline against history

A single incident-window number is not evidence. For any metric you flag,
compare the incident window to the same window on a prior cycle (yesterday, or
same weekday last week for weekly-seasonal workloads) using `ExecuteRangeQuery`
over both windows. State the delta and whether the current value is actually
anomalous versus normal variation. PromQL `offset` (e.g. `... offset 1d`,
`... offset 7d`) is the mechanism; keep the metric and label matchers identical
between current and offset queries so the comparison is valid.

## Step 4: Query hygiene (bound every query)

Unbounded or high-cardinality PromQL is the main failure mode. Before running:

- **Bounded time ranges.** Scope `ExecuteRangeQuery` to the incident window plus
  a short lead-in, not days of history. Instant queries (`ExecuteQuery`) for a
  point-in-time check.
- **Sensible step size.** Match step to range: a sub-minute step over a multi-day
  range returns an enormous matrix. As a rule of thumb target a few hundred
  points, not tens of thousands.
- **Aggregate and constrain cardinality.** Prefer `sum(...) by (<low-cardinality
  label>)` over returning every series. Never run a bare selector that matches a
  high-cardinality metric across all labels. Avoid grouping by unbounded labels
  such as `pod`, `instance`, or `id` without a narrowing selector first.
- **Always `rate()` counters** over an interval ≥ 4x the scrape interval; never
  graph a raw `_total` counter.

If a query would be expensive or broad, narrow it (tighter selector, coarser
step, or an aggregation) before calling the tool.

## Step 5: Report

- State the workspace queried and that the data is Prometheus/AMP-sourced.
- For each finding: the exact PromQL run, the observed value, and the baseline
  it was compared against (with the delta).
- Separate Prometheus-sourced findings from any CloudWatch-sourced ones.
- Name the coverage boundary: metrics checked, time window, and what was not
  queried. Absence of a metric from `ListMetrics` is a gap to report, not a
  value to assume.

## Limitations

- All tools are read-only. Do not attempt to write, remote-write, or modify the
  workspace; the server does not expose those operations.
- The skill is guidance only. Without the `aws-prometheus-mcp` server registered
  and its tools allowlisted, none of the referenced tools are callable.
- Metric availability depends entirely on the customer's scrape configuration;
  this skill reports what exists rather than assuming a standard set.
- PromQL evaluation is bounded by the workspace's own query limits; a query that
  is rejected or truncated must be narrowed, not retried unchanged.

## Prerequisites

Requires the `aws-prometheus-mcp` MCP server registered in the Agent Space with
its tools allowlisted, and an existing Amazon Managed Service for Prometheus
workspace supplied to the server. The server and its deployment instructions are
in this repository at `mcp/aws-prometheus-mcp/`. If the server is not registered
or no workspace is reachable, report that as the blocker rather than guessing at
metric values.
