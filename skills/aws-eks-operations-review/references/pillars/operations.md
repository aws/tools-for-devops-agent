# Pillar: Operations

Operational excellence: version currency, add-on/autoscaler hygiene, and workload operations. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html) · [Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html) · [CAS](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html) · [Auto Mode](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html)

Reads discovery areas: 1 CLUSTER_INFO, 2 NODES, 16 CRONJOBS, 27 KUBE_SYSTEM_RESOURCES, 28 AUTOSCALING_INFRA, 33 THIRD_PARTY_CONTROLLERS, 44 SCHEDULING.

> **AWS-side operations facts** (nodegroup health / `CREATE_FAILED`, managed-addon health + upgrade conflicts, addon versions) are graded by the **AWS-API component** ([`../aws-api-checks.md`](../aws-api-checks.md), AX4/AX5) — they confirm Op3/Op7 and close the node-join / addon-upgrade findings. In kubectl-only mode they stay N/A here and are flagged for follow-up.

## Cluster & version (Op1–Op7)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op1 | Kubernetes version currency | kubectl `version`; nodes kubeletVersion | server version within N–2 of latest EKS-supported | High |
| Op2 | Node version consistency | nodes `.status.nodeInfo.kubeletVersion` | all nodes same kubelet minor; within 1 of control plane | High |
| Op3 | Addon presence (CNI/CoreDNS/kube-proxy/CSI) | kube-system DaemonSets/Deployments | core addons present and Ready | Medium |
| Op4 | Managed vs self-managed nodes | node labels (`eks.amazonaws.com/nodegroup`) | workers under managed nodegroups or Karpenter/Auto Mode | Medium |
| Op5 | Resource governance tags | namespace labels (team/tenant/env) | workload namespaces carry org labels | Low |
| Op6 | IaC / GitOps management | `features.gitops.*`; CRDs | ArgoCD or Flux present, or IaC evident | Low |
| Op7 | Addon versions current | AWS-API | managed addon versions ≤1 minor behind; N/A in kubectl-only mode; requires AWS-API confirmation. | Medium |

