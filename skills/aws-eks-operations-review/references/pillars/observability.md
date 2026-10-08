# Pillar: Observability

Metrics, logging, tracing coverage, and workload-health signals. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Application — Observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html) · [Control Plane monitoring](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html)

Reads discovery areas: 7 PODS, 19 EVENTS, 29 OBSERVABILITY.

## Currency framing

- Control-plane *metrics* monitoring (API latency, etcd size, APF) is graded by the **Control Plane Health** pillar ([`control-plane.md`](control-plane.md)) — reference it rather than re-grading here.
- This pillar grades whether the cluster has a working metrics / logging / tracing stack and surfaces live health signals.

## Checks (O-series)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| O1 | Metrics Server present | `features.observability.metrics_server` | Ready | High |
| O2 | Metrics pipeline present | `features.observability` | Prometheus/AMP or CloudWatch Container Insights detected | High |
| O3 | kube-state-metrics present | `features.observability.kube_state_metrics` | detected | Medium |
| O4 | Logging pipeline present | `features.observability` | Fluent Bit/Fluentd/Vector or CloudWatch agent detected | High |
| O5 | Tracing present | `features.observability` | ADOT/OTel or X-Ray detected | Low |
| O6 | Alerting present | `features.observability.alertmanager` (or CW alarms) | alerting configured | Medium |
| O7 | No OOMKilled events | `pods_oomkilled` | zero in window | High |
| O8 | No CrashLoop / ImagePull | `pods_crashloop`, `pods_imagepull` | zero | High |
| O9 | No FailedScheduling / warning storms | area 19 warning events | no sustained FailedScheduling/BackOff/Unhealthy/FailedMount | Medium |
| O10 | CNI metrics helper (IP monitoring) | `features.observability.cni_metrics_helper` | present | Low |
| O11 | GPU metrics (DCGM) | `features.observability.dcgm_exporter` | present when GPU nodes exist | Low |

## Manual / AWS-API checks (OM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| OM1 | Control-plane log types enabled | AWS-API | `aws eks describe-cluster --query cluster.logging` (api/audit/authenticator/controllerManager/scheduler). |
| OM2 | Container Insights enabled | AWS-API / CW | CloudWatch Container Insights for EKS active. |
| OM3 | App-level metrics exposed | app code | workloads expose Prometheus metrics endpoints. |
| OM4 | Control-plane saturation review | metrics | grade the **Control Plane Health** pillar ([`control-plane.md`](control-plane.md)) for etcd/APF/latency. |

## CloudWatch data (7-day, when available)

When Container Insights / control-plane logging is enabled (collected in Step 5b), grade these data-plane and historical signals against the thresholds in [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md). They corroborate the live O-series signals above and feed Performance / Cost / data-plane Resilience:

| ID | Signal | Source | Threshold ref |
|----|--------|--------|---------------|
| O12 | Node/pod CPU/memory/filesystem utilization (7-day avg & max) | Container Insights | `metrics-thresholds.md` § node / pod metrics |
| O13 | Container restart trend (7-day) | Container Insights `pod_number_of_container_restarts` | `metrics-thresholds.md` § pod metrics |
| O14 | Control-plane log error patterns (`ERROR`/`429`/`OOMKilled`/`FailedScheduling`/`Evicted`) | CloudWatch Logs | `metrics-thresholds.md` § log patterns |
| O15 | EC2 node health (`StatusCheckFailed`, `CPUUtilization`) | `AWS/EC2` | `metrics-thresholds.md` § EC2 node metrics |
| O16 | CloudTrail event review (access entries, config changes, access-denied) | CloudTrail | `metrics-thresholds.md` § CloudTrail |

If CloudWatch / Container Insights access is unavailable, mark O12–O16 **N/A** and record the missing telemetry as an O2/O4 finding — never default them to PASS.

## Conditional telemetry & alarm coverage (O17–O21)

These grade whether component-specific telemetry is collected **and alarmed**. Each is conditional — skip (N/A) when the component isn't present. Thresholds and the recommended-alarm configs live in [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md).

| ID | Check | Detect via | Pass criteria | Severity |
|----|-------|-----------|---------------|----------|
| O17 | Control-plane request telemetry alarmed | ContainerInsights enhanced + `AWS/EKS` | `apiserver_longrunning_requests`, `apiserver_flowcontrol_rejected_requests_total`, 5xx, etcd size collected with alarms; Cross-check the Control Plane Health pillar. | Medium |
| O18 | Karpenter controller metrics + alarms | Karpenter detected; `listMetrics karpenter_*` | controller metrics scraped (`:8080/metrics`) and alarmed (errors, unschedulable, queue depth, startup); N/A without Karpenter. | Medium |
| O19 | CoreDNS DNS-health metrics + alarms | `listMetrics coredns_dns_requests_total` | DNS metrics scraped (`:9153/metrics`) and alarmed (panics, SERVFAIL, p99 latency) | Medium |
| O20 | ENA network-allowance metrics + alarms | `listMetrics linklocal_allowance_exceeded` | ethtool metrics published and alarmed (`linklocal_/conntrack_/pps_allowance_exceeded`); N/A when ethtool metrics are not collected; any breach raises severity to High. | Medium (High if breaches seen) |
| O21 | Recommended-alarm coverage (IDR) | `cloudwatch.describeAlarms` | the base recommended alarms exist (failed nodes, CPU/mem/fs, restarts, node-ready, pending, 5xx, etcd, NAT); Applies to IDR onboarding/CWR. | Medium |

When grading O17–O21, list each missing alarm with its concrete config (threshold · period · datapoints) so the output is directly actionable, not just "add alarms."

## Distributed tracing coverage (O22)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| O22 | Distributed tracing pipeline operational | `features.observability` (ADOT/OTel collector, X-Ray daemon, Jaeger, Zipkin) + trace backend | the tracing pipeline is not just *present* (O5) but *operational*: the collector pods are Running/Ready, traces are being sampled and exported to a backend (X-Ray, Jaeger, Tempo, or a third-party APM), and the sampling rate is configured (not 100% in production); Production sampling should normally be 1–10%; N/A without tracing or for a single-service cluster where tracing adds no value. | Low |
