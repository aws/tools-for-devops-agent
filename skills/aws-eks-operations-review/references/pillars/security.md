# Pillar: Security

Cluster access, pod security, network isolation, secrets, and image hygiene. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html) · [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html) · [Network Security](https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html) · [Runtime Security](https://docs.aws.amazon.com/eks/latest/best-practices/runtime-security.html) · [Data Encryption & Secrets](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html) · [Image Security](https://docs.aws.amazon.com/eks/latest/best-practices/image-security.html) · [Auditing & Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html)

Reads discovery areas: 21 NETWORKPOLICIES, 22 RBAC, 24 WEBHOOKS, 34 SECURITY, 39 IMAGE_SECURITY, 42 SECRETS_MANAGEMENT, 43 SERVICE_ACCOUNTS, 46 MULTI_TENANCY.

> **AWS-side access/encryption facts** (access-entry policies, authentication mode, KMS encryption, endpoint exposure, Pod Identity associations, controller IAM) are graded by the **AWS-API component** ([`../aws-api-checks.md`](../aws-api-checks.md), AX2/AX3/AX6/AX9/AX11/AX12) — they confirm/replace the N/A on S12/S13/SM1/SM3. In kubectl-only mode those stay N/A here.

## Currency framing (read first)

- **Access management:** the `aws-auth` ConfigMap is **deprecated**. Standard is the Cluster Access Management (CAM) API with **Access Entries** + `API` auth mode (ideally via IAM Identity Center). `aws_auth_present=true` is a migration finding; confirm `authenticationMode` via AWS-API.
- **Workload IAM:** **EKS Pod Identity is preferred over IRSA** for new workloads (no OIDC, session tagging/ABAC). IRSA is acceptable; note Pod Identity as the forward path. On Auto Mode the Pod Identity Agent is pre-deployed.
- **Pod security:** PSA `restricted` is the target.
- **Network policy:** VPC CNI Network Policy is **not on by default**; default-deny per namespace + DNS-allow is the baseline. No NetworkPolicies = allow-all east/west.
- **Node IAM (Auto Mode):** uses `AmazonEKSWorkerNodeMinimalPolicy` (least privilege) — don't flag missing traditional node policies on Auto Mode.

## Pod security (S1–S9)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| S1 | No privileged containers | `privileged_pods` | none privileged (outside known system) | Critical |
| S2 | No host namespaces | `hostnetwork/pid/ipc_pods` | no `hostNetwork`/`hostPID`/`hostIPC` (outside system) | High |
| S3 | allowPrivilegeEscalation=false | `privilege_escalation_allowed` | all containers set it false | High |
| S4 | Drop ALL capabilities | `capabilities_not_dropped` | containers drop `ALL`, add back only needed | High |
| S5 | seccomp RuntimeDefault | `seccomp_not_runtimedefault` | pods set `seccompProfile=RuntimeDefault` | Medium |
| S6 | readOnlyRootFilesystem | `readonly_rootfs_*` | serving containers use read-only rootfs | Medium |
| S7 | runAsNonRoot | `runasnonroot_true` | containers run as non-root | High |
| S8 | No hostPath volumes | `hostpath_pods` | no hostPath (or restricted prefix + read-only) | High |
| S9 | Pod Security Admission configured | namespace PSS labels | namespaces enforce `baseline`/`restricted` | Medium |

## Access & RBAC (S10–S14)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| S10 | No cluster-admin to non-system principals | ClusterRoleBindings | no cluster-admin outside `system:masters` | Critical |
| S11 | No wildcard RBAC | ClusterRoles rules | no `*` verbs+resources+apiGroups (excl. system) | High |
| S12 | Access Entries / API auth mode | `aws_auth_present` + AWS-API | not relying on deprecated aws-auth; `API` mode | Medium |
| S13 | IRSA / Pod Identity for workloads | `features.security.{irsa,pod_identity}` | workloads use IRSA or Pod Identity (not node role) | High |
| S14 | automountServiceAccountToken disabled where unused | SA/pod `automountServiceAccountToken` | set false where API access not needed | Medium |

## Network, webhooks, secrets, images, nodes (S15–S36)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| S15 | NetworkPolicy default-deny coverage | area 21/46 | each workload namespace has a default-deny + DNS-allow | High |
| S16 | No webhook catch-all rules | webhook rules | no `apiGroups:["*"]` AND `resources:["*"]` | High |
| S17 | Webhook failurePolicy on system NS | webhook `failurePolicy` | no `Fail` scoped to kube-system/kube-public | High |
| S18 | External secrets management | `features.security` + area 42 | ESO / Secrets Store CSI / Sealed Secrets in use | Medium |
| S19 | Secrets via volume not env | pod spec | secrets mounted as volumes, not env vars | Low |
| S20 | Image pull policy / no :latest | area 39 | no `:latest`/untagged; explicit tags | Medium |
| S21 | Image scanning present | `features.security` (trivy/etc.) | scanning tool detected | Medium |
| S22 | GuardDuty EKS protection | `features.security.guardduty` | GuardDuty agent / EKS protection present | Medium |
| S23 | Policy enforcement engine | `features.security` + area 24 webhooks | Kyverno / Gatekeeper (OPA) / validating policy engine present; N/A when PSA `restricted` alone meets the requirement (cross-check S9) | Medium |
| S24 | Container-optimized node OS | area 2 node `osImage` / AMI type | nodes run a hardened container OS (Bottlerocket / AL2023 / EKS-optimized) not a general-purpose distro; General-purpose/custom AMIs pass only with a documented hardening approach; N/A on Fargate/Auto Mode. | High |
| S25 | Minimized node access (SSM over SSH) | area 2 nodes + AWS-API (launch template) | no broad SSH (port 22) ingress to nodes; SSM Session Manager used instead; AWS-API confirmation required; N/A in kubectl-only mode. | Medium |
| S26 | No long-lived ServiceAccount-token auth | area 43 SA + secrets | no manually-created `kubernetes.io/service-account-token` Secrets used as static kubeconfig credentials | High |
| S27 | EFS Access Points for shared storage | `elasticfilesystem.describeAccessPoints` (AWS-API) | EFS-backed PVs use Access Points (enforced POSIX user/path) rather than mounting the file-system root; N/A without EFS or AWS-API access. | Medium |
| S28 | IMDSv2 enforced on nodes | EC2NodeClass `metadataOptions` / launch template (AWS-API) | worker nodes require IMDSv2 (`httpTokens=required`) with hop limit 1; pods can't reach the node instance profile via IMDS; N/A on Auto Mode or in kubectl-only mode. | High |
| S29 | No anonymous / unauthenticated RBAC | area 22 ClusterRoleBindings/RoleBindings | no binding references `system:anonymous` or `system:unauthenticated` | Critical |
| S30 | VPC flow logs enabled | `ec2.describeFlowLogs` (AWS-API) | the cluster VPC (and/or subnets) has flow logs active to CloudWatch/S3; N/A in kubectl-only mode. | Medium |
| S31 | Tenant workload isolation | area 44 scheduling + 46 multi-tenancy + nodes | sensitive/multi-tenant workloads isolated onto dedicated nodes via taints+tolerations / nodeAffinity (not co-scheduled with untrusted workloads); N/A for single-tenant clusters; cross-check S15 and P7. | Medium |
| S32 | StorageClass encryption enabled | area 20 STORAGE — StorageClass `parameters.encrypted` (`kubectl get storageclass -o json`) | every dynamic-provisioning EBS/EFS StorageClass sets `parameters.encrypted: "true"` (plus `kmsKeyId` where a customer-managed key is required); Cross-check SM4, R19, and R16. | High |
| S33 | Admission webhook timeout & reinvocation bounded | area 24 WEBHOOKS — `timeoutSeconds` / `reinvocationPolicy` | webhooks use a low `timeoutSeconds` (≤10s, not the 30s max); mutating webhooks avoid unnecessary `reinvocationPolicy: IfNeeded`; Cross-check S16 and Sc19. | Medium |
| S34 | Webhook CA-bundle certificate validity | area 24 WEBHOOKS — `clientConfig.caBundle` (base64 → x509 `notAfter`) | no Mutating/ValidatingWebhookConfiguration has an expired or near-expiry (<30 days) `caBundle` certificate | High |
| S35 | Secrets Store CSI rotation enabled | area 42 SECRETS_MANAGEMENT — Secrets Store CSI driver args + SecretProviderClass | if the Secrets Store CSI driver is present, secret rotation is enabled (driver `--enable-secret-rotation=true` and a sane `--rotation-poll-interval`); N/A when Secrets Store CSI is not used. | Medium |
| S36 | VPC CNI dedicated IAM role (not node role) | area 43 SERVICE_ACCOUNTS — `aws-node` SA annotations (IRSA `eks.amazonaws.com/role-arn`) or a Pod Identity association | the `aws-node` (VPC CNI) service account uses its own scoped IAM role via IRSA or Pod Identity — not the shared node instance role; AWS-API AX9 confirms IAM scope; cross-check S28. | Medium |

## Manual / AWS-API checks (SM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| SM1 | KMS envelope encryption | AWS-API | `aws eks describe-cluster --query cluster.encryptionConfig`. |
| SM2 | Audit logging enabled | AWS-API | `aws eks describe-cluster --query cluster.logging` (audit type on). |
| SM3 | Endpoint exposure | AWS-API | `endpointPublicAccess` / `publicAccessCidrs` not `0.0.0.0/0`. |
| SM4 | EBS/EFS encryption at rest | StorageClass / EFS API | default SC `encrypted: true`; EFS encrypted. |
| SM5 | ECR immutable tags + Inspector | ECR / Inspector API | `imageTagMutability=IMMUTABLE`; Inspector ECR scanning on. |
| SM6 | mTLS between workloads | service mesh | Istio PeerAuthentication / Linkerd mTLS, if required. |
| SM7 | Node IAM least privilege | AWS-API / IAM | node role limited to required managed policies (or Auto Mode minimal policy). |

## Security services integration (S37–S39)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| S37 | GuardDuty EKS Protection enabled + no active High/Critical findings | `guardduty:ListDetectors` + `guardduty:ListFindings` (AWS-API) | GuardDuty EKS Audit Log Monitoring and EKS Runtime Monitoring are enabled for the cluster's account/region; no active `HIGH`/`CRITICAL` severity Kubernetes findings (`Kubernetes:*` types) for this cluster; N/A without AWS-API access or when GuardDuty is not enabled. | High |
| S38 | Inspector container image scanning | `inspector2:ListFindings` (AWS-API) filtered to container/ECR | Amazon Inspector ECR scanning is enabled; no `CRITICAL`/`HIGH` severity image CVE findings for images currently running in this cluster; N/A without AWS-API access, Inspector, or ECR images; cross-check S21. | High |
| S39 | Security Hub EKS controls passing | `securityhub:GetFindings` (AWS-API) filtered to EKS | Security Hub is enabled with the EKS controls standard; no `FAILED` controls for this cluster's resources; N/A without AWS-API access or Security Hub. | Medium |
