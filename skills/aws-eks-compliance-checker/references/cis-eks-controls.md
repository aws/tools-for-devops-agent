# CIS Amazon EKS Benchmark v1.8.0 controls

Load in Step 4 and keep it until Step 5 is done. Control IDs, titles, and the Automated/Manual type follow the CIS Amazon EKS Benchmark v1.8.0 as encoded in the open-source kube-bench `cfg/eks-1.8.0` profile. Titles are abridged.

## Contents

- Exclusions
- Evidence collection
- Section 2 — Control plane configuration
- Section 3 — Worker nodes
- Section 4 — Policies
- Section 5 — Managed services

## Exclusions

Apply these exclusions everywhere a rule says "non-system":

- **System namespaces:** `kube-system`, `kube-public`, `kube-node-lease`, and namespaces of EKS-managed add-ons (`amazon-cloudwatch`, `amazon-guardduty`, `aws-observability`).
- **System subjects:** names starting with `system:`, the `eks:` prefixed roles and bindings, and service accounts in system namespaces.
- **System roles (CIS 4.1.3 only):** ClusterRoles named `cluster-admin`, `admin`, `edit`, `view`, or starting with `system:` or `eks:`. They are excluded only from 4.1.3, which is about custom roles.

**Built-in roles still count for permission checks.** For 4.1.1, 4.1.2, 4.1.4, and 4.1.8–4.1.12, the question is which non-system subjects hold the permission, so evaluate every role a subject is bound to, built-in roles included. Only system subjects are excluded. `cluster-admin` grants every verb on every resource. The built-in `admin` and `edit` ClusterRoles grant `create` on `pods` and on `serviceaccounts/token`, and `get`/`list`/`watch` on `secrets`. A subject bound to `cluster-admin` therefore fails 4.1.1, 4.1.2, 4.1.4, and 4.1.8–4.1.12.

List each exclusion you actually used in the report's Scope section.

## Evidence collection

Run each read once with `use_kubectl`. Keep only the fields named.

| # | Read | Keep |
|---|---|---|
| K1 | `get clusterrolebindings -o json` | name, `roleRef.name`, subjects (kind, name, namespace) |
| K2 | `get rolebindings -A -o json` | namespace, name, `roleRef`, subjects |
| K3 | `get clusterroles -o json` | name, rules (apiGroups, resources, verbs) |
| K4 | `get roles -A -o json` | namespace, name, rules |
| K5 | `get serviceaccounts -A -o json` | namespace, name, `automountServiceAccountToken`, annotation `eks.amazonaws.com/role-arn` |
| K6 | `get pods -A -o json` (over 500 pods: `-o custom-columns` with namespace, name, serviceAccountName, automountServiceAccountToken, hostPID, hostIPC, hostNetwork, and per-container securityContext.privileged, securityContext.allowPrivilegeEscalation, env[].valueFrom.secretKeyRef, image) | the listed fields |
| K7 | `get namespaces -o json` | name, labels `pod-security.kubernetes.io/*` |
| K8 | `get networkpolicies -A -o json` | namespace, name, `podSelector`, `policyTypes` |
| K9 | `get configmap aws-auth -n kube-system -o json` | `mapRoles` and `mapUsers` entries (ARN, username, groups) only |
| K10 | `get daemonsets -n kube-system -o wide`, then `get daemonset aws-node -n kube-system -o jsonpath='{range .spec.template.spec.containers[*]}{.name} {.args}{"\n"}{end}'` | DaemonSet names and images (to identify Calico or Cilium), and the `aws-eks-nodeagent` container's `--enable-network-policy` argument |
| K11 | `get deployments,statefulsets,daemonsets -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name` | count of workloads in `default` |
| K12 | `get pods -A -o jsonpath` over `spec.volumes[*].csi.driver` | whether `secrets-store.csi.k8s.io` is used |
| K13 | `get crd -o name` | presence of `externalsecrets.external-secrets.io`, `secretproviderclasses.secrets-store.csi.x-k8s.io`, `sealedsecrets.bitnami.com` |

Never read Secret objects with `-o json` or `-o yaml`. For K6 on very large clusters, page by namespace.

A role "grants" a verb on a resource when any of its rules lists that verb (or `*`) for that resource (or `*`) in a matching API group (or `*`). Read the rules from K3 and K4 for built-in roles too, rather than assuming their contents.

## Section 2 — Control plane configuration

| ID | Type | Control | Evidence | Pass rule |
|---|---|---|---|---|
| 2.1.1 | Manual | Enable audit logs | AWS-E1 `logging.clusterLogging` | PASS if the `audit` type is enabled. FAIL otherwise. |
| 2.1.2 | Manual | Audit logs are collected and managed | AWS-E1 plus AWS-E9 log group retention | PASS if `audit` is enabled and log group `/aws/eks/<cluster>/cluster` has a retention period set. FAIL if audit is off. `Manual review` if audit is on but retention is unset, asking whether logs are exported to a SIEM. |

