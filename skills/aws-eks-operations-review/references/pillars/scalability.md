# Pillar: Scalability

Cluster scale headroom, DNS scaling, instance strategy, and upgrade readiness. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Scalability](https://docs.aws.amazon.com/eks/latest/best-practices/scalability.html) · [Scaling Theory](https://docs.aws.amazon.com/eks/latest/best-practices/kubernetes_scaling_theory.html) · [Scale Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html) · [Scale Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-data-plane.html) · [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html) · [Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html) · [Node & Workload Efficiency](https://docs.aws.amazon.com/eks/latest/best-practices/node_and_workload_efficiency.html) · [Upstream SLOs](https://docs.aws.amazon.com/eks/latest/best-practices/kubernetes_upstream_slos.html) · [Known Limits & Service Quotas](https://docs.aws.amazon.com/eks/latest/best-practices/known_limits_and_service_quotas.html)

Reads discovery areas: 2 NODES, 8 SERVICES, 9 ENDPOINTS, 18 SECRETS, 24 WEBHOOKS, 26 NETWORKING_ADVANCED, 27 KUBE_SYSTEM_RESOURCES, 37 SCALABILITY, 41 DNS_CONFIG.

## Checks (Sc-series)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Sc1 | Cluster size vs K8s thresholds | counts (nodes/pods/services/namespaces) | within tested limits (≤5000 nodes, ≤150k pods, ≤10k services, ≤10k namespaces) | High |
| Sc2 | Services per namespace | services by namespace | no namespace > 500 services | Medium |
| Sc3 | Secrets count vs limit | `secrets` count | < 5,000 (warn) / < 10,000 (critical) | High |
| Sc4 | Instance type diversity | nodes instanceType | 2+ distinct instance types | Medium |
| Sc5 | No burstable (T-series) | nodes instanceType | no t2/t3/t3a/t4g for steady workloads | Medium |
| Sc6 | CoreDNS scaling | CoreDNS replicas vs node count | replicas adequate; autoscaling (CPA/HPA) configured | High |
| Sc7 | NodeLocal DNSCache | `features.dns.nodelocaldns` | present on large clusters | Medium |
| Sc8 | CoreDNS lameduck + readiness | CoreDNS Corefile | `lameduck` set; readiness `/ready` | Medium |
| Sc9 | DaemonSet rolling-update safety | DaemonSet `minReadySeconds`/`maxUnavailable` | controlled rollout (not all-at-once) on large clusters | Medium |
| Sc10 | PriorityClass for critical workloads | pod `priorityClassName` | critical Deployments/StatefulSets set a PriorityClass | Medium |
| Sc11 | Pods-per-node headroom | pods per node vs allocatable | nodes not near the 110/pod (or prefix) ceiling | Medium |
| Sc12 | ndots tuning | pod dnsConfig | external-heavy workloads lower `ndots` (default 5) | Low |
| Sc22 | EBS volume-attachment limit per instance | node instanceType + attached EBS volume count (`ebs.csi.aws.com` PVs bound to the node / AWS-API `describeVolumes`) | stateful node density leaves headroom under the instance's EBS attachment limit; use family-specific thresholds (older Nitro commonly shares ~28 attachments across EBS, ENIs, and instance store; seventh-generation families can have a dedicated limit up to 64); AWS-API determines exact counts/limits; in kubectl-only mode infer from EBS PVs per node or mark N/A | Medium |

## Workload API-load reduction + batch (Sc16–Sc21, Sc23)

These reduce per-workload load on the control plane, raising how many workloads a cluster can hold ([Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)).

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Sc16 | EndpointSlices over Endpoints | area 9 ENDPOINTS | services back EndpointSlices (default on modern EKS); no reliance on legacy Endpoints at scale | Medium |
| Sc17 | Deployment revisionHistoryLimit bounded | Deployment `spec.revisionHistoryLimit` | set to a small value (not the default 10) on large clusters | Low |
| Sc18 | enableServiceLinks disabled | pod `spec.enableServiceLinks` | set `false` where service env-var injection isn't needed | Low |
| Sc19 | Dynamic webhooks per resource bounded | areas 24 webhooks | few mutating/validating webhooks intercept any single resource (esp. pods) | Medium |
| Sc20 | IPv6 for large-scale pod networking | `features.cni_config.ipv6_cluster` | IPv6 used (or conscious IPv4 + prefix decision) on clusters expected to grow large; Cross-check N7. | Low |
| Sc21 | Cluster services on dedicated capacity | area 27 kube-system placement | critical cluster services (CoreDNS, metrics-server, controllers) not co-located with bursty workloads | Medium |
| Sc23 | Kueue queue health (conditional) | `kubectl get clusterqueues,localqueues,workloads` (CRD: `kueue.x-k8s.io`) | if Kueue CRDs are installed: ClusterQueues are `Active`, no LocalQueues stuck in `StoppedByClusterQueue`, no Workloads `Inadmissible` for > 10 min beyond their nominal wait; ResourceFlavors resolve; borrowing/lending limits are reasonable; stuck Workloads have a clear preemption/wait reason; N/A when Kueue CRDs are absent | Medium |

## Upgrade readiness (Sc13–Sc15)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Sc13 | Version skew | control plane vs kubelet | nodes within 2 minor of API server | High |
| Sc14 | No removed/deprecated admission mechanisms | `kubectl get podsecuritypolicies` (≤1.24) + PSA/policy-engine presence | **≤1.24:** no PodSecurityPolicy still in use (removed in 1.25). **≥1.25:** PSP is already gone — confirm its replacement is in place instead (PSA `restricted` via S9, or a policy engine via S23), not that PSP is absent; Cross-check U5/U5b and AX1. | High |
| Sc15 | No deprecated Ingress API | Ingress apiVersion | all `networking.k8s.io/v1` | Medium |

## Manual / AWS-API checks (ScM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| ScM1 | LoadBalancer / target-group quotas | AWS-API | LB count vs region quota (default 50); ALB targets default 1000, NLB 3000 (500/AZ). Split across LBs/Ingress or raise quota. |
| ScM2 | CAS sharding for very large clusters | replica analysis | shard CAS across node groups beyond ~1000 nodes. |
| ScM3 | API server throttling (429s) | control-plane metrics | see the **Control Plane Health** pillar (`pillars/control-plane.md`) for APF / 429 analysis and the upstream SLO view. |
| ScM4 | metrics-server vertical sizing | deployment resources | scale metrics-server requests/limits with node count (it holds data in memory). |
| ScM5 | AWS service quotas that gate scale | AWS-API / Service Quotas | review quotas EKS scaling commonly hits: ENIs/Region (5,000), IPv4 CIDRs/VPC (5), SGs/ENI (5), rules/SG (50), routes/route-table (50), VPCs/Region (5), IAM roles/account (1,000), OIDC providers/account (100), EC2 instance + EBS limits. |
| ScM6 | AWS API request throttling | AWS-API / logs | high-churn clusters (Karpenter/CAS, controllers) can hit EC2/ASG/IAM API rate limits — watch for throttling, use backoff/caching. |
| ScM7 | Single endpoint across multiple LBs | architecture | for services spanning >1 LB (target-group limits), front with Route 53 / Global Accelerator / CloudFront. |

## Notes

- **Where scale limits live:** workload-side (this pillar's Sc-series), control-plane saturation (APF/etcd/API latency → **Control Plane Health** pillar, `pillars/control-plane.md`), and AWS service quotas (ScM5). A scale review should touch all three.
- **Upstream SLOs / scaling theory:** Kubernetes publishes scalability SLOs (API request latency, pod startup) and tested thresholds (≤5000 nodes, ≤150k pods, ≤300k containers, ≤10k services). Treat these as ceilings, not targets — degradation often starts well before them.
