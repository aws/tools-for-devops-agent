# Security Pods Rbac remediations — shard 02

Canonical IDs: `S9,S10,S11,S12,S13,S14,S15`

### S9 — Pod Security Admission configured
**Why it matters:** Without PSA labels (or a policy engine), nothing stops a workload from running privileged/root/host-namespace — the hardening checks above aren't enforced, only hoped for.
**Steps:** Label workload namespaces with PSA `enforce`/`warn`/`audit` at `baseline` or `restricted`; or run Kyverno/Gatekeeper with equivalent policies.
**Snippet:**
```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: restricted
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)
- [Kubernetes — Enforce Pod Security Standards with Namespace Labels](https://kubernetes.io/docs/tasks/configure-pod-container/enforce-standards-namespace-labels/)

### S10 — No cluster-admin to non-system principals
**Why it matters:** A ClusterRoleBinding to `cluster-admin` for a human user, broad group, or workload SA is full cluster compromise if that identity is phished or leaked.
**Steps:**
1. Find them: `kubectl get clusterrolebindings -o json | jq -r '.items[] | select(.roleRef.name=="cluster-admin") | "\(.metadata.name): \(.subjects)"'`
2. Replace with least-privilege roles (`view`/`edit` or custom Roles scoped to namespaces). Keep cluster-admin only for break-glass, ideally via EKS Access Entries.
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [Kubernetes — Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

### S11 — No wildcard RBAC
**Why it matters:** A ClusterRole with `verbs: ["*"]`, `resources: ["*"]`, or `apiGroups: ["*"]` is cluster-admin by another name and bypasses the intent of RBAC.
**Steps:** Replace wildcards with explicit verbs/resources the workload actually uses; audit with `kubectl get clusterroles -o json | jq` filtering for `"*"` (exclude built-in `admin`/`cluster-admin`/`edit`/`system:` roles).
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)

### S12 — Access Entries / API auth mode *(AWS-API)*
**Why it matters:** The `aws-auth` ConfigMap is deprecated and error-prone; the Cluster Access Management API with Access Entries is the current, auditable standard.
**How to verify / fix:** `aws eks describe-cluster --name ${CLUSTER} --query cluster.accessConfig.authenticationMode` (target `API`); migrate principals to Access Entries.
**References:**
- [EKS Best Practices — Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html)

### S13 — IRSA / Pod Identity for workloads
**Why it matters:** Workloads using the node IAM role inherit the node's broad permissions. Per-workload identity (EKS Pod Identity, preferred; or IRSA) scopes AWS access to exactly what the pod needs.
**Steps:**
1. Identify workloads making AWS calls via the node role (no SA annotation / Pod Identity association).
2. Prefer **EKS Pod Identity** (no OIDC config, supports session tags/ABAC; pre-deployed on Auto Mode); use IRSA where Pod Identity isn't an option.
**Snippet (IRSA-annotated ServiceAccount):**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${APP}-sa
  namespace: ${NAMESPACE}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}
```
**References:**
- [EKS Best Practices — Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html)
- [EKS User Guide — EKS Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)

### S14 — automountServiceAccountToken disabled where unused
**Why it matters:** A mounted SA token a workload doesn't use is a free credential for an attacker who compromises the pod — it can call the Kubernetes API as that SA.
**Steps:** Set `automountServiceAccountToken: false` on the SA or pod for workloads that don't call the API; leave on only where in-cluster API access is needed.
**Snippet:**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata: { name: ${APP}-sa, namespace: ${NAMESPACE} }
automountServiceAccountToken: false
```
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)

### S15 — NetworkPolicy default-deny coverage
**Why it matters:** By default all pod-to-pod traffic is allowed (flat east/west). A compromised pod can reach everything. VPC CNI Network Policy is **not enabled by default** — the baseline is default-deny per namespace plus an explicit DNS allow.
**Steps:**
1. Enable Network Policy on the VPC CNI addon (`ENABLE_NETWORK_POLICY=true`) or use a policy-capable CNI.
2. Apply a default-deny (ingress+egress) per workload namespace, then a DNS-allow, then incrementally allow required flows.
**Snippet (default-deny + DNS allow):**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: default-deny, namespace: ${NAMESPACE} }
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: allow-dns, namespace: ${NAMESPACE} }
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } }
          podSelector: { matchLabels: { k8s-app: kube-dns } }
      ports: [{ protocol: UDP, port: 53 }, { protocol: TCP, port: 53 }]
```
**References:**
- [EKS Best Practices — Network Security](https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html)
- [EKS User Guide — Configure your cluster for Kubernetes network policies](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html)