## Section 3 — Worker nodes

Controls 3.1.1–3.1.4 (kubeconfig and kubelet config file permissions and ownership) and 3.2.1–3.2.9 (kubelet arguments) need host access to each node. Report all 13 as `Not covered — needs node host access`, and recommend running kube-bench as a Job using the `eks-1.8.0` benchmark. For Fargate-only or EKS Auto Mode clusters, say AWS manages the node configuration.

## Section 4 — Policies

| ID | Type | Control | Evidence | Pass rule |
|---|---|---|---|---|
| 4.1.1 | Automated | cluster-admin only where required | K1 | PASS if no ClusterRoleBinding to `cluster-admin` has a non-system subject. FAIL lists each binding and subject. |
| 4.1.2 | Automated | Minimize access to secrets | K1–K4 | FAIL if any role, built-in or custom, bound to a non-system subject grants `get`, `list`, or `watch` on `secrets` cluster-wide, or `list`/`watch` in a namespace other than its own. PASS otherwise. |
| 4.1.3 | Automated | Minimize wildcard use in Roles and ClusterRoles | K3, K4 | FAIL lists each non-system Role or ClusterRole with `*` in verbs, resources, or apiGroups. PASS otherwise. |
| 4.1.4 | Automated | Minimize access to create pods | K1–K4 | FAIL if a ClusterRoleBinding binds a non-system subject to any role, built-in roles such as `cluster-admin`, `admin`, and `edit` included, that grants `create` on `pods` (or `*`). FAIL lists each binding, role, and subject. Grants made only through RoleBindings are `Manual review` listing the namespace, role, and subjects. PASS if neither. |
| 4.1.5 | Automated | Default service accounts are not actively used | K5, K6 | FAIL if a non-system pod runs as `default`, or a `default` service account in a non-system namespace lacks `automountServiceAccountToken: false`. PASS otherwise. |
| 4.1.6 | Automated | Service account tokens mounted only where necessary | K5, K6 | A pod's effective `automountServiceAccountToken` is the pod's own field if set, otherwise its service account's field, otherwise true. PASS only if every non-system pod's effective value is false. Otherwise `Manual review`: list those pods and ask which need Kubernetes API access. IRSA and EKS Pod Identity are not an exemption: each injects its own projected token volume and does not need the automounted API token. |
| 4.1.7 | Manual | Use the Cluster Access Manager API | AWS-E1 `accessConfig.authenticationMode`, K9 | PASS if mode is `API`, or `API_AND_CONFIG_MAP` with no `mapUsers` and no `mapRoles` beyond node roles. FAIL if mode is `CONFIG_MAP`. Otherwise FAIL listing the extra mappings. |
| 4.1.8 | Manual | Limit bind, impersonate, and escalate | K1–K4 | FAIL lists non-system subjects bound to any role, built-in or custom, granting `bind`, `impersonate`, or `escalate`. PASS otherwise. |
| 4.1.9 | Manual | Minimize access to create PersistentVolumes | K1–K4 | FAIL lists non-system subjects granted `create` on `persistentvolumes` by any role, built-in or custom. PASS otherwise. |
| 4.1.10 | Manual | Minimize access to the proxy sub-resource of nodes | K1–K4 | FAIL lists non-system subjects granted any verb on `nodes/proxy` by any role, built-in or custom. PASS otherwise. |
| 4.1.11 | Manual | Minimize access to webhook configuration objects | K1–K4 | FAIL lists non-system subjects granted, by any role built-in or custom, `create`, `update`, `patch`, or `delete` on `validatingwebhookconfigurations` or `mutatingwebhookconfigurations`. PASS otherwise. |
| 4.1.12 | Manual | Minimize access to service account token creation | K1–K4 | FAIL lists non-system subjects granted `create` on `serviceaccounts/token` by any role, built-in or custom, through a ClusterRoleBinding or a RoleBinding, giving the binding and its scope. Subjects bound to `cluster-admin`, `admin`, or `edit` count. PASS otherwise. |
| 4.2.1 | Automated | Minimize admission of privileged containers | K6, K7 | FAIL lists non-system pods with a privileged container. Otherwise PASS, noting whether Pod Security Admission `enforce` labels prevent new ones. |
| 4.2.2 | Automated | Minimize containers sharing the host PID namespace | K6 | FAIL lists non-system pods with `hostPID: true`. PASS otherwise. |
| 4.2.3 | Automated | Minimize containers sharing the host IPC namespace | K6 | FAIL lists non-system pods with `hostIPC: true`. PASS otherwise. |
| 4.2.4 | Automated | Minimize containers sharing the host network namespace | K6 | FAIL lists non-system pods with `hostNetwork: true`. PASS otherwise. |
| 4.2.5 | Automated | Minimize containers with allowPrivilegeEscalation | K6 | FAIL lists non-system containers that do not set `allowPrivilegeEscalation: false`. PASS otherwise. |
| 4.3.1 | Manual | CNI supports network policies | K10, AWS-E7 VPC CNI configuration | PASS if VPC CNI network policy is enabled (`enableNetworkPolicy: "true"` in the `vpc-cni` add-on configuration, or `--enable-network-policy=true` on the `aws-eks-nodeagent` container), or Calico or Cilium runs. The `aws-eks-nodeagent` container is present even when network policy is off, so its presence alone is not evidence. FAIL otherwise. |
| 4.3.2 | Automated | All namespaces have NetworkPolicies | K7, K8 | FAIL lists non-system namespaces with no NetworkPolicy. PASS otherwise. |
| 4.4.1 | Automated | Prefer secrets as files over environment variables | K6 | FAIL lists non-system containers using `env[].valueFrom.secretKeyRef` or `envFrom[].secretRef`. PASS otherwise. |
| 4.4.2 | Manual | Consider external secret storage | K12, K13 | PASS if External Secrets Operator, Secrets Store CSI Driver, or Sealed Secrets is in use. Otherwise `Manual review` asking whether an external store is used another way. |
| 4.5.1 | Manual | Namespaces as administrative boundaries | K7, K2 | `Manual review`: give the non-system namespace count and how many have their own RoleBindings, and ask whether tenants or teams are separated by namespace. |
| 4.5.2 | Automated | The default namespace should not be used | K11 | FAIL lists workloads in `default`. PASS if none. |

