# Observability remediations — shard 01
Canonical IDs: `O1,O2,O3,O4,O5,O6,O7,O8,O9,O10,O11,O12,O13,O14,O15,O16,O17,O18,O19,O20,O21,OM1`

### O1 — Metrics Server present
**Why it matters:** Required for HPA/VPA and `kubectl top`. Without it autoscaling and live usage visibility are broken.
**Steps:** Install metrics-server (managed addon/manifest); confirm Ready.
**References:**
- [EKS User Guide — metrics-server](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html)

### O2 — Metrics pipeline present
**Why it matters:** Without a metrics backend (Prometheus/AMP or CloudWatch Container Insights) there are no dashboards, no historical trends, and no alerting substrate.
**Steps:** Deploy Prometheus/AMP or enable CloudWatch Container Insights; scrape cluster + workload metrics.
**References:**
- [EKS Best Practices — Application observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [CloudWatch — Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html)

### O3 — kube-state-metrics present
**Why it matters:** Object-state metrics (deployment/replica/pod conditions) are needed to alert on things like "replicas available < desired" — node/pod resource metrics alone don't cover it.
**Steps:** Deploy kube-state-metrics alongside the metrics backend.
**References:**
- [kube-state-metrics — GitHub](https://github.com/kubernetes/kube-state-metrics)

### O4 — Logging pipeline present
**Why it matters:** Without centralized logs, pod logs vanish when pods are rescheduled — no post-incident forensics.
**Steps:** Deploy Fluent Bit (or Fluentd/Vector) to ship container logs to CloudWatch Logs / OpenSearch; set retention.
**References:**
- [EKS Best Practices — Application observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [CloudWatch — Fluent Bit for Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-logs-FluentBit.html)

### O5 — Tracing present
**Why it matters:** Distributed tracing pinpoints latency across services; without it, cross-service bottlenecks are guesswork.
**Steps:** Instrument with OpenTelemetry; export via ADOT to X-Ray / a tracing backend.
**References:**
- [AWS Distro for OpenTelemetry](https://aws-otel.github.io/docs/introduction)

### O6 — Alerting present
**Why it matters:** Metrics without alerts mean problems are found by users, not operators. Alerting closes the loop.
**Steps:** Configure Alertmanager (Prometheus) or CloudWatch alarms on the signals that matter (saturation, error rate, OOM, FailedScheduling); route to on-call.
**References:**
- [EKS Best Practices — Application observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)

### O7 — No OOMKilled events
**Why it matters:** OOMKilled means memory limits are too low (or a leak) — the workload is being force-restarted, causing instability.
**Steps:** Raise memory `requests`/`limits` to the working-set size (use VPA/`kubectl top` to size); investigate leaks for repeat offenders.
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [Kubernetes — Assign Memory Resources](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/)

### O8 — No CrashLoop / ImagePull
**Why it matters:** CrashLoopBackOff (app/config failure) and ImagePullBackOff (registry/auth/tag) are live broken deployments.
**Steps:** `kubectl describe pod` + `kubectl logs --previous` for CrashLoop; check image tag, registry reachability, and pull-secret/ECR permissions for ImagePull.
**References:**
- [EKS — Troubleshooting](https://docs.aws.amazon.com/eks/latest/userguide/troubleshooting.html)

### O9 — No FailedScheduling / warning storms
**Why it matters:** Sustained FailedScheduling/BackOff/Unhealthy/FailedMount events indicate capacity, probe, or volume problems degrading the cluster.
**Steps:** Triage `kubectl get events --sort-by=.lastTimestamp`; address the root cause class (capacity → autoscaler/affinity; FailedMount → CSI/AZ; Unhealthy → probes).
**References:**
- [EKS — Troubleshooting](https://docs.aws.amazon.com/eks/latest/userguide/troubleshooting.html)

### O10 — CNI metrics helper (IP monitoring)
**Why it matters:** On IPv4 clusters at scale, ENI/IP exhaustion silently blocks pod scheduling; the CNI metrics helper exposes IP allocation so you can alert before exhaustion.
**Steps:** Deploy the CNI metrics helper; alert on low available IPs per ENI/subnet.
**References:**
- [EKS — CNI metrics helper](https://docs.aws.amazon.com/eks/latest/userguide/cni-metrics-helper.html)

### O11 — GPU metrics (DCGM)
**Why it matters:** Without GPU telemetry you can't see accelerator utilization — and idle GPUs are the biggest ML cost leak. (Also M15.)
**Steps:** Deploy the DCGM exporter (or CloudWatch GPU metrics) on GPU nodes; dashboard utilization and power.
**References:**
- [EKS Best Practices — AI/ML Observability](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-observability.html)

## Observability — CloudWatch & conditional telemetry (O12–O21)

### O12 — Node/pod utilization (7-day) collected
**Why it matters:** Without 7-day node/pod CPU/memory/filesystem utilization you can't tell saturation from waste, or right-size. Container Insights provides it.
**Steps:** Enable the `amazon-cloudwatch-observability` add-on; grade against [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md). **N/A** if Container Insights is off (and that's an O2 finding).
**References:** [Container Insights metrics (EKS)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-EKS.html)

### O13 — Container restart trend (7-day)
**Why it matters:** A rising `pod_number_of_container_restarts` is an early instability signal (OOM, crash loops, bad probes) before it becomes an outage.
**Steps:** Trend restarts over 7 days; investigate workloads over the threshold (`metrics-thresholds.md`). **References:** [Container Insights metrics (EKS)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-EKS.html)

### O14 — Control-plane log error patterns
**Why it matters:** `ERROR`/`429`/`OOMKilled`/`FailedScheduling`/`Evicted` patterns in control-plane logs surface problems metrics alone miss.
**Steps:** Query control-plane logs over 7 days for the patterns in `metrics-thresholds.md`; correlate counts to findings. **N/A** if control-plane logging is off (OM1). **References:** [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html)

### O15 — EC2 node health (StatusCheckFailed)
**Why it matters:** `StatusCheckFailed`/high `CPUUtilization` on worker instances catch hardware/system faults the kubelet may not report.
**Steps:** Check `AWS/EC2` per-instance metrics; replace failing instances (auto-repair via Op8). **References:** [EC2 status checks](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-system-instance-status-check.html)

### O16 — CloudTrail event review
**Why it matters:** Access-entry creation, config changes, and access-denied bursts are the audit trail for security and change correlation.
**Steps:** Review 7-day CloudTrail EKS management events per `metrics-thresholds.md`; corroborate with AX2. **References:** [Logging EKS API calls with CloudTrail](https://docs.aws.amazon.com/eks/latest/userguide/logging-using-cloudtrail.html)

### O17 — Control-plane request telemetry alarmed
**Why it matters:** `apiserver_longrunning_requests` and `apiserver_flowcontrol_rejected_requests_total` (APF) are leading indicators of control-plane pressure; uncollected/unalarmed, you learn about it during an incident.
**Steps:** Enable enhanced Container Insights; add the base control-plane alarms from `metrics-thresholds.md`. Pairs with the Control Plane Health pillar.
**References:** [Enhanced Container Insights metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-enhanced-EKS.html)

### O18 — Karpenter controller metrics + alarms *(conditional)*
**Why it matters:** Karpenter's own metrics (`cloudprovider_errors_total`, `scheduler_unschedulable_pods_count`, `scheduler_queue_depth`, `pods_startup_duration_seconds`, `nodeclaims_*`) reveal provisioning failures (ICE, throttling) and scheduling backlog that node-level metrics don't.
**Steps:** Enable Container Insights Prometheus scraping (or AMP remote-write) for the Karpenter controller `:8080/metrics`; add the conditional Karpenter alarms (`metrics-thresholds.md`). **N/A** if Karpenter isn't deployed.
**References:** [Karpenter — Metrics](https://karpenter.sh/docs/reference/metrics/)

### O19 — CoreDNS DNS-health metrics + alarms *(conditional)*
**Why it matters:** Basic Container Insights shows only CoreDNS pod CPU/mem/restarts. The DNS-health metrics — `coredns_panics_total` (must be 0), SERVFAIL rate, p99 latency — are what actually tell you DNS is failing.
**Steps:** Enable enhanced observability Prometheus scraping for CoreDNS `:9153/metrics`; add the conditional CoreDNS alarms. **N/A** if no DNS metrics and no Container Insights.
**References:** [CoreDNS metrics plugin](https://coredns.io/plugins/metrics/)

### O20 — ENA network-allowance metrics + alarms *(conditional)*
**Why it matters:** `linklocal_allowance_exceeded` (1024 PPS VPC DNS limit), `conntrack_allowance_exceeded`, and `pps_allowance_exceeded` are dropped-packet counters that explain "DNS randomly fails but CoreDNS is healthy." They aren't auto-vended.
**Steps:** Enable ethtool metrics in the CloudWatch Observability add-on (or CW Agent `ethtool.metrics_include`); alarm on any breach; remediate per Networking N21 (NodeLocal DNSCache). A breach in the last 7 days is **High**.
**References:** [Monitoring network performance](https://docs.aws.amazon.com/eks/latest/best-practices/monitoring_eks_workloads_for_network_performance_issues.html)

### O21 — Recommended-alarm coverage (IDR)
**Why it matters:** For IDR onboarding / a CWR, the deliverable isn't just findings — it's a ready-to-create alarm set so the customer has detection from day one.
**Steps:** Compare existing `describeAlarms` against the base recommended set in `metrics-thresholds.md`; for each missing alarm, emit its concrete config (metric · namespace · threshold · period · datapoints · SNS action). List conditional sets when Karpenter/CoreDNS/ENA telemetry is present.
**References:** [AWS Recommended Alarms — EKS](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html) · [EKS IDR Alarming Best Practices](https://repost.aws/articles/ARhnAXjQGMSr2l2_qb_J8uaA)

## Observability — manual / AWS-API (OM)

### OM1 — Control-plane log types enabled
**Why / fix:** Verify `aws eks describe-cluster --name ${CLUSTER} --query cluster.logging` and enable api/audit/authenticator/controllerManager/scheduler as needed. Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).