## Autoscaler operations (Op8–Op13, Op20–Op28)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op8 | Node Monitoring Agent present | kube-system DaemonSet | `eks-node-monitoring-agent` detected and Ready; Configured independently; prerequisite for Op26. | High |
| Op9 | CAS version matches cluster | CAS pod image tag vs kubeletVersion | CAS minor = cluster minor | High |
| Op10 | Karpenter NodePool limits set | NodePool `spec.limits` | `cpu` and `memory` limits set | Medium |
| Op11 | Karpenter AMI pinned | EC2NodeClass `amiSelectorTerms` | not using `@latest` alias in prod | High |
| Op12 | Karpenter consolidation policy | NodePool `spec.disruption.consolidationPolicy` | policy set | Medium |
| Op13 | Karpenter node expiry | NodePool `spec.disruption.expireAfter` | set (not `Never`) for prod | Medium |
| Op20 | Karpenter controller placement | Karpenter pod's node labels (`karpenter_self_hosted`) | controller runs on Fargate or an MNG node — **not** on a Karpenter-managed node | High |
| Op21 | Consolidation requires requests=limits (non-CPU) | workload `resources` + NodePool consolidation | when consolidation is enabled, memory `requests == limits` | Medium |
| Op22 | Spot NodePool instance diversity | NodePool `requirements` (`spot_nodepool_low_diversity`) | Spot NodePools allow a broad instance set | Medium |
| Op23 | Auto Mode managed-component expectations | nodes (`compute-type=auto`) + controller pods | on Auto Mode, Karpenter/LBC/EBS CSI are AWS-managed — **do not** flag as missing; host agents still run as DaemonSets; flag only leftover self-managed duplicates (cross-check Op17). | Low |
| Op24 | CAS auto-discovery + version coupling | CAS deployment args + image tag | `--node-group-auto-discovery` set and minor matches cluster | High |
| Op26 | Node Auto Repair enabled | nodegroup config (AWS-API) `nodeRepairConfig` / Karpenter | Node Auto Repair enabled on managed nodegroups (or Karpenter's built-in node repair) so unhealthy nodes are automatically replaced; AWS-API only; N/A in kubectl-only mode. Independently configured from, and dependent on, Op8. | High |
| Op27 | Karpenter NodePool exclusivity / weighting | NodePools `spec.template.spec.requirements`/`taints` + `spec.weight` | multiple NodePools are mutually exclusive (non-overlapping requirements/taints) or use `spec.weight` to break ties; N/A with a single NodePool. | Medium |
| Op28 | Karpenter Spot-to-Spot consolidation | Karpenter controller feature gates / settings | when Spot NodePools exist, `SpotToSpotConsolidation` is enabled; N/A without Spot NodePools; cross-check A1/A8. | Low |

## Workload operations (Op14–Op17)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op14 | CronJob schedule coverage | CronJob `.spec.schedule` | all CronJobs have explicit schedules | Medium |
| Op15 | All pods Running | pod `.status.phase` | no `Failed`/`Unknown`; no CrashLoop/ImagePull/OOMKilled | Medium |
| Op16 | Workload SA hygiene | workload + pod `serviceAccountName` | no workloads on `default` SA | High |
| Op17 | Auto Mode component dedup | nodes + controller pods | if Auto Mode, no duplicate self-managed Karpenter/LBC/EBS CSI | Low |

## Node health & runtime (Op25, Op29)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op25 | Node conditions healthy | area 2 node `.status.conditions` (`nodes_notready`, `nodes_diskpressure`, `nodes_memorypressure`, `nodes_pidpressure`) | every node `Ready=True` with `DiskPressure`/`MemoryPressure`/`PIDPressure` all `False`; Escalate severity to Critical when multiple nodes share a pressure condition or a NotReady node hosts singleton/stateful pods. | High |
| Op29 | Node AMI age / rotation window | area 2 node AMI ID + `ec2.describeImages` `CreationDate` (AWS-API) | worker-node AMIs (self-managed and MNG **custom** AMIs) are not older than the rotation window (90 days is a common bar); custom AMIs have a documented rebuild/rotation pipeline; N/A in kubectl-only mode and on Auto Mode/Fargate; cross-check Op11 and U15. | Medium |

> Op25 grades the live node-condition signals captured in discovery area 2. The data was always collected (`Ready`/`DiskPressure`/`MemoryPressure`) but previously ungraded; PIDPressure is now captured too. Pair with Resilience R1/R12 (AZ spread, version consistency) and Performance (requests/limits) when pressure is workload-driven.

## Conflict checks (Op18–Op19)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op18 | Single autoscaler | `features.autoscaling.*` | not more than one node autoscaler active | High |
| Op19 | metrics-server present | `features.observability.metrics_server` | metrics-server Ready | High |

## Manual / AWS-API checks (OpM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| OpM1 | Karpenter Spot interruption handling | controller CLI flag | If Spot NodePools exist, verify native interruption handling / `--interruption-queue` → SQS. |
| OpM2 | CAS auto-discovery | CAS CLI flag | `--node-group-auto-discovery` in use (also Op24 when args readable). |
| OpM3 | Control-plane logging enabled | AWS-API | `aws eks describe-cluster --query cluster.logging`. |
| OpM4 | Cluster auth mode | AWS-API | `aws eks describe-cluster --query cluster.accessConfig.authenticationMode`. |
| OpM5 | CAS IAM least privilege | AWS-API / IAM | CAS IRSA role scopes `autoscaling:SetDesiredCapacity` + `TerminateInstanceInAutoScalingGroup` to cluster ASGs via `aws:ResourceTag` conditions. |
| OpM6 | CAS sharding for large clusters | node count + replica analysis | CAS is single active replica; shard across node groups for very large clusters. |
| OpM7 | CoreDNS tuning under Karpenter | CoreDNS config | With fast churn, ensure CoreDNS reliability (replicas/autoscaling, `lameduck`, topology spread). |
| OpM8 | do-not-disrupt on critical pods | pod annotations | Critical pods carry `karpenter.sh/do-not-disrupt: "true"`. |
| OpM9 | AWS Health integration | EventBridge | Rules matching `aws.health` with EKS filter. |

## Infrastructure operations (Op30–Op32)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| Op30 | CSI driver controller + node health | kube-system DaemonSet/Deployment (ebs-csi-controller, ebs-csi-node, efs-csi-*) | CSI controller Deployment and node-driver DaemonSet pods are all Running/Ready; no pods in CrashLoop or pending; `CSIDriver` and `CSINode` objects present; N/A on Auto Mode or when no CSI driver is used. | High |
| Op31 | GitOps reconciliation health | area 33 ArgoCD Applications / Flux Kustomizations | if GitOps is detected (Op6), all Applications/Kustomizations are `Synced`/`Healthy` (Argo) or `Ready=True` (Flux); no `OutOfSync`, `Degraded`, `Stalled`, or `ReconciliationFailed`; N/A when GitOps is not detected. | Medium |
| Op32 | Deployment rollback readiness | Deployment `spec.revisionHistoryLimit` + ReplicaSets | Deployments retain sufficient revision history (`revisionHistoryLimit` ≥ 2, not 0) and have at least one previous successful ReplicaSet available for `kubectl rollout undo`; The default of 10 passes; lower values may be intentional at very large scale (cross-check Sc17). | Low |
