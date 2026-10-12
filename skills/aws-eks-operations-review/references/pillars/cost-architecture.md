# Pillar: Cost / Sustainability / Architectural

Compute/storage efficiency, networking cost, and architectural hygiene. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Cost Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt.html) · [Framework](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-framework.html) · [Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html) · [Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html) · [Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html) · [Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html) · [Observability](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-observability.html)

Reads discovery areas: 4/5 workloads, 8 SERVICES, 11/12/13 autoscalers, 20 STORAGE, 23 CRDS, 28 AUTOSCALING_INFRA, 29 OBSERVABILITY, 32 COST_OPTIMIZATION, 36 DATA_PLANE, 47 RESOURCE_OPTIMIZATION.

## Currency framing (read first)

Cost-opt priority order from the framework: **(1) right-size workloads → (2) reduce unused capacity → (3) optimize capacity types (Spot/Graviton/commitments)**. Right-sizing first; cheaper instances under an oversized workload still waste money. Cost *awareness* (allocation/showback via Kubecost/OpenCost, CUR, Split Cost Allocation Data) underpins all of it — you can't optimize what you can't attribute.

## Compute (A1–A2, A5–A8, A13–A15)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| A1 | Spot adoption | nodes `capacityType=SPOT` (`spot_nodes`) | Spot used for fault-tolerant workloads | Low |
| A2 | Graviton adoption | nodes `arch=arm64` | arm64 where workloads allow | Low |
| A5 | Cost monitoring tooling | `features.cost_optimization.*` | Kubecost / OpenCost / Goldilocks present | Low |
| A6 | Right-sizing signal | pods without requests + VPA | low share of no-request pods; VPA in audit mode available | Medium |
| A7 | Autoscaler present | `features.autoscaling.*` | Karpenter / CAS / Auto Mode active | High |
| A8 | Consolidation / descheduler | NodePool consolidation or descheduler | underutilized nodes are reclaimed | Medium |
| A13 | HPA + VPA coverage for right-sizing | areas 11/12 | stateless workloads have HPA; VPA present for request tuning | Medium |
| A14 | PDBs don't block scale-down | area 14 (`pdb_blocking`) | no blocking PDBs (`minAvailable:100%`/`maxUnavailable:0`) | Medium |
| A15 | Instance-store for ephemeral scratch | node instance types + workloads | heavy-scratch/cache workloads consider instance-store over large EBS | Low |
| A23 | Fargate for spiky / low-density workloads | `eks.listFargateProfiles` + workload profile | bursty, low-density, or per-pod-isolated workloads considered for Fargate vs always-on nodes; Architectural consideration, not a defect; steady dense workloads may favor EC2/Karpenter. | Low |

## Storage (A3–A4, A12, A16–A18)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| A3 | gp3 over gp2 | StorageClasses `parameters.type` | no gp2 StorageClasses | Medium |
| A4 | No unused PVCs | PVCs vs pod mounts | no orphaned (unmounted) PVCs | Medium |
| A12 | EFS vs EBS appropriateness | PV CSI drivers | EFS only where ReadWriteMany needed | Low |
| A16 | EFS lifecycle / IA storage class | EFS PV config (AWS-API confirm) | infrequent-access lifecycle policy where data is cold | Low |
| A17 | EBS backup retention bounded | VolumeSnapshots / DLM | snapshot retention has a policy (not unbounded) | Low |
| A18 | Right-sized EBS volumes | PVC sizes vs usage | volumes not heavily over-provisioned | Low |

## Networking (A9–A11, A19–A20)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| A9 | No NodePort services | services type (`svcType`) | no `NodePort` (use LB/Ingress) | Medium |
| A10 | Ingress consolidation | areas 8/10 | many services share ALB/Ingress vs one LB per service | Medium |
| A11 | Topology-aware routing | service annotations | high-traffic services use topology-aware routing | Low |
| A19 | Cross-AZ traffic awareness | areas 7/36 (pod/node AZ) | chatty service-to-service paths consider AZ locality | Low |
| A20 | LB target-type IP | area 26 (LB annotations) | LB uses `target-type: ip` (cross-check N14) | Low |

## Observability & operations cost (A21–A26)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| A21 | Control-plane log selectivity | AWS-API (log config) | enable only needed CP log types; non-prod selective | Low |
| A22 | Telemetry volume / retention | area 29 + backends | log retention bounded; metric cardinality controlled; trace sampling applied | Low |
| A24 | Cost allocation tooling presence | `features.cost_optimization` + kube-system/opencost-ns pods | Kubecost, OpenCost, or AWS Split Cost Allocation Data (SCAD) is configured for workload-level cost attribution and produces actionable allocation data (cross-check A5); N/A on very small clusters where tooling overhead exceeds attribution value | Low |
| A25 | Log ingestion cost awareness | CloudWatch `LogIncomingBytes` metric for the cluster's log groups (AWS-API) | CloudWatch Logs ingestion for `/aws/eks/{cluster}/cluster` + application log groups is tracked; clusters ingesting > 100 GB/day have a cost-reduction plan (sampling, filtering, or tier to S3); N/A without CloudWatch metrics access. | Low |
| A26 | Non-production operating schedule | namespace/cluster labels (environment=dev/staging) + scaling config | non-production clusters or workloads have a scale-down or shutdown schedule for off-hours/weekends; N/A for production or explicitly always-on clusters. | Low |

## Manual / AWS-API checks (AM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| AM1 | VPC endpoints for AWS services | AWS-API | ECR/S3/STS/EC2/logs endpoints reduce NAT cost. |
| AM2 | ECR pull-through cache | AWS-API | reduces NAT Gateway charges for public pulls. |
| AM3 | Node utilization / idle spend | metrics | `kubectl top nodes`; low-utilization nodes → consolidate. |
| AM4 | Savings Plans / RI / EDP coverage | AWS billing | steady On-Demand baseline covered by commitments. |
| AM5 | Cost allocation / showback | AWS billing | CUR + Split Cost Allocation Data for EKS, or Kubecost/OpenCost, attributing spend to teams/namespaces. |
| AM6 | NAT Gateway data-processing spend | AWS billing | high NAT processing → add VPC endpoints / pull-through cache (AM1/AM2). |
| AM7 | Scheduled / off-hours scaling | process | scale non-prod down off-hours (scheduled scaling). |
