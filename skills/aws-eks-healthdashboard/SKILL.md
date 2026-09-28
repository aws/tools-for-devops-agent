---
name: aws-eks-healthdashboard
description: Produces an Amazon EKS health dashboard — a point-in-time snapshot of
  control-plane health (etcd, API Priority & Fairness, API-server latency/5xx,
  kube-controller-manager, scheduler, eviction) and node / data-plane health
  (node conditions, node & pod utilization, EC2 status, ENA network allowances,
  EBS volume performance, NAT, CoreDNS, Karpenter, and AWS-side nodegroup /
  registration facts). Reviews all available metrics and logs from CloudWatch
  Logs Insights, CloudWatch metrics / Container Insights, native EKS
  control-plane metrics, and any connected Prometheus / Datadog / New Relic /
  Dynatrace / Splunk source. Read-only. Triggers on: "EKS health dashboard",
  "EKS control plane health", "EKS node health", "is my EKS cluster healthy",
  "check EKS cluster health", "EKS etcd / APF / API latency", "EKS node status".
metadata:
  version: "1.0.0"
---

# EKS Health Dashboard — DevOps Agent Skill

## What this skill is

A focused, **read-only** EKS health monitor. It answers "is this cluster healthy right now?" across
three domains and grades every signal it can observe:

1. **Cluster, Version & Add-on Health** — cluster status + `health.issues`, Kubernetes version &
   **extended-support** state, EKS managed add-on health (`DEGRADED`/failed + `health.issues`),
   whether core components (CoreDNS/kube-proxy/VPC CNI/CSI) are actually running, EKS Cluster
   Insights (upgrade/config/rollback), and Node Monitoring Agent enablement (CA-series).
2. **Control Plane Health** — etcd size/growth, APF throttling, API-server 5xx + LIST latency,
   write-path/verb latency, apiserver outbound-client errors, watch pressure, KCM backpressure,
   scheduler lag, eviction stalls (CP1–CP11 + the metric-native CP-M1–CP-M9). The control plane is
   AWS-managed, so these come from CloudWatch Logs Insights (audit log) + CloudWatch metrics, never
   kubectl.
3. **Node & Data-Plane Health** — node conditions, node & pod utilization, EC2 instance status,
   ENA network allowances, EBS volume performance, NAT gateway, CoreDNS, Karpenter, Node Monitoring
   Agent conditions, a workload/pod health rollup, and the AWS-side nodegroup/registration facts
   (NH-series).

It **reviews all available metrics**: it detects which observability sources are enabled and fans
out across them (CloudWatch Logs, Container Insights, native EKS metrics, AMP / in-cluster
Prometheus, Datadog / New Relic / Dynatrace / Splunk), cross-validating where more than one covers
a signal. Output is a **health dashboard artifact**, not a best-practices audit — for the full
9-pillar review use the `aws-eks-operations-review` skill.

> Read this skill and the reference files it names **in full** — do not distill/summarize them; the
> queries, thresholds, and check definitions live in the reference files. Load each with the
> runtime's resource-reading tool (in AWS DevOps Agent, `read_skill_resource`).

## Tools

- `use_kubectl` — node conditions & version (`kubectl get nodes -o json`, read-only) **and the raw API server metrics for the CP-M checks** (`get --raw /metrics`) when CloudWatch lacks a CP-M metric.
- `use_aws` — CloudWatch metrics (`cloudwatch:GetMetricData` / `ListMetrics`), EKS/EC2/AutoScaling `describe*`, Cluster Insights.
- `query_cloudwatch_logs` — the CP1–CP18 Logs Insights queries against `/aws/eks/{cluster}/cluster`.
- `create_or_update_artifact` — write/refresh the dashboard as a single Markdown **`text`** element (see [`references/report-format.md`](references/report-format.md) → *Artifact element types*).

## Workflow

### Step 0 — Confirm the cluster
Confirm cluster name + region + account before collecting anything (restate it back). Never assume the current context.

### Step 1 — Detect observability sources
Probe what's enabled per [`references/metric-sources.md`](references/metric-sources.md) §3 (CloudWatch Logs audit stream, Container Insights, native `AWS/EKS` metrics, AMP / in-cluster Prometheus, third-party connectors, **and — for the NH-P/NET depth checks — kube-state-metrics, prometheus-node-exporter, and the VPC CNI metrics helper**). Record `sources_detected` / `sources_missing`. This drives which checks are gradable vs ⚪ N/A. An absent KSM / node-exporter / CNI-metrics-helper source makes its dependent checks ⚪ N/A **and** is itself an observability-gap finding — never a silent skip.

