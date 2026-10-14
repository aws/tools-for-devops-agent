# Node & data-plane health (NH-series)

Node/data-plane health signals — node conditions (kubectl), node & pod utilization
(Container Insights), per-instance EC2 health, network allowances (ENA), EBS volume
performance, NAT gateway, CoreDNS, Karpenter, and the AWS-side nodegroup/registration facts
kubectl can't see. Grade each **✅ HEALTHY / ⚠️ ATTENTION / ❌ ACTION / ⚪ N/A** with the
observed value as evidence. Default lookback **7 days**. Mark a check ⚪ N/A only after
attempting and finding no data source (metric missing, add-on absent, Fargate-only) — never
skip silently.

> **Apply the grading guards** in [`grading-guards.md`](grading-guards.md) before fixing a verdict:
> high CPU/mem ≠ "add capacity" (FP2), low utilization ≠ "remove capacity" (FP8), `OOMKilled` ≠ a
> memory leak (FP3), and `pods_pending > 0` ≠ "scheduler broken" (FP1). Record the applied guard ID
> and a confidence level with each status.

> **Sources:** node conditions via `use_kubectl`; node/pod/EC2/ENA/EBS/NAT/DNS metrics via
> `use_aws` (`cloudwatch:GetMetricData` / `ListMetrics`); nodegroup/registration facts via
> `use_aws` (EKS/EC2/AutoScaling `describe*`). The **NH-P depth checks** additionally need
> kube-state-metrics, prometheus-node-exporter, and kubelet/cadvisor scrape; the **NET checks**
> need the VPC CNI metrics helper (`cni-metrics-helper`). Detect what's enabled first (see
> [`metric-sources.md`](metric-sources.md) §3) and record `sources_missing` — an absent NH-P/NET
> source is a ⚪ N/A **and** an observability-gap finding, never a silent skip.

## Node conditions & version (kubectl — `kubectl get nodes -o json`)

| ID | Check | Signal (`.status.conditions` / `.nodeInfo`) | Healthy | Severity if breached |
|----|-------|----------------------------------------------|---------|----------------------|
| NH1 | All nodes Ready | `Ready==True` for every node | 0 NotReady | Critical |
| NH2 | No DiskPressure | `DiskPressure!=True` | 0 nodes | High |
| NH3 | No MemoryPressure | `MemoryPressure!=True` | 0 nodes | High |
| NH4 | No PIDPressure | `PIDPressure!=True` | 0 nodes | Medium |
| NH5 | Kubelet version skew | kubelet minor within 1 of control-plane, uniform across nodes | within skew | Medium |
| NH6 | Allocatable headroom | pods/CPU/mem allocatable vs capacity; no node pinned at max pods | headroom present | Medium |

## Node utilization (Container Insights — namespace `ContainerInsights`)

| ID | Metric | Healthy | Attention | Action |
|----|--------|---------|-----------|--------|
| NH7 | `node_cpu_utilization` | <70% | >70% | >90% |
| NH8 | `node_memory_utilization` | <80% | >80% | >95% |
| NH9 | `node_filesystem_utilization` | <70% | >70% | >85% |
| NH10 | `cluster_failed_node_count` | 0 | >0 | >1 |

## Pod utilization / stability (Container Insights)

| ID | Metric | Healthy | Attention | Action |
|----|--------|---------|-----------|--------|
| NH11 | `pod_number_of_container_restarts` | <50 / 7d | >50 / 7d | >200 / 7d |
| NH12 | `pod_memory_utilization_over_pod_limit` | <80% | >80% | >95% (OOMKill risk) |
| NH13 | `pod_cpu_utilization_over_pod_limit` | <80% | >80% | >95% (throttling) |
| NH14 | `pod_status_pending` | 0 | >0 brief | >0 sustained (scheduling/capacity) |

## EC2 node health (namespace `AWS/EC2`, per instance)

