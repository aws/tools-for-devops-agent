# Observability remediations — shard 03

Canonical IDs: `O17,O18,O19,O20,O21,OM1`

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

