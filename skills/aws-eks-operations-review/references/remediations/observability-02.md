# Observability remediations — shard 02

Canonical IDs: `O9,O10,O11,O12,O13,O14,O15,O16`

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