| ID | Metric | Healthy | Attention | Action |
|----|--------|---------|-----------|--------|
| NH15 | `StatusCheckFailed` | 0 | — | >0 (replace instance) |
| NH16 | `CPUUtilization` | <70% | >80% | >95% |

## Network allowances (ENA — `CWAgent`/Container Insights ethtool, conditional)

Not auto-vended; require the CloudWatch Observability add-on (ethtool metrics) or a CW agent.
Discover via `ListMetrics metricName=linklocal_allowance_exceeded`. If absent, that itself is an
observability gap (Medium).

| ID | Metric | Healthy | Action | Why |
|----|--------|---------|--------|-----|
| NH17 | `linklocal_allowance_exceeded` | 0 | >0 → High | 1024-PPS VPC DNS limit — pods see `UnknownHostException` while CoreDNS looks healthy (mitigate with NodeLocal DNSCache) |
| NH18 | `conntrack_allowance_exceeded` | 0 | >0 → High | conntrack table full — new connections (incl. DNS) fail |
| NH19 | `pps_allowance_exceeded` / `bw_*_allowance_exceeded` | 0 | >0 → Medium/Low | PPS / bandwidth cap — consider larger instance / more ENIs |

## EBS volume performance (namespace `AWS/EBS`, per volume)

| ID | Metric | Healthy | Action | Why |
|----|--------|---------|--------|-----|
| NH20 | `BurstBalance` (gp2/st1/sc1) | >20% | <20% → High; 0 sustained → Critical | Burst-credit exhaustion throttles to baseline — migrate gp2→gp3 |
| NH20b | `VolumeReadOps`+`VolumeWriteOps` vs provisioned IOPS; `VolumeThroughputPercentage`; `VolumeQueueLength` | below provisioned | sustained ≥ provisioned → High | IOPS/throughput saturation or I/O backlog |

## NAT gateway (namespace `AWS/NATGateway`, per NAT)

| ID | Metric | Healthy | Action | Why |
|----|--------|---------|--------|-----|
| NH21 | `ErrorPortAllocation` | 0 | >0 → High | SNAT port exhaustion — new outbound connections fail |
| NH21b | `PacketsDropCount` | <100 / 5 min | >100 / 5 min → Medium | NAT dropping packets |

## CoreDNS (Prometheus scrape of `:9153/metrics`, conditional)

| ID | Metric | Healthy | Action | Why |
|----|--------|---------|--------|-----|
| NH22 | `coredns_panics_total` | 0 | >0 → Critical | any panic = CoreDNS crashed on internal error |
| NH23 | `coredns_dns_responses_total{rcode="SERVFAIL"}` | <100 / 5 min | >100 / 5 min → High | sustained upstream DNS failures |
| NH23b | `coredns_dns_request_duration_seconds` p99 | <1 s | >5 s → High | DNS tail latency |

## Karpenter controller (Prometheus scrape of `:8080/metrics`, when Karpenter detected)

| ID | Metric | Healthy | Action | Why |
|----|--------|---------|--------|-----|
| NH24 | `karpenter_cloudprovider_errors_total` | <10 / 5 min | >10 / 5 min → Medium | ICE / throttling / auth failures |
| NH24b | `karpenter_scheduler_unschedulable_pods_count` / `_queue_depth` | <5 | >5 sustained → Medium | Karpenter can't place pods / falling behind |
| NH24c | `karpenter_pods_startup_duration_seconds` | <180 s | >180 s → Medium | slow scheduling-to-running (EC2 slowness / ICE retries) |

## AWS-side node facts (`use_aws` — EKS / EC2 / AutoScaling `describe*`)

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| NH25 | Managed nodegroup health | `eks describe-nodegroup` → `status`, `health.issues` | ACTIVE, no issues | High (CREATE_FAILED/DEGRADED/stuck update) |
| NH26 | No EC2 instances failing to register | ASG desired/running (`autoscaling describe-auto-scaling-groups`, `ec2 describe-instances`) vs `kubectl get nodes` | counts match | High (launched but never Ready → check SG/NACL/VPC-endpoint path to the cluster endpoint) |
| NH27 | Node auto-repair enabled | `eks describe-nodegroup` → `nodeRepairConfig.enabled` | true | Medium |
| NH28 | Node AMI age (custom / self-managed) | node AMI ID → `ec2 describe-images` `CreationDate` | <90 days | Medium (stale AMI misses kernel/OS patches); N/A on Auto Mode / Fargate |