### Step 2 — Cluster, version & add-on health
Grade the **CA-series** from [`references/cluster-addon-health.md`](references/cluster-addon-health.md) via `use_aws` (+ `use_kubectl` for CA9): cluster `status` + `health.issues` (CA1–CA2), control-plane logging (CA3), Kubernetes version & **extended-support** state (CA4–CA5), EKS managed add-on health incl. `DEGRADED`/failed + `health.issues` codes and version compatibility (CA6–CA8), core components **and every installed add-on/controller** (managed or self-managed/Helm) actually running (CA9, CA14), EKS Cluster Insights — upgrade/config/rollback (CA10–CA12), and Node Monitoring Agent enablement (CA13). **Cluster-Insights findings are reported as CA10–CA12 — never as `CP*` checks.**

### Step 3 — Control Plane Health
Grade **CP1–CP11 + CP-M1–CP-M9** from [`references/control-plane-health.md`](references/control-plane-health.md):
- If control-plane logging is enabled, run the CP1–CP18 Logs Insights queries ([`references/queries.md`](references/queries.md)) via `query_cloudwatch_logs`, **and** pull control-plane metrics via `use_aws` `GetMetricData`.
- If logging is disabled, flag it as a finding and still grade from metrics (native `AWS/EKS` metrics / Container Insights) and any Prometheus / connector.
- **Always query Prometheus/AMP for metrics when it's present.** If Step 1 detected an AMP workspace or in-cluster Prometheus, you MUST run the metric-native queries against it for every CP-M and NH-P check — Prometheus carries the full apiserver metric set (including the histograms CloudWatch omits). Do not rely on CloudWatch alone, and do not skip Prometheus because CloudWatch returned partial values.
- **For the CP-M checks, follow the source-fallback order** in [`references/control-plane-health.md`](references/control-plane-health.md) (CloudWatch → **Prometheus/AMP if detected (mandatory)** → raw API server `/metrics` via `use_kubectl get --raw /metrics` → N/A). CP-M3/M5/M6/M7/M8/M9 are absent from CloudWatch's curated subset, so pull them from Prometheus or the raw `/metrics` endpoint before marking ⚪ N/A; a metric absent from CloudWatch is **not** an N/A until Prometheus and `/metrics` were attempted. A Prometheus query that returns empty for a metric that should exist is a **scrape-coverage gap** (histograms dropped / apiserver job not scraped), not a PASS.
- Follow the investigation procedures in [`references/procedures.md`](references/procedures.md) (`health_overview` first, then drill into non-`ok` signals); evaluate against [`references/thresholds.md`](references/thresholds.md).
- Apply the grading guards in [`references/grading-guards.md`](references/grading-guards.md) before fixing any verdict — an empty query / no-datapoint result is *unknown*, never an automatic PASS (FP11); a 429 spike is not "scale the control plane" (FP6). Record the applied guard ID and a confidence level with each status.
- Run CP19–CP25 only when a matching auth / write-path / change-correlation / WATCH / mutation-attribution / anonymous-access signal appears — they are triggered diagnostics, not scorecard rows.
- Mark a check ⚪ N/A only after attempting and finding no source carries the signal — never "pending."
- **CP checks are CP1–CP11.** Cluster-Insights / upgrade items (kube-proxy skew, AL2, kubelet skew, addon compat) are **not** CP checks.

### Step 4 — Node & Data-Plane Health
Grade the **NH-series** from [`references/node-health.md`](references/node-health.md): node conditions + Node Monitoring Agent conditions (`use_kubectl`), node/pod utilization + EC2/ENA/EBS/NAT/CoreDNS/Karpenter metrics (`use_aws`), the workload/pod health rollup (CrashLoopBackOff/ImagePullBackOff/Pending/OOMKilled/Warning events), and AWS-side nodegroup/registration facts. Also grade the **NH-P depth checks** (NH-P1/P2/P6/P7/P9/P10/P11 — kubelet running pods, true allocatable headroom, `MemAvailable`, NIC errors, node `Ready=Unknown`, Failed-pod accumulation, PVC Pending) and the **NET series** (NET-P1/P2/P3 — VPC CNI IP exhaustion / allocation errors / stuck IPAMD). Detect conditional sources (ENA ethtool, CoreDNS Prometheus, Karpenter, **kube-state-metrics, node-exporter, cni-metrics-helper**) and mark absent ones ⚪ N/A (the absence is itself an observability gap).

### Step 5 — Produce the dashboard
Write the artifact per [`references/report-format.md`](references/report-format.md): header, overall health, sources & coverage, Control Plane scorecard (CP + CP-M), Node & Data-Plane scorecard (NH + NH-P + NET), detailed findings for every ❌/⚠️ with remediation + AWS link, recommended CloudWatch alarms, and "what was not assessed." Refresh a same-day artifact instead of duplicating. Default `eks-health-{cluster}-{date}.md`.

