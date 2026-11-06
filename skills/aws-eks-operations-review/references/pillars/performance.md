# Pillar: Performance Efficiency

Right-sizing, autoscaling coverage, QoS, and compute selection. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html) · [Application HA](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)

Reads discovery areas: 4 DEPLOYMENTS, 5 STATEFULSETS, 11 HPA, 12 VPA, 13 KEDA, 35 RELIABILITY, 36 DATA_PLANE, 47 RESOURCE_OPTIMIZATION.

## Checks (P-series)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| P1 | Resource requests set | container `resources.requests` | all containers set cpu + memory requests | High |
| P2 | CPU limits — deliberate trade-off (tenancy-conditional) | container `resources.limits.cpu` + cluster tenancy (single- vs multi-tenant) | **Dedicated / single-tenant:** CPU limits absent — requests act as a CPU-time weight so pods burst into idle CPU ([EKS Data Plane guide](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)). **Multi-tenant / noisy-neighbor:** noisy workloads bounded via ResourceQuota (P7) + dedicated node pools (taints/tolerations) or CPU pinning — *not* blanket CPU limits | Low |
| P3 | Memory requests = limits | container memory resources | memory `requests == limits` (Guaranteed/Burstable intent) | Medium |
| P4 | QoS distribution | pod `.status.qosClass` (`qos_*`) | minimal BestEffort for prod workloads | Medium |
| P5 | HPA coverage | HPAs vs Deployments | replicas>1 stateless workloads have HPA or KEDA | High |
| P6 | VPA present (right-sizing) | `features.autoscaling.vpa` | VPA in at least recommendation mode | Medium |
| P7 | ResourceQuota per namespace | area 35 (`resourcequotas`) | quotas in namespaces with workloads | Medium |
| P8 | LimitRange per namespace | area 35 (`limitranges`) | LimitRanges set defaults | Medium |
| P9 | Graviton adoption | nodes `arch=arm64` | at least some arm64 where workloads allow | Low |
| P10 | Instance selection fit | nodes instanceType vs workload | instance families match workload profile | Low |
| P11 | Prefix delegation (pod density / startup) | `features.cni_config.prefix_delegation` | enabled where pod density / fast startup needed | Low |
| P12 | Compute Optimizer recommendations reviewed | `computeoptimizer.getEC2InstanceRecommendations` (AWS-API) | no `OVER_PROVISIONED`/`UNDER_PROVISIONED` worker instances left unaddressed; N/A in kubectl-only mode. | Medium |
| P13 | EBS volume performance headroom | `AWS/EBS` metrics (AWS-API) | no `BurstBalance` exhaustion (gp2/st1/sc1); IOPS/throughput not saturated vs provisioned; N/A without CloudWatch access. | High |
| P14 | Init container resource footprint | pod `initContainers` vs app `containers` `resources.requests` | init-container requests don't greatly exceed the app containers' effective request (a pod's effective request is `max(sum(app containers), max(any init container))`) | Low |
| P15 | EBS IOPS/throughput headroom per volume | `AWS/EBS` `VolumeReadOps` + `VolumeWriteOps` + `VolumeThroughputPercentage` (AWS-API) | no EBS volume sustained at > 80% of provisioned IOPS or throughput; no gp2 volume with `BurstBalance` < 20%; N/A without CloudWatch access or EBS volumes. | High |
| P16 | CPU throttling percentage | Container Insights `container_cpu_cfs_throttled_periods` / `container_cpu_cfs_periods_total` (Prometheus) | no container sustained > 25% throttled periods over 7 days; N/A without enhanced Container Insights/Prometheus metrics; cross-check P2. | Medium |

## Manual / metrics-dependent checks (PM)

| ID | Check | Why not from kubectl alone | How to verify |
|----|-------|----------------------------|---------------|
| PM1 | Actual usage vs requests | needs metrics-server | `kubectl top pods/nodes`; compare to requests to find over/under-provisioning. |
| PM2 | Node utilization / bin-packing | needs metrics | low-utilization nodes → consolidation / right-sizing. |
| PM3 | VPA recommendations applied | VPA status | review VPA `status.recommendation` vs configured requests. |
