# Observability remediations — shard 04

Canonical IDs: `OM2,OM3,OM4,O22`

### OM2 — Container Insights enabled
**Why / fix:** Confirm CloudWatch Container Insights for EKS is active (metrics + optionally logs). Link: [Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html).

### OM3 — App-level metrics exposed
**Why / fix:** Confirm workloads expose Prometheus metrics endpoints (RED/USE signals), not just infra metrics. Link: [Application observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html).

### OM4 — Control-plane saturation review
**Why / fix:** etcd size / APF / API latency belong to the **Control Plane Health** pillar (`pillars/control-plane.md`, backed by the `control-plane-health/` component) — grade it for control-plane saturation. Link: [Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html).

### O22 — Distributed tracing pipeline operational
**Why it matters:** Without operational tracing, distributed-system latency issues require manual log correlation across services — dramatically increasing MTTR for performance incidents.
**Steps:**
1. Verify collector health: `kubectl get pods -A -l app.kubernetes.io/component=opentelemetry-collector` (or X-Ray daemon, Jaeger).
2. Confirm traces are being exported: check collector logs for successful export confirmations or backend (X-Ray console, Jaeger UI, Tempo).
3. Verify sampling rate: production should sample 1–10% (not 100%, which is expensive and overwhelming; not 0%, which is useless). Check the OTEL sampler config or X-Ray sampling rules.
4. If not present: deploy the AWS Distro for OpenTelemetry (ADOT) collector as a DaemonSet or Sidecar. See the EKS observability add-on.
**References:**
- [EKS Best Practices — Application Observability](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [AWS Distro for OpenTelemetry](https://aws-otel.github.io/docs/getting-started/eks)