## Section 5 — Managed services

| ID | Type | Control | Evidence | Pass rule |
|---|---|---|---|---|
| 5.1.1 | Manual | Image vulnerability scanning | AWS-E5 Inspector coverage | PASS if Inspector ECR scanning covers the repositories the running images come from, or ECR enhanced scanning is on. `Manual review` if images come only from non-ECR registries, asking which scanner is used. FAIL if images are in ECR and no scanning is enabled. |
| 5.1.2 | Manual | Minimize user access to Amazon ECR | — | `Manual review`: say the check needs an IAM review of human principals with `ecr:*` write actions, which is outside this cluster review. |
| 5.1.3 | Manual | Cluster ECR access is read-only | AWS-E4 node role policies | PASS if node roles attach `AmazonEC2ContainerRegistryReadOnly` or `AmazonEC2ContainerRegistryPullOnly` and no policy granting ECR write actions. FAIL lists the write grant. |
| 5.1.4 | Manual | Minimize container registries to approved ones | K6 images | `Manual review`: list the distinct registries in use and ask which are approved. FAIL is never inferred. |
| 5.2.1 | Manual | Dedicated EKS service accounts | K5, K6, AWS-E1 Pod Identity associations | FAIL if non-system workloads that call AWS APIs rely on the node role (no IRSA annotation and no Pod Identity association) and the node role has non-default policies. Otherwise PASS, listing the IRSA and Pod Identity service accounts. |
| 5.3.1 | Manual | Secrets encrypted with AWS KMS keys | AWS-E1 `encryptionConfig` | PASS if `encryptionConfig` contains `secrets` with a KMS key ARN. FAIL otherwise. Note that EKS on Kubernetes 1.28 and later also applies default envelope encryption with an AWS owned key. |
| 5.4.1 | Manual | Restrict access to the control plane endpoint | AWS-E1 `resourcesVpcConfig` | PASS if `endpointPublicAccess=false`, or public access is on and `publicAccessCidrs` excludes `0.0.0.0/0`. FAIL if public access is open to `0.0.0.0/0`. |
| 5.4.2 | Manual | Private endpoint enabled, public access disabled | AWS-E1 `resourcesVpcConfig` | PASS only if `endpointPrivateAccess=true` and `endpointPublicAccess=false`. FAIL otherwise, even with restricted CIDRs. |
| 5.4.3 | Manual | Private nodes | AWS-E2 node group subnets | PASS if every node group subnet has `MapPublicIpOnLaunch=false` and no node has a public IP. FAIL lists subnets or nodes. |
| 5.4.4 | Manual | Network policy enabled and set as appropriate | 4.3.1 and 4.3.2 results | PASS if 4.3.1 and 4.3.2 both PASS. FAIL if 4.3.1 FAILs. `Manual review` if only 4.3.2 FAILs. |
| 5.4.5 | Manual | TLS on HTTPS load balancers | AWS-E8 load balancer listeners | FAIL lists internet-facing load balancers tagged for this cluster with an HTTP listener that does not redirect to HTTPS. PASS if all use HTTPS or TLS. `Not assessed` if no tagged load balancer is found. |
| 5.5.1 | Manual | Manage Kubernetes RBAC users with AWS IAM | AWS-E1 access entries, K9 | PASS if every human principal in the access entries and `aws-auth` is an IAM user or role, so people authenticate through IAM. Recommend IAM roles over IAM users (long-lived keys) as advice, not as a FAIL. `Manual review` if non-IAM authentication (an OIDC identity provider config or static service account tokens for people) is in use. |