## Node Monitoring Agent conditions (when NMA is installed — see CA13)

The EKS Node Monitoring Agent surfaces deeper node faults as node conditions (terminal, may trigger
auto-repair) and events (transient). Read them from `kubectl get nodes -o json` `.status.conditions`
when the agent is present (`cluster-addon-health.md` CA13).

| ID | Condition | Healthy | Severity if `True` (unhealthy) |
|----|-----------|---------|-------------------------------|
| NH29 | `ContainerRuntimeReady` | True | High — containerd fault |
| NH30 | `NetworkingReady` | True | High — CNI problem, missing route-table entry, packet drops |
| NH31 | `StorageReady` | True | High — disk exhaustion / I/O errors |
| NH32 | `KernelReady` | True | High — kernel panic / critical system error |
| NH33 | `AcceleratedHardwareReady` | True | High — GPU/Neuron fault (XID errors, ECC, NVLink); N/A if no accelerators |

Also surface NMA node **events** (transient, no auto-repair) if present — CPU throttling, memory
pressure, sub-optimal config — as ⚠️ attention items, not failures.

## Depth checks (NH-P series — kubelet / KSM / node-exporter, conditional)

These extend the NH-series with signals that catch failures the aggregate metrics above miss. They require **kube-state-metrics (KSM)**, **prometheus-node-exporter**, and kubelet/cadvisor scrape (CloudWatch Observability add-on / ADOT). Detect each source first (see [`metric-sources.md`](metric-sources.md) §3, §4.7); when a source is absent, mark the check ⚪ N/A **and** raise the absence as an observability-gap finding. Metric names follow the AWS [EKS essential metrics guide](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/). Each pairs with an existing row — keep the "distinct from" note so verdicts aren't merged.

| ID | Check | Metric / source | Healthy | Severity | Distinct from |
|----|-------|-----------------|---------|----------|---------------|
| NH-P1 | Kubelet running pods/containers | `kubelet_running_pods`, `kubelet_running_container_count` (kubelet) | matches scheduler-bound count | High — runtime not launching containers | NH34 sees API-server state; this sees the kubelet runtime's ground truth |
| NH-P2 | True allocatable headroom | `kube_node_status_allocatable` vs Σ `kube_pod_resource_request` (KSM) | requests < ~90% allocatable | High — `Insufficient cpu/memory` despite low utilization | NH6 = allocatable vs capacity (node overhead); this = allocatable vs requested (workload commitment) |
| NH-P6 | True available memory | `node_memory_MemAvailable_bytes` / `node_memory_MemTotal_bytes` (node-exporter) | > 15% available | High — OOM-eviction risk | NH8 working-set util can look fine while `MemAvailable` (kernel OOM number) is minutes from eviction |
| NH-P7 | NIC-level network errors | `node_network_receive_errs_total`, `node_network_transmit_errs_total` (node-exporter) | 0 | High — hardware/driver packet errors | NH17–19 ENA metrics catch AWS soft-limit throttling; this catches driver/hardware faults |
| NH-P9 | Node Unknown state | `kube_node_status_condition{condition="Ready",status="unknown"}` (KSM) | 0 nodes Unknown | Critical — kubelet stopped heart-beating (partition vs dead) | NH1 catches `Ready=False` (node reporting unhealthy); this catches `Ready=Unknown` (node reporting nothing) |
| NH-P10 | Failed-pod accumulation | `kube_pod_status_phase{phase="Failed"}` (KSM) | not accumulating | Medium — silent etcd growth (CP1) | NH34 catches CrashLoopBackOff (actively restarting); Failed pods never restart and are invisible to it |
| NH-P11 | PVC stuck Pending | `kube_persistentvolumeclaim_status_phase{phase="Pending"}` (KSM) | 0 Pending > a few min | High — storage-blocked pods | NH36 shows the Pending pod; this pinpoints the cause as storage (AZ binding / CSI / IAM), a different fix |

