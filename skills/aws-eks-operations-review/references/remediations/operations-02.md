# Operations remediations — shard 02

Canonical IDs: `Op9,Op10,Op11,Op12,Op13,Op14,Op15,Op16`

### Op9 — Cluster Autoscaler version matches cluster
**Why it matters:** Cluster Autoscaler is version-coupled to Kubernetes — a CAS minor that doesn't match the cluster minor is unsupported and can misbehave during scaling.
**Steps:** Pin the CAS image tag to the cluster's minor (e.g. cluster 1.30 → CAS `v1.30.x`); bump CAS as part of every cluster upgrade.
**References:**
- [EKS Best Practices — Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html)

### Op10 — Karpenter NodePool limits set
**Why it matters:** A NodePool with no `spec.limits` can scale compute without bound — a runaway workload or misconfig can launch huge amounts of capacity (cost + blast radius).
**Steps:** Set `cpu` and `memory` limits on every NodePool sized to the workload's realistic ceiling.
**Snippet:**
```yaml
spec:
  limits:
    cpu: "1000"
    memory: 1000Gi
```
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)
- [Karpenter — NodePools](https://karpenter.sh/docs/concepts/nodepools/)

### Op11 — Karpenter AMI pinned (no @latest in prod)
**Why it matters:** An `amiSelectorTerms` alias of `@latest` deploys whatever AMI Karpenter resolves at provision time — an untested AMI can roll into production and break workloads.
**Steps:**
1. Find it: `kubectl get ec2nodeclasses -o json | jq -r '.items[] | select(.spec.amiSelectorTerms[]?.alias|test("@latest$")) | .metadata.name'`
2. Pin a tested AMI alias version (test newer AMIs in non-prod first).
**Snippet:**
```yaml
spec:
  amiSelectorTerms:
    - alias: al2023@v20240807   # pin a tested version, not @latest
```
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)
- [Karpenter — Managing AMIs](https://karpenter.sh/docs/tasks/managing-amis/)

### Op12 — Karpenter consolidation policy
**Why it matters:** Without a consolidation policy, Karpenter never reclaims underutilized nodes → idle spend and poor bin-packing.
**Steps:** Set `consolidationPolicy` (`WhenEmptyOrUnderutilized` for most; `WhenEmpty` for conservative). Tune `consolidateAfter`.
**Snippet:**
```yaml
spec:
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
```
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op13 — Karpenter node expiry
**Why it matters:** Without `expireAfter`, nodes live indefinitely and drift from patched AMIs — a security and consistency gap.
**Steps:** Set `expireAfter` (not `Never`) so nodes are recycled onto current AMIs automatically. Pair with PDBs so expiry is non-disruptive.
**Snippet:**
```yaml
spec:
  disruption:
    expireAfter: 720h   # 30 days
```
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op14 — CronJob schedule coverage
**Why it matters:** A CronJob with a wrong/empty schedule silently never runs (or runs at the wrong time), and missing `concurrencyPolicy`/history limits pile up Jobs.
**Steps:** Verify each CronJob's `schedule` cron expression; set `concurrencyPolicy`, `startingDeadlineSeconds`, and history limits.
**Snippet:**
```yaml
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```
**References:**
- [Kubernetes — CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)

### Op15 — All pods Running (no problem pods)
**Why it matters:** Pending / Failed / CrashLoopBackOff / ImagePull / OOMKilled pods are live operational faults — degraded capacity, failing deploys, or memory misconfig.
**Steps:**
1. Triage: `kubectl get pods -A | grep -Ev 'Running|Completed'` and `kubectl describe pod` / `kubectl logs --previous` for the offenders.
2. Fix by class — CrashLoop (config/app), ImagePull (registry/auth/tag), OOMKilled (raise memory limit or right-size), Pending (capacity/affinity/quota).
**References:**
- [EKS Best Practices — Running highly-available applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)

### Op16 — Workload service-account hygiene
**Why it matters:** Workloads on the `default` SA can't be granted least-privilege IAM (IRSA/Pod Identity) cleanly and share an identity, breaking auditability.
**Steps:** Create a dedicated ServiceAccount per workload and reference it in the pod spec; disable token automount where the workload doesn't call the Kubernetes API.
**Snippet:**
```yaml
spec:
  serviceAccountName: ${APP}-sa
  automountServiceAccountToken: false   # if no in-cluster API access needed
```
**References:**
- [EKS Best Practices — Identity and Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)

