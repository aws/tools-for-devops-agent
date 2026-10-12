# Remediation playbooks

## Contents

- Remediation blocks, in order: R-ETCD-1 … R-ETCD-7 (7 blocks — one `###` heading per check ID; IDs appear in ascending order, with the manual `*M` blocks interleaved after their related numbered checks)

Every finding the skill emits comes with a remediation playbook from this file. Recommendations are anchored to AWS public guidance: [EKS Scalability — Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html), [EKS Scalability — Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html), [Compute and Autoscaling](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html), and [EKS Provisioned Control Plane](https://docs.aws.amazon.com/eks/latest/userguide/eks-provisioned-control-plane.html).

> **Decision rule for the agent.** Always prefer the **least disruptive** option that resolves the finding. Drop runaway / leaked objects before tuning APF. Tune APF before scaling the control plane. Scale the control plane (Provisioned mode) only when workload-side fixes are exhausted or when the cluster is genuinely large.

## Playbook index

| ID | Trigger | Headline action |
|----|---------|----------------|
| [R-ETCD-1](#r-etcd-1--jobs-and-pods-leaking) | etcd > 75%, top resource = `jobs` | Set `ttlSecondsAfterFinished` on Jobs/CronJobs |
| [R-ETCD-2](#r-etcd-2--replicasets-leaking-from-helm-rollouts) | etcd > 75%, top resource = `replicasets` | Lower `revisionHistoryLimit` on Deployments |
| [R-ETCD-3](#r-etcd-3--events-flooding) | etcd > 75%, top resource = `events` | Quiet noisy event sources / export to CW Logs |
| [R-ETCD-4](#r-etcd-4--secrets-and-configmaps-watch-load) | etcd > 75%, top resource = `secrets`/`configmaps` | Mark immutable, externalize, or disable mounting |
| [R-ETCD-5](#r-etcd-5--csrs-not-being-garbage-collected) | etcd > 75%, top resource = `csrs` | Enable CSR signer GC / clean up old CSRs |
| [R-ETCD-6](#r-etcd-6--leases-churn) | etcd > 75%, top resource = `leases` | Reduce duplicate controller replicas; check Karpenter / CAS |
| [R-ETCD-7](#r-etcd-7--general-bulk-cleanup-etcd--90-emergency) | etcd > 90% — emergency | Delete in batches, then defrag |
| [R-APF-1](remediations-apf.md#r-apf-1--workload-low-throttling) | 429s in `workload-low` only | No action — APF working as designed |
| [R-APF-2](remediations-apf.md#r-apf-2--system-or-leader-election-throttling) | 429s in `system` / `leader-election` | Identify caller, reduce load OR add a FlowSchema |
| [R-APF-3](remediations-apf.md#r-apf-3--single-caller-dominating) | One user agent > 30% of LIST volume | Use shared informers / drop kubectl-in-loop / cache |
| [R-API-1](remediations-apiserver.md#r-api-1--list-latency-slo-breach-avg--1-s) | LIST avg > 1 s | Find the offender via CP4, paginate / use field selectors |
| [R-API-2](remediations-apiserver.md#r-api-2--list-max--20-s) | LIST max > 20 s | Block the offending caller; investigate webhook timeouts |
| [R-API-3](remediations-apiserver.md#r-api-3--sustained-5xx) | 5xx > 0 over 5 min | Cross-check etcd quota and APF; engage AWS Support if not workload-side |
| [R-KCM-1](remediations-apiserver.md#r-kcm-1--controller-saturating-kubeapiqps) | Any controller > 18 QPS | Tune `revisionHistoryLimit`, namespace count, or shard the controller |
| [R-SCHED-1](remediations-apiserver.md#r-sched-1--unschedulable-pods) | Pods unschedulable > 10 min | Check node capacity, NodePool limits, taints |
| [R-EVICT-1](remediations-apiserver.md#r-evict-1--pods-failing-eviction) | Pod fails eviction > 30 min | Check PDBs, finalizers, terminationGracePeriod |
| [R-WORKLOAD-1](remediations-apiserver.md#r-workload-1--services-per-namespace) | > 500 services in one namespace | Split namespaces, switch to ingress |
| [R-WORKLOAD-2](remediations-apiserver.md#r-workload-2--watch-load-from-secrets) | High watch traffic on Secrets | Mark immutable; use external secrets |
| [R-WORKLOAD-3](remediations-apiserver.md#r-workload-3--daemonset-thundering-herd) | DaemonSet update p99 spikes | Set `minReadySeconds` and `maxSurge` |
| [R-WORKLOAD-4](remediations-apiserver.md#r-workload-4--enableservicelinks-defaults) | Many services, slow pod startup | Set `enableServiceLinks: false` |
| [R-WORKLOAD-5](remediations-apiserver.md#r-workload-5--admission-webhook-blast-radius) | Webhook timeout / failurePolicy issue | Scope the webhook; reduce timeout |
| [R-CP-1](remediations-apiserver.md#r-cp-1--escalate-to-provisioned-control-plane) | All workload-side fixes exhausted, sustained saturation | Move to Provisioned Control Plane tier |

---

## etcd remediations

### R-ETCD-1 — Jobs and Pods leaking

**Trigger:** etcd > 75% of 8 GB; CP10 shows `jobs` (or `pods` from completed Jobs) as top resource.

**Why:** A CronJob without `spec.ttlSecondsAfterFinished` keeps every Job and its Pods around forever. At any non-trivial schedule this is the single most common cause of etcd fill-up.

**Action — recommended (low risk):**

```yaml
# On every CronJob in the cluster
spec:
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      ttlSecondsAfterFinished: 3600   # 1 hour after completion
```

For one-off Jobs created by controllers (Argo Workflows, Tekton, etc.) make sure the controller's Job pruning is on.

**Action — bulk cleanup of existing leaked Jobs:**

```bash
# DRY-RUN first — count what would be deleted
kubectl get jobs --all-namespaces \
  --field-selector=status.successful=1 \
  -o json | jq '.items | length'

# Delete completed Jobs older than 7 days (validate the namespace list first)
kubectl get jobs --all-namespaces \
  --field-selector=status.successful=1 \
  -o json \
  | jq -r '.items[] | select(.status.completionTime < (now - 7*86400 | todate))
           | "\(.metadata.namespace) \(.metadata.name)"' \
  | while read ns name; do
      kubectl delete job -n "$ns" "$name"
    done
```

**Why this is safe:** Jobs are batch objects. Their Pods have already exited. Nothing in the cluster depends on them after the application has consumed the result.

> Per AWS guidance for [bulk Kubernetes deletes](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#api-priority-and-fairness), **delete in batches** (≤ 200 per minute) to avoid hitting APF rejections during the cleanup itself.

**Reference:** [Kubernetes — automatic cleanup for finished Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/), [scale-workloads.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html).

### R-ETCD-2 — ReplicaSets leaking from Helm rollouts

**Trigger:** CP10 shows `replicasets` as top resource.

**Why:** The Deployment controller default is `revisionHistoryLimit: 10`. Helm chart upgrades add a new ReplicaSet on every release; on busy CD pipelines you can have 200+ stale ReplicaSets per Deployment.

**Action — recommended:**

```yaml
spec:
  revisionHistoryLimit: 2   # default 10, EKS guidance is 2-3 for production
```

Reference: [EKS — Limit Deployment history](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html).

**Action — bulk cleanup:**

```bash
# Identify orphaned ReplicaSets (replicas=0, not the latest)
kubectl get rs --all-namespaces -o json \
  | jq -r '.items[] | select(.spec.replicas == 0)
           | "\(.metadata.namespace) \(.metadata.name)"' \
  | wc -l
# Delete in batches once the count is confirmed
```

### R-ETCD-3 — Events flooding

**Trigger:** CP10 shows `events` as top resource.

**Why:** Kubernetes events have a hard 60-minute TTL ([Managing Kubernetes control plane events](https://aws.amazon.com/blogs/containers/managing-kubernetes-control-plane-events-in-amazon-eks/)) so they don't accumulate in etcd indefinitely — but if a controller is *generating* events at a high rate (e.g. probe failure loops, OOM crash loops), the in-flight write volume saturates etcd anyway.

**Action — recommended:**

1. Identify the noisy source. The audit log shows the `userAgent` and the `objectRef.namespace` of the event's involved object. CP6 (top callers) almost always names the controller.
2. Common offenders and their fix:
   - Failing readiness probe → tune `initialDelaySeconds` / `periodSeconds`.
   - OOMKilled crash loop → raise memory request, or use VPA.
   - kubelet PLEG / runtime errors → check node disk and memory.
3. For long-term retention without etcd pressure, **export events to CloudWatch Logs** following the AWS guide ([Managing Kubernetes control plane events](https://aws.amazon.com/blogs/containers/managing-kubernetes-control-plane-events-in-amazon-eks/)).

### R-ETCD-4 — Secrets and ConfigMaps watch load

**Trigger:** CP10 shows `secrets` or `configmaps` as top resource OR the kubelet's watch volume on Secrets is high (visible in CP6 or APF).

**Why:** The kubelet watches every Secret used by a Pod on its node. Many Secrets × many nodes = high control-plane watch traffic. AWS specifically calls this out: ["the growing number of watches can negatively impact API server performance"](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html).

**Action — recommended (in priority order):**

1. **Mark Secrets and ConfigMaps `immutable`** for any that don't change at runtime. This stops the watch entirely.

   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: my-app-credentials
   immutable: true   # no more watches once set
   data: {...}
   ```

2. **Externalize secrets** to AWS Secrets Manager via the [Secrets Store CSI Driver + ASCP](https://docs.aws.amazon.com/secretsmanager/latest/userguide/integrating_csi_driver.html) or [External Secrets Operator](https://external-secrets.io). Removes Secrets from etcd entirely.

3. **Disable token automounting** for ServiceAccounts whose pods don't talk to the API server:

   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: my-app
   automountServiceAccountToken: false
   ```

### R-ETCD-5 — CSRs not being garbage-collected

**Trigger:** CP10 shows `certificatesigningrequests` as top resource.

**Why:** Kubelet rotates serving and client certs. If the CSR signer GC isn't keeping up, completed CSRs accumulate. There have been real production incidents where leaked CSRs filled etcd past 3 GB.

**Action:**

1. Check signer health:
   ```bash
   kubectl get csr --no-headers | wc -l
   kubectl get csr -o json \
     | jq -r '.items[] | select(.status.certificate != null)
              | "\(.metadata.creationTimestamp) \(.metadata.name)"' \
     | sort | head
   ```
2. Bulk-delete approved-and-issued CSRs older than 24 hours:
   ```bash
   kubectl get csr -o json \
     | jq -r '.items[] | select(.status.certificate != null
              and (.metadata.creationTimestamp | fromdateiso8601) < (now - 86400))
              | .metadata.name' \
     | xargs -n 50 kubectl delete csr
   ```

### R-ETCD-6 — Leases churn

**Trigger:** CP10 shows `leases` as top resource.

**Why:** Every controller that does leader election (KCM, kube-scheduler, Karpenter, Cluster Autoscaler, cloud controller, plus many add-ons) writes a Lease on every renewal — by default every 10 seconds.

**Action:**

1. Audit the controller list. CP6 / `cp_top_callers` will show which `system:serviceaccount:*` is writing leases. Common culprits when the count is unusually high: multiple Karpenter replicas with the same lease key, duplicate CAS instances, or an add-on with an unreasonably short lease renewal interval.
2. Reduce duplicates. One CAS for the cluster (or shard them per [scale-control-plane.md — Shard Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#shard-cluster-autoscaler)). One Karpenter, one set of metrics-server replicas.
3. For a controller you own, raise `--leader-elect-lease-duration` (default 15 s) so renewals are less frequent. Validate the failover SLA you accept.

### R-ETCD-7 — General bulk cleanup (etcd > 90%, emergency)

**Trigger:** etcd > 90% of 8 GB, customer needs to free space *now*.

> **High-impact action — confirm with the user before proceeding.** Destructive operations in production need explicit user confirmation.

1. Identify what to delete (use CP10 + your application knowledge):
   - Completed Jobs older than 24 hours.
   - ReplicaSets with `replicas=0` not owned by the latest Deployment.
   - Events older than 1 hour (already auto-expired by Kubernetes).
   - Old CSRs.
2. Delete in batches of 100–200 to avoid causing APF throttling during cleanup.
3. After cleanup, etcd reclaims space on the next compaction + defragmentation cycle. The customer-visible metric `apiserver_storage_db_total_size_in_bytes` decreases on a defrag, not a delete.
4. If the cluster has crossed the upstream 8 GB threshold and is in read-only mode, escalate via AWS Support — only the service team can disarm the etcd alarm. Do **not** advise the customer to attempt etcd recovery themselves.

> **Pro tip:** `apiserver_storage_db_total_size_in_use_in_bytes` is the post-compaction size. The gap between it and the on-disk metric is the defrag headroom. If the gap is small but on-disk is high, you have a real fill problem (not a defrag-pending problem).

---