For each ❌/⚠️ finding, follow the **findings-analysis contract** in [`references/report-format.md`](references/report-format.md) §7 — *reason* from the observed evidence (what it means, symptoms, ranked probable causes, cascade risk, confidence) using your own EKS knowledge; do not recite a canned definition, and never invent thresholds or metric names (those come only from the reference files).

Emit the dashboard as **one Markdown `text` artifact element** — Markdown `##`/`###` headings and `|...|` pipe tables render natively inside a `text` element, so the whole report (scorecards included) is one `text` block. The artifact platform supports only four element types — **`text`, `chart`, `table`, `topology`** — and renders anything else as *"Unknown artifact element type."* **Never emit a `section` element**; use Markdown headings for section structure instead. Only use `chart`, `table`, or `topology` as standalone elements when you deliberately need that specific widget and populate its exact required schema — otherwise keep tabular data as Markdown tables inside the `text` element.

## Constraints

- **Read-only.** No mutating `use_kubectl` verbs, no destructive `use_aws` calls. Remediations are recommendations drafted for human approval.
- **Never print Secret values** — metadata only.
- Every status cites its query ID / metric; ⚪ N/A always carries the real reason. Never guess or silently skip.
- Customer-facing output uses descriptive status labels — no internal severity numbers.

## Reference files

| File | Read it when |
|------|--------------|
| [`references/cluster-addon-health.md`](references/cluster-addon-health.md) | Grading CA1–CA13 — cluster status/health issues, version & extended support, add-on health, core components running, Cluster Insights, node-monitoring enablement. |
| [`references/control-plane-health.md`](references/control-plane-health.md) | Grading CP1–CP11 + CP-M1–CP-M9 — the control-plane check set, data sources, the etcd observability boundary, and decision tree. |
| [`references/queries.md`](references/queries.md) | Running the CloudWatch Logs Insights queries — CP1–CP18 (core) + CP19–CP25 (auth denials, write-path latency, change-correlation, watch volume, mutation attribution, anonymous access). |
| [`references/metric-sources.md`](references/metric-sources.md) | Detecting sources and getting per-source queries (CW Insights / Container Insights / PromQL / connectors / `metrics.eks.amazonaws.com` / kube-state-metrics / node-exporter / VPC CNI metrics helper). |
| [`references/thresholds.md`](references/thresholds.md) | Control-plane thresholds + the CP-M series + override format + cross-validation rules. |
| [`references/grading-guards.md`](references/grading-guards.md) | **Before fixing any CA/CP/CP-M/CPM/NH verdict** — the false-positive controls (FP1–FP12), the empty-result rule, and the confidence contract. |
| [`references/procedures.md`](references/procedures.md) | The investigation procedures (`health_overview`, `etcd_pressure`, `apf_health`, …). |
| [`references/node-health.md`](references/node-health.md) | Grading the NH-series + the NH-P depth checks (KSM/node-exporter/kubelet) + the NET series (VPC CNI IP health). |
| [`references/remediations-etcd.md`](references/remediations-etcd.md), [`references/remediations-apf.md`](references/remediations-apf.md), [`references/remediations-apiserver.md`](references/remediations-apiserver.md) | Control-plane remediation playbooks for a FAIL (R-ETCD-* / R-APF-* / R-API-*/R-KCM-*/R-SCHED-*/R-EVICT-*/R-CP-*). |
| [`references/alerting.md`](references/alerting.md) | Customer-facing alert language / label mapping (and the optional continuous-monitoring mode). |
| [`references/report-format.md`](references/report-format.md) | Writing the dashboard artifact. |

## Non-goals

- **Not a best-practices audit.** For the full 9-pillar operations review (Security, Cost, Scalability, etc.), use `aws-eks-operations-review`.
- **No writes.** Read-only by design; remediations are drafted, not applied.
- **Detection, not delivery.** This produces a point-in-time dashboard; continuous alert fan-out is a separate operating mode (see `alerting.md`).

## Source attribution

- [EKS Control Plane Monitoring](https://docs.aws.amazon.com/eks/latest/best-practices/control_plane_monitoring.html)
- [EKS best practices — Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html)
- [AWS EKS essential metrics guide](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/) — the source→metric authority for CP-M, NH-P, and NET checks
- [VPC CNI — monitor IP address inventory](https://aws.github.io/aws-eks-best-practices/networking/vpc-cni/#monitor-ip-address-inventory)
- [AWS recommended alarms — EKS](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
