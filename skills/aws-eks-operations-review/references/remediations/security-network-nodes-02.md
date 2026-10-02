# Security Network Nodes remediations — shard 02

Canonical IDs: `S24,S25,S26,S27,S28,S29,S30,S31`

### S24 — Container-optimized node OS
**Why it matters:** General-purpose or custom AMIs carry a larger attack surface and a heavier patch burden than purpose-built container OSes. Bottlerocket (immutable, minimal, SELinux-enforcing) and AL2023 / EKS-optimized AMIs reduce both.
**Steps:**
1. Inspect: `kubectl get nodes -o custom-columns=NAME:.metadata.name,OS:.status.nodeInfo.osImage,RUNTIME:.status.nodeInfo.containerRuntimeVersion`
2. Migrate general-purpose/custom AMIs to Bottlerocket or AL2023 via the MNG AMI type or Karpenter `EC2NodeClass.amiFamily`.
**N/A** on Fargate / Auto Mode (AWS-managed OS).
**References:**
- [EKS Best Practices — Infrastructure Security](https://docs.aws.amazon.com/eks/latest/best-practices/infrastructure-security.html)
- [Bottlerocket](https://aws.amazon.com/bottlerocket/)

### S25 — Minimized node access (SSM over SSH)
**Why it matters:** Open SSH (port 22) on worker nodes is a standing attack surface and a credential-management burden. SSM Session Manager gives audited, key-less, IAM-gated break-glass access with no inbound port.
**Steps:**
1. Check for SSH exposure: launch-template key pairs and security-group rules allowing TCP 22 (especially from `0.0.0.0/0`) — AWS-API.
2. Remove the SSH ingress and key pairs; attach `AmazonSSMManagedInstanceCore` to the node role and use `aws ssm start-session`.
**N/A** in kubectl-only mode (SG/launch-template facts need AWS-API) — flag for follow-up.
**References:**
- [EKS Best Practices — Infrastructure Security](https://docs.aws.amazon.com/eks/latest/best-practices/infrastructure-security.html)
- [Systems Manager — Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)

### S26 — No long-lived ServiceAccount-token auth
**Why it matters:** A manually-created `kubernetes.io/service-account-token` Secret is a static, non-expiring credential. If it leaks it grants the SA's access until the Secret is deleted — there is no rotation. Modern clusters should use short-lived projected tokens, and AWS workloads should use IRSA / Pod Identity.
**Steps:**
1. Find static SA-token Secrets: `kubectl get secrets -A --field-selector type=kubernetes.io/service-account-token -o wide` (legacy auto-created ones are expected on older clusters; flag any used as kubeconfig credentials).
2. Replace with `TokenRequest`-projected volumes (auto-mounted, short-lived) for in-cluster, and IRSA / Pod Identity for AWS access; delete the static Secret after migrating.
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Kubernetes — Bound Service Account Tokens](https://kubernetes.io/docs/concepts/security/service-accounts/#bound-service-account-tokens)

### S27 — EFS Access Points for shared storage
**Why it matters:** Mounting the EFS file-system root gives every consuming pod the same broad path and POSIX identity — one compromised or buggy app can traverse another tenant's data. EFS Access Points enforce a fixed root directory and POSIX user/group per application, isolating tenants on a shared file system.
**Steps:**
1. Inventory EFS-backed PVs: check the EFS CSI driver `PersistentVolume` specs for `volumeHandle` using the FS root vs an `accessPointID` (`fs-xxxx::fsap-xxxx`).
2. Create an Access Point per application (enforced UID/GID + root dir) and reference it in the StorageClass / PV.
**Snippet:**
```yaml
# EFS CSI StorageClass using an access point
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-0123456789abcdef0
  directoryPerms: "700"
```
**N/A** if no EFS in use or no AWS-API access.
**References:**
- [EFS — Working with access points](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html)
- [EFS CSI driver — Access points](https://github.com/kubernetes-sigs/aws-efs-csi-driver/tree/master/examples/kubernetes/access_points)

### S28 — IMDSv2 enforced on nodes
**Why it matters:** With IMDSv1, any pod that has network egress can reach `169.254.169.254` and retrieve the node's **instance-profile credentials** — an SSRF/escape path to whatever the node role can do. IMDSv2 (token-required) plus a hop limit of 1 blocks pods from the metadata endpoint.
**Steps:**
1. Karpenter: set `metadataOptions` on the EC2NodeClass. MNG/self-managed: set it on the launch template (AWS-API to confirm `HttpTokens=required`, `HttpPutResponseHopLimit=1`).
2. Also block pod access to the node IMDS at the network layer where feasible (and prefer IRSA/Pod Identity so pods never need node creds).
**Snippet:**
```yaml
# Karpenter EC2NodeClass
spec:
  metadataOptions:
    httpTokens: required          # IMDSv2 only
    httpPutResponseHopLimit: 1     # pods (extra hop) can't reach IMDS
    httpEndpoint: enabled
```
**N/A** on Auto Mode (AWS-managed node config) / kubectl-only mode (launch-template is AWS-API).
**References:**
- [EKS Best Practices — Identity and Access Management (IMDS)](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [EC2 — Use IMDSv2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html)

### S29 — No anonymous / unauthenticated RBAC bindings
**Why it matters:** A RoleBinding or ClusterRoleBinding to `system:anonymous` or the `system:unauthenticated` group grants **unauthenticated** callers whatever that role allows — a direct, unauthenticated access path into the cluster. This is distinct from S10 (cluster-admin to named principals).
**Steps:**
1. Find them: `kubectl get clusterrolebindings,rolebindings -A -o json | jq -r '.items[] | select(.subjects[]?? | (.name=="system:anonymous") or (.name=="system:unauthenticated")) | .metadata.name'`
2. Delete the offending binding (or scope it to an authenticated subject). Verify no legitimate component depends on it first.
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Kubernetes — RBAC: anonymous requests](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#anonymous-requests)

### S30 — VPC flow logs enabled *(AWS-API)*
**Why it matters:** VPC flow logs are the network forensic record — without them, investigating an intrusion, data-exfiltration, or pod-connectivity issue has no packet-flow evidence.
**How to verify / fix:** `ec2.describeFlowLogs` filtered by the cluster VPC; enable VPC-level flow logs to CloudWatch Logs or S3 if absent. Sample at the VPC level (cheaper than per-ENI) for baseline coverage.
**N/A** in kubectl-only mode — flag for AWS-API follow-up.
**References:**
- [VPC — Flow logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)

### S31 — Tenant workload isolation
**Why it matters:** Pods sharing a node share the kernel — soft multi-tenancy means a compromised or hostile pod is one kernel bug away from its neighbors. Co-scheduling untrusted/multi-tenant workloads with sensitive ones raises blast radius.
**Steps:**
1. Isolate sensitive or per-tenant workloads onto dedicated node pools using **taints + tolerations** and `nodeAffinity`/`nodeSelector`.
2. Pair with default-deny NetworkPolicy (S15), ResourceQuotas (P7), and (for hard isolation) separate clusters/accounts.
**Snippet:**
```yaml
# dedicated nodes: taint the pool, tolerate on the workload
# nodepool: taints: [{ key: tenant, value: payments, effect: NoSchedule }]
tolerations: [{ key: tenant, operator: Equal, value: payments, effect: NoSchedule }]
affinity: { nodeAffinity: { requiredDuringSchedulingIgnoredDuringExecution: {
  nodeSelectorTerms: [{ matchExpressions: [{ key: tenant, operator: In, values: [payments] }] }] } } }
```
**N/A** for single-tenant clusters.
**References:**
- [EKS Best Practices — Multi-tenancy / Tenant Isolation](https://docs.aws.amazon.com/eks/latest/best-practices/multitenancy.html)

## Security — manual / AWS-API (SM)

