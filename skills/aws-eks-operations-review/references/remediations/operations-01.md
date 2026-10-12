# Operations remediations — shard 01
Canonical IDs: `Op1,Op2,Op3,Op4,Op5,Op6,Op7,Op8,Op9,Op10,Op11,Op12,Op13,Op14,Op15,Op16`

### Op1 — Kubernetes version currency
**Why it matters:** Versions in extended support cost more and stop getting features; at end-of-life EKS auto-upgrades you, risking unplanned disruption. Each minor gets 14 months standard + 12 months extended support.
**Steps:**
1. Check current vs supported: `kubectl version` and the EKS release calendar.
2. Plan sequential single-minor in-place upgrades (run the upgrade-readiness checklist first). Adopt a regular cadence (at least annually).
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [EKS User Guide — Kubernetes version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)

### Op2 — Node version consistency
**Why it matters:** Nodes lagging the control plane (or each other) widen version skew, risk unsupported kubelet/API-server combinations, and signal a stalled rollout that will compound at the next upgrade.
**Steps:**
1. List kubelet versions: `kubectl get nodes -o custom-columns=NAME:.metadata.name,KUBELET:.status.nodeInfo.kubeletVersion`
2. Finish the stalled node rollout (cycle MNG/Karpenter nodes) so all nodes are one kubelet minor and within 1 of the control plane.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [Kubernetes — Version skew policy](https://kubernetes.io/releases/version-skew-policy/)

### Op3 — Core addon presence (CNI/CoreDNS/kube-proxy/CSI)
**Why it matters:** These are the cluster's data-path foundation. A missing or unhealthy core addon degrades networking, DNS, or storage cluster-wide.
**Steps:**
1. Check kube-system: `kubectl get ds,deploy -n kube-system` — confirm `aws-node`, `kube-proxy`, `coredns`, and the EBS/EFS CSI driver are present and Ready.
2. Install/repair any missing managed addon (prefer EKS managed addons over self-managed manifests).
**References:**
- [EKS User Guide — Amazon EKS add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)

### Op4 — Managed vs self-managed nodes
**Why it matters:** Self-managed nodes put AMI patching, version upgrades, and lifecycle on you. Managed node groups / Karpenter / Auto Mode automate that and reduce upgrade risk.
**Steps:**
1. Inspect node labels for `eks.amazonaws.com/nodegroup` (MNG) or Karpenter ownership.
2. Migrate unmanaged self-managed nodes to MNG or Karpenter for automated AMI lifecycle.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [EKS User Guide — Managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)

### Op5 — Resource governance tags / labels
**Why it matters:** Namespaces without team/owner/env labels break cost allocation, ownership routing, and policy targeting.
**Steps:** Apply organizational labels (`team`, `env`, `cost-center`) to workload namespaces; enforce with a policy engine so new namespaces inherit the standard.
**Snippet:**
```yaml
metadata:
  labels: { team: payments, env: prod, cost-center: "1234" }
```
**References:**
- [EKS Best Practices — Cost Optimization: Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html)

### Op6 — IaC / GitOps management
**Why it matters:** Click-ops / imperative changes drift from source control, are hard to audit, and can't be reliably reproduced or rolled back.
**Steps:** Manage cluster state declaratively — ArgoCD or Flux for in-cluster manifests, Terraform/CloudFormation/CDK for the AWS-side cluster + nodegroups.
**References:**
- [EKS Best Practices — Cluster Upgrades (IaC)](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### Op7 — Addon versions current *(AWS-API)*
**Why it matters:** EKS does not auto-update addons. A CNI/CoreDNS/kube-proxy/CSI version far behind the cluster minor can break at upgrade time or miss security fixes.
**How to verify / fix:** `aws eks describe-addon --cluster-name ${CLUSTER} --addon-name vpc-cni` (repeat per addon); compare to `aws eks describe-addon-versions`. Bump addons as part of each upgrade.
**References:**
- [EKS User Guide — Updating an add-on](https://docs.aws.amazon.com/eks/latest/userguide/updating-an-add-on.html)

### Op8 — Node Monitoring Agent present
**Why it matters:** The EKS Node Monitoring Agent surfaces node-level health (kernel, networking, storage) as NodeConditions and is the **prerequisite** for Node Auto Repair (Op26). Without it, node faults go undetected. It is configured independently from auto-repair.
**Steps:** Enable the `eks-node-monitoring-agent` EKS add-on. Node Auto Repair is a separate setting — see **Op26**.
**References:**
- [EKS User Guide — Node health and auto repair](https://docs.aws.amazon.com/eks/latest/userguide/node-health.html)

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
