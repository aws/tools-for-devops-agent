# AWS-API & Cluster Insights checks (AX-series)

The fourth data source for an EKS review. The eight in-cluster pillars are graded from `kubectl`; the Control Plane Health pillar is graded from CloudWatch Logs; this component grades the facts that are **only visible from the AWS control-plane APIs and EKS Cluster Insights** — the layer that `kubectl` and CloudWatch logs cannot see.

It exists because a large share of real-world EKS support cases are rooted in AWS-side state that an in-cluster sweep marks `N/A`: access entries with no policy attached, nodegroups stuck in `CREATE_FAILED`, EC2 instances that launch but never register, per-subnet IP exhaustion, managed-addon upgrade conflicts, Pod Identity associations that aren't active, and the AWS Load Balancer Controller's IAM permissions. Cluster Insights is the authoritative AWS signal for upgrade readiness and misconfiguration. Promoting these from "AWS-API follow-up" to graded checks is what closes the review to full coverage.

Best-practice anchors: [Cluster Insights](https://docs.aws.amazon.com/eks/latest/userguide/cluster-insights.html) · [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html) · [Managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html) · [EKS add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html) · [Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) · [VPC CNI / IP optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html) · [AWS Load Balancer Controller](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html)

## Contents

- Data source — read this first
- Official AWS API operations used
- How to grade
- Cluster Insights (AX1)
- Access & authentication (AX2–AX3)
- Nodegroup & node-join health (AX4, AX8)
- Addon health (AX5)
- Workload IAM (AX6, AX9)
- IP & subnet capacity (AX7)
- Manual / config-surface checks (AX10–AX14)
- Finding → check map (full 15-row coverage)
- Relationship to other pillars

## Data source — read this first

This component is **not** graded from in-cluster `kubectl`. It reads the AWS control-plane APIs through the agent's authorized, read-only access path (`describe*` / `list*` / `get*` on the EKS / EC2 / IAM APIs). Use read-only credentials; never a mutating call.

Grade this component when:

- the review scope is "operations review" / "is it following best practices?" / a CWR (grade everything), **or**
- the user explicitly asks about access entries, nodegroup health, addons, Pod Identity, IP exhaustion, node join failures, or load balancer controller health, **and**
- the agent has read access to the EKS / EC2 / IAM APIs for the cluster's account.

If AWS-API access is unavailable, mark every check below **N/A**, state which API was unreachable, and flag it as a follow-up. Never guess an AWS-side fact.

> **Read-only.** Every call here is a `Describe` / `List` / `Get` / policy-simulation. This component never mutates AWS resources. Remediations are drafted for human approval.

## Official AWS API operations used

Every AX check maps to a documented, read-only AWS API operation (callable via `aws <service> <operation>` or any SDK). Cite the operation as the authoritative source. All EKS operations are in the [Amazon EKS API Reference](https://docs.aws.amazon.com/eks/latest/APIReference/Welcome.html).

| Check | EKS / EC2 / IAM API operation(s) | CLI |
|-------|----------------------------------|-----|
| AX1 | [`ListInsights`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListInsights.html), [`DescribeInsight`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeInsight.html) | `aws eks list-insights` / `describe-insight` |
| AX2 | [`ListAccessEntries`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAccessEntries.html), [`DescribeAccessEntry`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeAccessEntry.html), [`ListAssociatedAccessPolicies`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAssociatedAccessPolicies.html) | `aws eks list-access-entries` / `describe-access-entry` / `list-associated-access-policies` |
| AX3 | [`DescribeCluster`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeCluster.html) → `accessConfig.authenticationMode` | `aws eks describe-cluster` |
| AX4 | [`DescribeNodegroup`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeNodegroup.html), [`ListUpdates`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListUpdates.html), [`DescribeUpdate`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeUpdate.html) | `aws eks describe-nodegroup` / `list-updates` / `describe-update` |
| AX5 | [`ListAddons`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAddons.html), [`DescribeAddon`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeAddon.html) | `aws eks list-addons` / `describe-addon` |
| AX6 | [`ListPodIdentityAssociations`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListPodIdentityAssociations.html), [`DescribePodIdentityAssociation`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribePodIdentityAssociation.html), `DescribeAddon` (agent) | `aws eks list-pod-identity-associations` / `describe-addon` |
| AX7 | `DescribeCluster` (subnets) + EC2 [`DescribeSubnets`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSubnets.html) | `aws eks describe-cluster` + `aws ec2 describe-subnets` |
| AX8 | EC2 [`DescribeInstances`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html), Auto Scaling [`DescribeAutoScalingGroups`](https://docs.aws.amazon.com/autoscaling/ec2/APIReference/API_DescribeAutoScalingGroups.html), `DescribeNodegroup` | `aws ec2 describe-instances` + `aws autoscaling describe-auto-scaling-groups` |
| AX9 | IAM [`ListAttachedRolePolicies`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListAttachedRolePolicies.html), [`GetRolePolicy`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetRolePolicy.html), [`SimulatePrincipalPolicy`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html) | `aws iam list-attached-role-policies` / `get-role-policy` / `simulate-principal-policy` |
| AX10 | `DescribeCluster` → `logging` | `aws eks describe-cluster` |
| AX11 | `DescribeCluster` → `encryptionConfig` | `aws eks describe-cluster` |
| AX12 | `DescribeCluster` → `resourcesVpcConfig` | `aws eks describe-cluster` |
| AX13 | `DescribeCluster` → `tags`, `DescribeNodegroup` → `tags`, EC2 [`DescribeVolumes`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumes.html)/`DescribeInstances` → `Tags` | `aws eks describe-cluster` / `describe-nodegroup` + `aws ec2 describe-volumes` |
| AX14 | EFS [`DescribeMountTargets`](https://docs.aws.amazon.com/efs/latest/ug/API_DescribeMountTargets.html), [`DescribeMountTargetSecurityGroups`](https://docs.aws.amazon.com/efs/latest/ug/API_DescribeMountTargetSecurityGroups.html) + EC2 `DescribeSecurityGroups` | `aws efs describe-mount-targets` / `describe-mount-target-security-groups` + `aws ec2 describe-security-groups` |

Use only these documented read-only operations — never an undocumented or mutating call.

## How to grade

1. Resolve cluster identity (name, region, account) — already confirmed in SKILL.md Step 0.
2. Run **AX1 (Cluster Insights) first** — it is the authoritative AWS signal and often explains findings the other checks confirm in detail.
3. Run the remaining AX checks for the requested pillars (see the per-finding map below). Fan out independent `Describe`/`List` calls in parallel.
4. Grade each **PASS / FAIL / N/A** with the AWS-observed value as evidence.
5. For each FAIL, resolve the check ID through [`remediations/index.md`](remediations/index.md) and load only the returned shard or control-plane playbook.

## Cluster Insights (AX1)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX1 | EKS Cluster Insights — no failing insights | `ListInsights` + `DescribeInsight` | no insight in `ERROR`/`WARNING` for `UPGRADE_READINESS` or `MISCONFIGURATION` | High | Cluster Insights is the authoritative AWS readiness/misconfig signal. Resolve every failing insight before an upgrade; treat `MISCONFIGURATION` insights as live findings. Escalate to Critical when a failing `UPGRADE_READINESS` insight blocks an imminent upgrade. |

## Access & authentication (AX2–AX3) — closes finding #8

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX2 | Access entries have policies attached | `ListAccessEntries` + `DescribeAccessEntry` + `ListAssociatedAccessPolicies` | every access entry either maps to a Kubernetes group/RBAC or has an EKS access policy associated; no entry left able to authenticate with zero authorization; no malformed/typo'd IAM role ARNs | High | An access entry with no access policy and no group mapping can authenticate but has zero permissions — a silent lockout/confusion source. Attach an appropriate access policy (e.g. `AmazonEKSClusterAdminPolicy` / `AmazonEKSAdminViewPolicy`) or map to RBAC groups. Fix ARN typos. |
| AX3 | Authentication mode + aws-auth migration | `DescribeCluster` → `accessConfig.authenticationMode` | mode is `API` or `API_AND_CONFIG_MAP`; not relying solely on the deprecated `aws-auth` ConfigMap; cluster-creator lockout risk mitigated | Medium | Migrate to the Cluster Access Management (CAM) API with Access Entries (ideally via IAM Identity Center). `CONFIG_MAP`-only mode and a deleted creator role can lock everyone out. Confirms in-cluster S12. |

## Nodegroup & node-join health (AX4, AX8) — closes findings #10, #13, #14

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX4 | Managed nodegroup health & update status | `DescribeNodegroup` + `ListUpdates` + `DescribeUpdate` | nodegroup `status` is `ACTIVE` (not `CREATE_FAILED`/`DEGRADED`); `health.issues` empty; no rolling update stuck/`FAILED` | High | Read `health.issues` for the root cause (e.g. launch-template + bootstrap conflict → CREATE_FAILED; PDB blocking eviction → update stalled). For bootstrap/AMI conflicts: a launch template that includes a bootstrap script **and** a custom AMI conflicts with EKS-injected bootstrap — remove one. For stuck updates, cross-reference Resilience R6/R7 (PDBs) and Control Plane Health CP10 (eviction stalls). |
| AX8 | No EC2 instances failing to register | EC2 `DescribeInstances` + Auto Scaling `DescribeAutoScalingGroups` + `DescribeNodegroup`, cross-referenced with `kubectl get nodes` | every running worker instance for the cluster's nodegroups/ASGs is registered as a Ready node; no instance launched > 15 min ago that never joined | High | Instances that launch but never register are invisible to kubectl — compare ASG desired/running EC2 count to registered node count. Common causes: worker security group missing outbound TCP/443 to the cluster endpoint, NACL/VPC-endpoint gaps, or wrong cluster security group. Verify the cluster security group allows node↔control-plane traffic. |

## Addon health (AX5) — closes findings #1, #2, #15

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX5 | Managed addon health, version & upgrade conflicts | `ListAddons` + `DescribeAddon` | each managed addon (vpc-cni, coredns, kube-proxy, ebs-csi, pod-identity-agent) `status` is `ACTIVE`; no `DEGRADED`/`CREATE_FAILED`/`UPDATE_FAILED`; version ≤ 1 minor behind; no unresolved `configurationConflict` | High | `health.issues` surfaces upgrade failures: a CoreDNS addon update blocked by a ConfigMap conflict, or a VPC CNI update that left `aws-node` crashlooping with lost custom config. Resolve conflicts with the documented `resolveConflicts=PRESERVE/OVERWRITE` strategy and re-apply preserved config values; roll back a failed CNI upgrade if pod networking is disrupted. Confirms in-cluster N1/N2 and Op3/Op7. |

## Workload IAM (AX6, AX9) — closes findings #7, #11

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX6 | Pod Identity associations active | `ListPodIdentityAssociations` + `DescribePodIdentityAssociation` + `DescribeAddon` (agent) + `kubectl get ds -n kube-system eks-pod-identity-agent` | for workloads using Pod Identity: the `eks-pod-identity-agent` addon/DaemonSet is installed and Ready, and each association maps the right namespace/service account to an active role with a valid trust policy | High | A Pod Identity association can't work if the agent isn't installed — install the EKS Pod Identity Agent add-on. Verify the association's role trust policy allows `pods.eks.amazonaws.com` and the SA/namespace match. Cross-references in-cluster S13. |
| AX9 | Controller IAM permissions (LBC + others) | resolve the controller's SA → IRSA/Pod-Identity role, then IAM `ListAttachedRolePolicies` + `GetRolePolicy` (or `SimulatePrincipalPolicy`) | the AWS Load Balancer Controller's role grants the documented `elasticloadbalancing:*`, `ec2:Describe*`, `wafv2`, `shield` actions; controller SA is annotated with a valid role | Medium | The dominant LBC failure mode is IAM: the controller can't create an ALB/NLB because its role is missing `elasticloadbalancing:CreateLoadBalancer` (etc.). Attach the official LBC IAM policy to the controller's service-account role. Apply the same SA→role→policy check to other IRSA/Pod-Identity controllers (ExternalDNS, EBS CSI, Karpenter) when they're degraded. |

## IP & subnet capacity (AX7) — closes finding #3

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX7 | Per-subnet IP availability | `DescribeCluster` (subnets) + EC2 `DescribeSubnets` → `AvailableIpAddressCount` vs CIDR size | every cluster/pod subnet has meaningful IP headroom (e.g. > 10% free and an absolute floor); no subnet near exhaustion given node/pod growth | High | Per-subnet utilization is invisible to kubectl — read `AvailableIpAddressCount` per subnet. A subnet near zero free IPs leaves new pods stuck `ContainerCreating`. Mitigate with prefix delegation, custom networking (secondary non-routable CIDRs), or IPv6; size subnets for growth. Confirms/quantifies in-cluster N3. |

## Manual / config-surface checks (AX10–AX14)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| AX10 | Control-plane logging enabled | `DescribeCluster` → `logging` | at least `api` + `audit` enabled (gates the Control Plane Health pillar) | Medium | Without `api`/`audit` logs, the Control Plane Health pillar (etcd/APF/latency) can't be graded. Enable [control-plane logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html). |
| AX11 | Secrets envelope encryption (KMS) | `DescribeCluster` → `encryptionConfig` | KMS envelope encryption configured for `secrets` | Medium | Enable KMS envelope encryption for at-rest defense-in-depth. Confirms in-cluster SM1. |
| AX12 | Endpoint exposure | `DescribeCluster` → `resourcesVpcConfig` | private access on; `publicAccessCidrs` not `0.0.0.0/0` if public access is enabled | High | A public endpoint open to `0.0.0.0/0` is an attack surface. Restrict `publicAccessCidrs` or use private-only access. Confirms in-cluster SM3. |
| AX13 | AWS resource tagging (cost allocation / ownership) | `DescribeCluster` → `tags`, `DescribeNodegroup` → `tags`, EC2 `DescribeVolumes`/`DescribeInstances` → `Tags` | the cluster and its AWS resources (nodegroups, EBS volumes, load balancers) carry the org's required tags — at minimum `Environment`, `Owner`, `CostCenter` | Low | Missing tags break cost allocation, ownership routing, and tag-based access control. Apply the org's mandatory tag set to the cluster and its managed resources (Karpenter propagates tags via `EC2NodeClass.spec.tags`; managed nodegroups via `tags`). Satisfies the common-check baseline **COp1**; complements the in-cluster namespace-label check **Op5**. **N/A** in kubectl-only mode — flag for AWS-API follow-up. |
| AX14 | EFS mount-target availability & NFS reachability | EFS `DescribeMountTargets` + `DescribeMountTargetSecurityGroups` + EC2 `DescribeSecurityGroups` | for EFS-backed PVs: a mount target exists in **every AZ** that has worker nodes, and each mount-target security group allows inbound TCP **2049** (NFS) from the node/cluster security group | High | EFS is mounted per-AZ through mount targets — a pod on a node in an AZ with no mount target, or where NFS port 2049 is blocked, hangs on mount and the pod stays `ContainerCreating`. Create a mount target in each worker AZ and allow inbound 2049 from the node SG. Complements the in-cluster S27 (EFS Access Points). **N/A** if no EFS in use / no AWS-API access. |

## Finding → check map (full 15-row coverage)

This is how the AX-series, the kubectl pillars, and the Control Plane Health pillar together cover the enablement findings list end-to-end. "Detect" means the review raises a graded PASS/FAIL with evidence — not the live notification/EventBridge delivery, which is a separate pipeline.

| # | Finding | Graded by (check IDs) | Primary data source |
|---|---------|-----------|---------------------|
| 1 | CoreDNS degradation | N10, N19, Sc6, O7, O8 + **AX5** (addon/ConfigMap conflict) | kubectl + AWS-API |
| 2 | VPC CNI / pod networking health | N1, N3, N11 + **AX5** | kubectl + AWS-API |
| 3 | IP exhaustion (per-subnet) | N3, O10 + **AX7** | AWS-API |
| 4 | Resource tagging / ownership gaps | **AX13** (+ in-cluster Op5) | AWS-API |
| 5 | Webhook misconfiguration | S16, S17, S33, S34, Sc19, CP-M4 | kubectl + metrics |
| 6 | etcd storage pressure | CP1, CP2, CP3 (checks) | CloudWatch |
| 7 | AWS LB Controller health | N13, N14 + **AX9** (IAM) | kubectl + AWS-API |
| 8 | Access entry / aws-auth misconfig | **AX2, AX3** (+ in-cluster S12) | AWS-API |
| 9 | API server SLO breach | CP6, CP7 (checks) | CloudWatch |
| 10 | MNG rolling update stuck | R6, R7, CP10 (eviction stalls) + **AX4** | kubectl + CloudWatch + AWS-API |
| 11 | Pod Identity failures | S13 + **AX6, AX9** | kubectl + AWS-API |
| 12 | Node resource exhaustion | **Op25** (node conditions: Disk/Memory/PID pressure, NotReady) | kubectl |
| 13 | Worker node join failure (networking) | **AX8, AX1** | AWS-API + Cluster Insights |
| 14 | Worker node join failure (bootstrap/AMI) | **AX4, AX1** | AWS-API + Cluster Insights |
| 15 | VPC CNI addon upgrade failure | **AX5** (+ O8) | AWS-API |
| 16 | API server throttling (429s) | CP4, CP5 (checks) | CloudWatch |

> All "Graded by" entries are **check IDs** (never Logs-Insights query IDs).

## Relationship to other pillars

- **Security (S-series)** grades pod/RBAC/network posture from kubectl; AX2/AX3/AX11/AX12 add the AWS-side access/encryption/endpoint facts S12/SM1/SM3 mark N/A.
- **Operations (Op-series)** grades addon/version hygiene from kubectl; AX4/AX5 add the AWS-side nodegroup/addon health and confirm Op3/Op7.
- **Networking (N-series)** grades the in-cluster data path; AX7 adds the per-subnet IP capacity NM4 marks N/A.
- **Control Plane Health (CP-series)** grades control-plane saturation from CloudWatch; AX10 gates whether that pillar can run.
