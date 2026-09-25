# Runtime telemetry thresholds

Load in S4/S6 only when telemetry applies. Default lookback is 7 days. Missing metrics are N/A with the source reason and a visibility finding, never PASS. Apply `grading-guards.md` before interpreting CPU, memory, 429, object-growth, or empty-log signals. Detailed sourcing/rationale is in [`../docs/operator-guides.md#metrics-and-alarms`](../docs/operator-guides.md#metrics-and-alarms) and loads only for an explicit operator question.

## Core node, pod, EKS, and EC2 thresholds

| Source / metric | Normal | Warning | Critical |
|---|---|---|---|
| ContainerInsights `node_cpu_utilization` | <70% | >70% | >90% |
| `node_memory_utilization` | <80% | >80% | >95% |
| `node_filesystem_utilization` | <70% | >70% | >85% |
| `cluster_failed_node_count` | 0 | >0 | >1 |
| `pod_cpu_utilization` | 10–60% | <10% or >60% | >80% |
| `pod_memory_utilization` | 20–70% | <20% or >70% | >85% |
| `pod_number_of_container_restarts` | <50/7d | >50/7d | >200/7d |
| AWS/EKS `apiserver_request_total_5XX` | <100/7d | >100/7d | sustained >5m |
| `apiserver_request_total_429` | <50/7d | >50/7d | privileged tier or sustained >5m |
| `apiserver_storage_size_bytes` | <75% quota | >75% | >90% |
| admission webhook duration | <1s | >3s | sustained |
| `scheduler_pending_pods` | 0 | >10 peak | >10 sustained |
| AWS/EC2 `CPUUtilization` | <70% | >80% | >95% |
| `StatusCheckFailed` | 0 | — | >0 |

## Logs and CloudTrail

| Signal | Finding threshold / required interpretation |
|---|---|
| `ERROR` | >100/7d: investigate component/cause. |
| `429` | Apply FP6; identify priority and caller. |
| `OOMKilled` | Apply FP3; do not claim a leak from one event. |
| `FailedScheduling` | Apply FP1; classify constraint/capacity cause. |
| `Evicted` | Investigate node pressure, requests, PDB, and drain history. |
| CloudTrail `AccessDenied`/`UnauthorizedOperation` | investigate authorization and principal; do not claim compromise without FP9 evidence. |
| `CreateAccessEntry` | verify authorization and correlate AX2. |
| `UpdateClusterConfig`/`UpdateNodegroupConfig`/`DeleteCluster` | record change correlation and intent. |

## Conditional telemetry

| Component / metric | Threshold |
|---|---|
| ENA `linklocal_allowance_exceeded` | any breach/7d High; 30d-only Medium; metric absent = visibility gap. |
| `conntrack_allowance_exceeded` | >0 High |
| `pps_allowance_exceeded` | >0 Medium |
| `bw_in_allowance_exceeded` / `bw_out_allowance_exceeded` | >0 Low |
| CoreDNS `coredns_panics_total` | >0 Critical |
| CoreDNS SERVFAIL | >100/5m High |
| CoreDNS request duration | p99 >5s or average >1s High |
| Karpenter cloud-provider errors | >10/5m Medium |
| Karpenter unschedulable or queue depth | >5 sustained Medium |
| Karpenter pod startup | >180s Medium |
| EBS `BurstBalance` | <20% High; 0 sustained Critical |
| EBS IOPS/throughput | sustained ≥ provisioned or near 100% High |
| EBS `VolumeQueueLength` | persistently high Medium |
| NAT `ErrorPortAllocation` | >0 High |
| NAT `PacketsDropCount` | >100/5m Medium |
| CPU throttled periods | >25% sustained Medium |

## Recommended alarms for IDR/CWR

Emit existing/missing state plus this exact config; add component alarms only when the metric exists.

| Alarm | Config |
|---|---|
| failed nodes | ContainerInsights Max >0, 1m, 1/1 |
| node CPU/memory/filesystem | Avg >80%, 5m, 3/5 |
| pod CPU/memory over limit | Avg >95%, 5m, 3/5 |
| container restarts | Sum >5/hour, 1/1 |
| node Ready | Min <1, 5m, 2/3 |
| pending pods | Max >0, 5m, 2/3 |
| API long-running requests | Avg >50, 5m, 3/5 |
| APF rejected requests | Sum >10, 5m, 2/3 |
| API 5xx | AWS/EKS Sum >10, 1m, 1/1 |
| etcd size | AWS/EKS Max >80% quota, 5m, 3/5 |
| NAT port allocation | Sum >0, 5m, 1/1 |
| NAT dropped packets | Sum >100, 5m, 2/3 |