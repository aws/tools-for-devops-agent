# Aws Api remediations — shard 01

Canonical IDs: `AX1,AX2,AX3,AX4,AX5,AX6,AX7,AX8`

### AX1 — EKS Cluster Insights (no failing insights)
**Why it matters:** Cluster Insights is AWS's authoritative, continuously-evaluated signal for upgrade readiness and misconfiguration — it catches removed-API usage, deprecated kubelet/addon combos, and node-join blockers before they cause an outage or a failed upgrade.
**Steps:**
1. Read insights with the [`ListInsights`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListInsights.html) + [`DescribeInsight`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeInsight.html) operations (`aws eks list-insights` / `describe-insight`) or console. Filter `UPGRADE_READINESS` and `MISCONFIGURATION`.
2. For every insight not in `PASSING`, follow its `recommendation` and resolve before the next upgrade. Treat `MISCONFIGURATION` insights as live findings in the report.
**References:**
- [EKS — Cluster Insights](https://docs.aws.amazon.com/eks/latest/userguide/cluster-insights.html)
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### AX2 — Access entries have policies attached
**Why it matters:** An access entry that can authenticate but has no access policy and no Kubernetes group mapping grants zero permissions — a silent source of "I have access but can't do anything" lockouts and confusion. ARN typos produce entries that never match a real principal.
**Steps:**
1. List entries with [`ListAccessEntries`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAccessEntries.html); for each, [`DescribeAccessEntry`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeAccessEntry.html) + [`ListAssociatedAccessPolicies`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAssociatedAccessPolicies.html) (`aws eks list-access-entries` / `describe-access-entry` / `list-associated-access-policies`).
2. For an entry with no policy and no group: attach an appropriate EKS access policy (e.g. `AmazonEKSClusterAdminPolicy`, `AmazonEKSAdminPolicy`, `AmazonEKSAdminViewPolicy`) scoped to the right namespaces, or map it to RBAC groups.
3. Fix malformed/typo'd IAM role ARNs.
**References:**
- [EKS — Access entries](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html)
- [EKS Best Practices — Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html)

### AX3 — Authentication mode + aws-auth migration
**Why it matters:** `CONFIG_MAP`-only auth relies on the deprecated `aws-auth` ConfigMap; a malformed edit or a deleted cluster-creator role can lock everyone out with no recovery path short of support.
**Steps:**
1. `aws eks describe-cluster` → `accessConfig.authenticationMode`. Target `API` or `API_AND_CONFIG_MAP`.
2. Migrate principals from `aws-auth` to Access Entries (ideally via IAM Identity Center), then move toward `API` mode.
3. Ensure at least one durable admin access entry exists that doesn't depend on the original creator role.
**References:**
- [EKS — Cluster authentication mode](https://docs.aws.amazon.com/eks/latest/userguide/grant-k8s-access.html)
- [EKS Best Practices — Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html)

### AX4 — Managed nodegroup health & update status
**Why it matters:** A nodegroup in `CREATE_FAILED`/`DEGRADED`, or a rolling update stuck/`FAILED`, means capacity isn't coming online or an upgrade is wedged. `health.issues` carries the machine-readable root cause.
**Steps:**
1. Call [`DescribeNodegroup`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeNodegroup.html) (and [`ListUpdates`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListUpdates.html) / [`DescribeUpdate`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeUpdate.html) for an in-flight update). Read `status` and `health.issues`.
2. **Bootstrap/AMI conflict (CREATE_FAILED):** a launch template that supplies a bootstrap script **and** a custom AMI conflicts with EKS-injected bootstrap. Either specify a custom AMI and own the full bootstrap, or remove the script and let EKS inject it — not both.
3. **Stuck rolling update:** usually a PDB blocking eviction or insufficient surge capacity. Cross-reference Resilience R6/R7 (PDBs) and Control Plane Health CP10 (eviction stalls); adjust the PDB or add capacity.
**References:**
- [EKS — Managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)
- [EKS — Managed node group update behavior](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-group-update-behavior.html)

### AX5 — Managed addon health, version & upgrade conflicts
**Why it matters:** A managed addon in `DEGRADED`/`UPDATE_FAILED`, or with an unresolved `configurationConflict`, degrades a core data-path component cluster-wide — e.g. a CoreDNS addon update blocked by a ConfigMap conflict, or a VPC CNI update that left `aws-node` crashlooping and dropped custom config.
**Steps:**
1. Call [`ListAddons`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListAddons.html) + [`DescribeAddon`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeAddon.html). Read `status` and `health.issues` for each addon.
2. For a conflict, re-run the update with the documented `resolveConflicts` strategy (`PRESERVE` to keep custom field values, `OVERWRITE` to take the addon default) and re-apply preserved configuration values.
3. For a failed VPC CNI upgrade disrupting pod networking, roll back to the prior version and re-apply config before retrying.
**References:**
- [EKS — Managing add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)
- [EKS — Addon update / resolveConflicts](https://docs.aws.amazon.com/eks/latest/userguide/updating-an-add-on.html)

### AX6 — Pod Identity associations active
**Why it matters:** A Pod Identity association can't deliver credentials if the `eks-pod-identity-agent` isn't installed, or if the association's role trust policy / namespace / service-account mapping is wrong — pods then fall back to the node role or fail AWS calls outright.
**Steps:**
1. Confirm the agent: `kubectl get ds -n kube-system eks-pod-identity-agent` (or that the addon is `ACTIVE`). Install the EKS Pod Identity Agent add-on if missing.
2. List associations with [`ListPodIdentityAssociations`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListPodIdentityAssociations.html) → [`DescribePodIdentityAssociation`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribePodIdentityAssociation.html). Verify each maps the correct namespace + service account to an active role.
3. Verify the role trust policy allows `pods.eks.amazonaws.com` (`sts:AssumeRole` + `sts:TagSession`).
**References:**
- [EKS — Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [EKS — Pod Identity Agent setup](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)

### AX7 — Per-subnet IP availability
**Why it matters:** With VPC CNI, pods draw IPs from VPC subnets. A subnet near zero free IPs leaves new pods stuck `ContainerCreating` even though nodes have capacity — and per-subnet utilization is invisible to kubectl.
**Steps:**
1. Resolve cluster/pod subnets with [`DescribeCluster`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeCluster.html), then EC2 [`DescribeSubnets`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSubnets.html) and read `AvailableIpAddressCount` vs the subnet CIDR size.
2. For a constrained subnet: enable **prefix delegation** (`ENABLE_PREFIX_DELEGATION=true`) to raise IPs/ENI, add **custom networking** with secondary non-routable CIDRs, or adopt **IPv6** for new clusters. Size subnets for growth.
3. Monitor ongoing IP consumption with the CNI metrics helper (Observability O10).
**References:**
- [EKS Best Practices — IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html)
- [EKS Best Practices — Prefix Mode (Linux)](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html)

### AX8 — No EC2 instances failing to register
**Why it matters:** EC2 instances that launch but never register as Ready nodes are invisible to kubectl — capacity is paid for and absent. The usual cause is a network path the node can't use to reach the cluster endpoint.
**Steps:**
1. Compare ASG desired/running EC2 count (Auto Scaling [`DescribeAutoScalingGroups`](https://docs.aws.amazon.com/autoscaling/ec2/APIReference/API_DescribeAutoScalingGroups.html), EC2 [`DescribeInstances`](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html) filtered to the cluster's nodegroup tags) against `kubectl get nodes`.
2. For an instance that launched > 15 min ago and never joined: verify the **worker security group allows outbound TCP/443 to the cluster endpoint**, the cluster security group allows node↔control-plane traffic, and NACLs / VPC endpoints (ec2, ecr, sts, eks) permit the path.
3. Check the instance's user-data / bootstrap logs (SSM) for join errors.
**References:**
- [EKS — Worker node troubleshooting](https://docs.aws.amazon.com/eks/latest/userguide/troubleshooting.html)
- [re:Post — Worker nodes fail to join the cluster](https://repost.aws/knowledge-center/eks-worker-nodes-cluster)

