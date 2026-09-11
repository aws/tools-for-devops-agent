# Security Network Nodes remediations — shard 01

Canonical IDs: `S16,S17,S18,S19,S20,S21,S22,S23`

### S16 — No webhook catch-all rules
**Why it matters:** An admission webhook matching `apiGroups:["*"]` AND `resources:["*"]` intercepts every API call — a single point of failure and a latency tax on all operations.
**Steps:** Scope webhook `rules` to the specific apiGroups/resources/operations the webhook actually needs.
**References:**
- [Kubernetes — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)

### S17 — Webhook failurePolicy on system namespaces
**Why it matters:** A webhook with `failurePolicy: Fail` that also intercepts kube-system can block control-plane operations if the webhook backend is down — a cluster-wide outage risk.
**Steps:** Exempt kube-system/kube-public via `namespaceSelector`, or set `failurePolicy: Ignore` for non-critical webhooks.
**Snippet:**
```yaml
namespaceSelector:
  matchExpressions:
    - { key: kubernetes.io/metadata.name, operator: NotIn, values: [kube-system, kube-public] }
```
**References:**
- [Kubernetes — Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)

### S18 — External secrets management
**Why it matters:** Raw Kubernetes Secrets are base64 (not encrypted) and live in etcd; sprawl of sensitive data in Secrets widens the blast radius of an etcd or RBAC compromise.
**Steps:** Use External Secrets Operator or the Secrets Store CSI Driver to source secrets from AWS Secrets Manager / Parameter Store at runtime; pair with KMS envelope encryption (SM1).
**References:**
- [EKS Best Practices — Data encryption and secrets management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html)

### S19 — Secrets via volume not env
**Why it matters:** Secrets injected as env vars leak through crash dumps, `/proc`, logging, and `kubectl describe` more readily than mounted files.
**Steps:** Mount secrets as files (volume) instead of `env`/`envFrom`; the app reads from the mounted path.
**References:**
- [EKS Best Practices — Data encryption and secrets management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html)

### S20 — Image pull policy / no :latest
**Why it matters:** `:latest` (or untagged) images are non-deterministic — two pods can run different code, and rollbacks are impossible. It also defeats image provenance.
**Steps:** Pin explicit, immutable tags (or digests); set ECR repositories to `IMMUTABLE`; set `imagePullPolicy: IfNotPresent` with pinned tags.
**Snippet:**
```yaml
containers:
  - name: ${APP}
    image: ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:1.4.2
    imagePullPolicy: IfNotPresent
```
**References:**
- [EKS Best Practices — Image Security](https://docs.aws.amazon.com/eks/latest/best-practices/image-security.html)

### S21 — Image scanning present
**Why it matters:** Unscanned images ship known CVEs into the cluster. Continuous scanning catches them before and after deploy.
**Steps:** Enable Amazon ECR enhanced scanning (Inspector) on repositories, or run Trivy/Grype in CI and in-cluster.
**References:**
- [EKS Best Practices — Image Security](https://docs.aws.amazon.com/eks/latest/best-practices/image-security.html)
- [Amazon ECR — Image scanning](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-scanning.html)

### S22 — GuardDuty EKS protection
**Why it matters:** GuardDuty EKS Protection (audit-log + runtime monitoring) detects threats like crypto-mining, privilege escalation, and suspicious API calls that static checks miss.
**Steps:** Enable GuardDuty EKS Audit Log Monitoring and EKS Runtime Monitoring (agent auto-managed) for the account.
**References:**
- [EKS Best Practices — Runtime Security](https://docs.aws.amazon.com/eks/latest/best-practices/runtime-security.html)
- [GuardDuty — EKS Protection](https://docs.aws.amazon.com/guardduty/latest/ug/kubernetes-protection.html)

### S23 — Policy enforcement engine
**Why it matters:** Pod Security Admission enforces only the built-in PSS levels. A policy engine (Kyverno, Gatekeeper/OPA) enforces org-specific rules at admission — required registries, no `:latest`, mandatory labels, blocked capabilities — and rejects non-compliant workloads before they run, instead of detecting them after.
**Steps:**
1. Detect: `kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations -o name | grep -Ei 'kyverno|gatekeeper|opa'` and check for the controller Deployment.
2. If absent and PSA alone doesn't meet policy needs, deploy Kyverno or Gatekeeper and start in `audit`/`Warn` mode before enforcing.
**Snippet:**
```yaml
# Kyverno ClusterPolicy — block :latest as an example
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: { name: disallow-latest-tag }
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-image-tag
      match: { any: [{ resources: { kinds: [Pod] } }] }
      validate:
        message: "Using a mutable image tag is not allowed."
        pattern: { spec: { containers: [{ image: "!*:latest" }] } }
```
**N/A** if PSA `restricted` alone satisfies the requirement.
**References:**
- [EKS Best Practices — Pod Security (Policy as Code)](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)
- [Kyverno](https://kyverno.io/docs/) · [Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)