## VPC CNI IP health (NET series — `cni-metrics-helper`, conditional)

VPC CNI IP-address inventory — the most common **silent** EKS scheduling-failure blind spot (nodes Ready, control plane fine, CPU/memory headroom, but pods stuck Pending because a node is out of IPs). Requires the **CNI metrics helper** (`cni-metrics-helper`) publishing `awscni_*` (to CloudWatch or Prometheus). If it isn't installed, mark ⚪ N/A **and** recommend installing it — the absence is itself a material gap. Source: [VPC CNI — monitor IP address inventory](https://aws.github.io/aws-eks-best-practices/networking/vpc-cni/#monitor-ip-address-inventory).

| ID | Check | Metric | Healthy | Action | Why |
|----|-------|--------|---------|--------|-----|
| NET-P1 | IP address exhaustion per node | `awscni_assigned_ip_addresses` / `awscni_total_ip_addresses` | < 90% | ≥ 90% sustained → Critical | Pods Pending "failed to assign an IP" on healthy-looking nodes — instance ENI/IP cap, subnet CIDR, or `WARM_IP_TARGET` misconfig |
| NET-P2 | CNI IP allocation error rate | `awscni_add_ip_req_count` / `awscni_del_ip_req_count` error rate | 0 | sustained errors → High | Pool can't be refilled — EC2 API throttling on `AssignPrivateIpAddresses`, IAM, or subnet exhaustion; fires before NET-P1 |
| NET-P3 | IPAMD stuck operations | `awscni_ipamd_action_inprogress` | 0 | > 0 sustained → High | IPAMD hung — node becomes a "zombie" that accepts pod assignments but fails all new pod networking |

## Workload health rollup (kubectl — `kubectl get pods -A`)

Point-in-time data-plane workload health. Not a per-app audit — a cluster-wide "are pods actually
running" snapshot.

| ID | Check | Signal | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| NH34 | No pods CrashLoopBackOff / Error | pod `.status` container waiting reason | 0 | High (repeated crashes) |
| NH35 | No ImagePullBackOff / ErrImagePull | container waiting reason | 0 | High (can't start — bad image/registry/creds) |
| NH36 | No pods stuck Pending | `status.phase=Pending` > a few min | 0 sustained | Medium — scheduling/capacity/PVC (cross-check scheduler CP + NH14) |
| NH37 | No recent OOMKilled | `lastState.terminated.reason=OOMKilled` | 0 / 7d | High — memory limit too low / leak |
| NH38 | Recent Warning events | `kubectl get events -A --field-selector type=Warning` | none significant | Medium — `FailedScheduling`, `BackOff`, `FailedMount`, `Unhealthy` (probe), `NodeNotReady` |

## Remediation pointers

Node-condition failures (NH1–NH4) usually trace to a specific eviction signal — inspect the node
(`kubectl describe node <n>`), find the pressure source (image cache / logs / ephemeral for
DiskPressure; leaking/over-committed pods for MemoryPressure; pod density for PIDPressure), drain
and replace via the managed nodegroup / Karpenter if it doesn't recover. NH25/NH26 (nodegroup
health, failed registration) map to the same AWS-API remediations as the ops-review AX4/AX8
checks: read `health.issues`, fix bootstrap/AMI conflicts, and verify the worker security group
allows outbound TCP/443 to the cluster endpoint. Node auto-repair (NH27) and AMI rotation (NH28)
are managed-nodegroup config changes. All remediations are **read-only recommendations** — draft
for human approval; never mutate the cluster or node groups from this skill.
