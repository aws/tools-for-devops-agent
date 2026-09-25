# Aws Api remediations — shard 02

Canonical IDs: `AX9,AX10,AX11,AX12,AX13,AX14`

### AX9 — Controller IAM permissions (LBC + others)
**Why it matters:** The dominant AWS Load Balancer Controller failure is IAM: the controller can't create an ALB/NLB because its service-account role is missing `elasticloadbalancing:CreateLoadBalancer` (and related actions). The same SA→role→policy gap breaks ExternalDNS, EBS CSI, and Karpenter.
**Steps:**
1. Resolve the controller SA's role: read the SA's IRSA annotation (`eks.amazonaws.com/role-arn`) or its Pod Identity association, then IAM [`ListAttachedRolePolicies`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListAttachedRolePolicies.html) + [`GetRolePolicy`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetRolePolicy.html) (or [`SimulatePrincipalPolicy`](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html)).
2. Confirm the role carries the official LBC IAM policy (`elasticloadbalancing:*`, `ec2:Describe*`, `wafv2`, `shield`, `acm` as documented). Attach/repair it.
3. For other degraded controllers, apply the same check against their documented policy.
**References:**
- [EKS — AWS Load Balancer Controller](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html)
- [AWS Load Balancer Controller — IAM policy](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/installation/)

### AX10 — Control-plane logging enabled
**Why it matters:** Without `api` + `audit` control-plane logs, the Control Plane Health pillar (etcd/APF/LIST latency) can't be graded — those signals live only in the audit log.
**How to verify / fix:** `aws eks describe-cluster` → `logging`. Enable at least `api` and `audit` log types.
**References:**
- [EKS — Control plane logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)

### AX11 — Secrets envelope encryption (KMS)
**Why it matters:** Without KMS envelope encryption, Kubernetes Secrets are stored without an additional at-rest encryption layer — a defense-in-depth gap.
**How to verify / fix:** `aws eks describe-cluster` → `encryptionConfig`. Enable KMS envelope encryption for the `secrets` resource.
**References:**
- [EKS Best Practices — Data Encryption & Secrets](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html)

### AX12 — Endpoint exposure
**Why it matters:** A cluster API endpoint open to `0.0.0.0/0` is an internet-facing attack surface.
**How to verify / fix:** `aws eks describe-cluster` → `resourcesVpcConfig`. Enable private access; if public access is on, restrict `publicAccessCidrs` to known ranges.
**References:**
- [EKS — Cluster endpoint access control](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)
- [EKS Best Practices — Network Security](https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html)

### AX13 — AWS resource tagging (cost allocation / ownership)
**Why it matters:** Missing `Environment`/`Owner`/`CostCenter` tags on the cluster and its AWS resources break cost allocation, ownership routing, and tag-based access control. This check also carries the shared `review-common` baseline COp1.
**Steps:**
1. Read tags: `aws eks describe-cluster --query cluster.tags`, `aws eks describe-nodegroup --query nodegroup.tags`, `aws ec2 describe-volumes --filters Name=tag:kubernetes.io/cluster/${CLUSTER},Values=owned --query 'Volumes[].Tags'`.
2. Apply the org's mandatory tag set to the cluster and nodegroups (`aws eks tag-resource` — drafted for human approval, not executed by the review).
3. Propagate to dynamic resources: Karpenter via `EC2NodeClass.spec.tags`; managed nodegroups via their `tags` field; EBS via the CSI driver's `--extra-tags` / StorageClass `tagSpecification` parameters.
**References:**
- [EKS — Tagging your resources](https://docs.aws.amazon.com/eks/latest/userguide/eks-using-tags.html)
- [AWS — Cost allocation tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)

### AX14 — EFS mount-target availability & NFS reachability *(AWS-API)*
**Why it matters:** EFS is mounted per-AZ through mount targets — a pod on a node in an AZ with no mount target, or where NFS port 2049 is blocked, hangs on mount and the pod stays `ContainerCreating`.
**How to verify / fix:** `aws efs describe-mount-targets --file-system-id ${FS}` (one per worker AZ) and `describe-mount-target-security-groups` → confirm inbound TCP 2049 from the node SG. Complements S27 (EFS Access Points). **N/A** if no EFS / no AWS-API access.
**References:**
- [Amazon EFS — Using VPC security groups (NFS 2049)](https://docs.aws.amazon.com/efs/latest/ug/network-access.html)
