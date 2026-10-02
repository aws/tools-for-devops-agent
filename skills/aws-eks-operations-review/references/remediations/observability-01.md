# Observability remediations — shard 01

Canonical IDs: `O1,O2,O3,O4,O5,O6,O7,O8`

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

