# API server, controller-manager, scheduler & control-plane-scaling remediations

## Contents

- Remediation blocks, in order: R-API-1 … R-CP-1 (12 blocks — one `###` heading per check ID; IDs appear in ascending order, with the manual `*M` blocks interleaved after their related numbered checks)

Playbooks for API server LIST latency / 5xx (R-API-*), kube-controller-manager (R-KCM-*), scheduler (R-SCHED-*), eviction (R-EVICT-*), workload-level control-plane load (R-WORKLOAD-*), and Provisioned Control Plane escalation (R-CP-*), plus the output format and guardrails. Symptom→playbook index and the least-disruptive decision rule are in [`remediations-etcd.md`](remediations-etcd.md).

### R-API-1 — LIST latency SLO breach (avg > 1 s)

**Trigger:** CP2 shows any URI with avg > 1 s.

**Why:** [Kubernetes scalability SLO](https://github.com/kubernetes/community/blob/master/sig-scalability/slos/slos.md#steady-state-slisslos) target. Sustained breach means either etcd is slow (cross-check with `cp_etcd_pressure`) or the LIST is doing too much work.

**Action:**

1. Run CP4 — find the user agent driving the slow LIST.
2. If the LIST is unscoped (no namespace, no field selector), recommend pagination + scoping.
3. If etcd commit p99 > 200 ms, the bottleneck is etcd — see etcd remediations.

### R-API-2 — LIST max > 20 s

**Trigger:** CP3 shows any URI with max > 20 s.

**Action:**

1. This is an acute event, not steady state. Find the offending request via CP15 raw data.
2. Common causes: an admission webhook timing out (check webhook timeouts in the cluster — recommend `timeoutSeconds < 10`), an enormous unscoped LIST, or etcd in defrag.
3. If the cluster is genuinely too small, escalate to Provisioned mode.

### R-API-3 — Sustained 5xx

**Trigger:** Any sustained 5xx (CP8) over a 5-minute window.

**Action:**

1. Cross-check `cp_etcd_pressure` — 5xx on writes is often etcd quota or apply latency.
2. Cross-check `cp_apf_health` — 5xx can be downstream of APF saturation.
3. If neither, this is an EKS service-side issue — escalate to **AWS Support**. Standard SLA for managed control plane is 99.95% (99.99% on Provisioned mode) — see [EKS SLA](https://aws.amazon.com/eks/sla/).

---

## kube-controller-manager remediations

### R-KCM-1 — Controller saturating `kubeAPIQPS`

**Trigger:** Any controller sustained > 18 QPS (90% of default `kubeAPIQPS=20`).

**Why:** The controller is being client-side throttled. It's not breaking, but reconciles are slow and the controller is falling behind on its workqueue.

**Action — pick by which controller:**

| Controller | Cause | Fix |
|-----------|-------|-----|
| `replicaset-controller` | Helm `revisionHistoryLimit` too high | [R-ETCD-2](remediations-etcd.md#r-etcd-2--replicasets-leaking-from-helm-rollouts) |
| `endpointslice-controller` / `endpoint-controller` | Service churn (rolling deploys, NLB target updates) | Use EndpointSlices everywhere ([scale-workloads.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)); raise `concurrentEndpointSyncs` if self-managed |
| `serviceaccount-token-controller` | Many short-lived pods auto-mounting tokens | Set `automountServiceAccountToken: false` on SAs that don't need it |
| `garbage-collector` | Owner-ref churn at scale | Investigate the parent objects driving the deletes |
| Cluster Autoscaler | Cluster > 1000 nodes | **Shard CAS** per [scale-control-plane.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#shard-cluster-autoscaler) — multiple CAS instances each scoped to a subset of node groups |

For a self-managed controller you can tune the kubeadm-style ClusterConfiguration to raise `kubeAPIQPS` / `kubeAPIBurst` — but raising QPS pushes the load to etcd, which often makes the underlying problem worse. Fix the source instead.

---

## Scheduler remediations

### R-SCHED-1 — Unschedulable pods

**Trigger:** CP18 shows pods unschedulable for > 10 min.

**Action — by failure reason:**

| Reason | Likely cause | Fix |
|--------|-------------|-----|
| `Insufficient cpu` / `memory` | Cluster Autoscaler / Karpenter not scaling | Check NodePool / NodeGroup `limits`; check instance availability for the requested type |
| `node(s) had taint X that the pod didn't tolerate` | Workload missing toleration | Add tolerations or remove the taint |
| `node(s) didn't match Pod's node affinity` | Misconfigured affinity | Audit affinity expressions |
| `pod has unbound immediate PersistentVolumeClaims` | PVC bound in wrong AZ | Use `WaitForFirstConsumer` storage class binding mode |

### R-EVICT-1 — Pods failing eviction

**Trigger:** CP17 shows the same pod failing eviction for > 30 min.

**Action:**

1. Check for a too-strict PDB:
   ```bash
   kubectl get pdb -A -o json \
     | jq '.items[] | select(.spec.minAvailable=="100%" or
                            .spec.maxUnavailable==0)
              | {ns: .metadata.namespace, name: .metadata.name}'
   ```
   PDBs that allow zero disruption block evictions forever. Recommend `maxUnavailable: 1` instead.
2. Check for stuck finalizers:
   ```bash
   kubectl get pod <name> -n <ns> -o jsonpath='{.metadata.finalizers}'
   ```
   A finalizer that the responsible controller has stopped reconciling will block deletion. Identify the controller and either restart it or (last resort, with user approval) patch the finalizers off.
3. Confirm `terminationGracePeriodSeconds` is reasonable (not 0, not 3600).

---

## Workload-level remediations

### R-WORKLOAD-1 — Services per namespace

**Trigger:** Any namespace has > 500 services.

**Why:** AWS recommends ≤ 500 services per namespace. The hard cluster limit is 10,000 and the hard namespace limit is 5,000 ([scale-workloads.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)). kube-proxy generates iptables rules per service per node — at 500+ services, packet routing latency becomes noticeable.

**Action:**

1. Split the namespace by application or team.
2. For "service per microservice" patterns, consider an ingress controller — one ALB / NLB plus an in-cluster reverse proxy can serve thousands of routes from one service.

### R-WORKLOAD-2 — Watch load from Secrets

**Trigger:** High volume of Secret watches in CP6, or kubelet-driven watch traffic dominates.

See [R-ETCD-4](remediations-etcd.md#r-etcd-4--secrets-and-configmaps-watch-load) — same fix.

### R-WORKLOAD-3 — DaemonSet thundering herd

**Trigger:** API server p99 spikes correlate with DaemonSet rollouts (visible in CP15).

**Why:** From [scale-control-plane.md — Prevent DaemonSet thundering herds](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#prevent-daemonset-thundering-herds): when many DS pods start simultaneously they all hit the API server at once.

**Action:**

```yaml
# On the DaemonSet
spec:
  minReadySeconds: 60     # space the rollout
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 0
      maxUnavailable: 10%   # or absolute number for huge clusters
```

### R-WORKLOAD-4 — `enableServiceLinks` defaults

**Trigger:** Pod startup is slow and the cluster has many services.

**Why:** Kubernetes injects an env var per service into every container by default. With 1000 services, every new pod gets 1000 env vars and a slower startup.

**Action:**

```yaml
spec:
  enableServiceLinks: false
```

Recommend setting this on every workload that doesn't depend on legacy service env vars ([scale-workloads.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)).

### R-WORKLOAD-5 — Admission webhook blast radius

**Trigger:** CP14 shows webhook latency dominating, or CP12 health-check failures correlate with webhook activity.

**Why:** A misconfigured admission webhook can block every API request. `failurePolicy: Fail` scoped over `apiGroups: ["*"]` and `resources: ["*"]` will hard-fail every API call when the webhook backend is down.

**Action — in priority order:**

1. **Scope the webhook.** Limit `rules` to the specific resources and verbs that need it.
2. **Reduce timeout.** `timeoutSeconds: 5` is a sane default; never above 10.
3. **Set `failurePolicy: Ignore`** for non-critical webhooks (audit, observability, mutation that's not security-critical).
4. **Exclude system namespaces.** Webhooks with `failurePolicy: Fail` should not match `kube-system` or `kube-public` — that path leads to control-plane lockups during webhook outages.

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: my-webhook
webhooks:
- name: my-webhook.example.com
  failurePolicy: Ignore       # safer default unless this is security-critical
  timeoutSeconds: 5
  namespaceSelector:
    matchExpressions:
    - key: kubernetes.io/metadata.name
      operator: NotIn
      values: [kube-system, kube-public, kube-node-lease]
  rules:
  - apiGroups: ["apps"]        # scoped, NOT ["*"]
    apiVersions: ["v1"]
    operations: ["CREATE", "UPDATE"]
    resources: ["deployments"]
```

---

## Control-plane scaling escalation

### R-CP-1 — Escalate to Provisioned Control Plane

**Trigger:** Workload-side fixes have been applied and the control plane is still saturated.

**Why:** [EKS Provisioned Control Plane](https://docs.aws.amazon.com/eks/latest/userguide/eks-provisioned-control-plane.html) lets you pre-allocate control plane capacity in tiers (XL, 2XL, 4XL, 8XL) with a 99.99% SLA measured in 1-minute intervals. Use it when:

- The cluster is genuinely large (> 1000 nodes, > 50000 pods).
- Workload patterns are spiky (AI/ML training, batch processing, e-commerce events) and standard auto-scaling can't react fast enough.
- The customer needs identical control-plane performance across staging and production.

**Action:**

1. **Confirm workload-side options are exhausted first.** Provisioned mode adds cost — make sure the customer has lowered `revisionHistoryLimit`, externalized Secrets, set TTLs on Jobs, and isn't being throttled because of a leaked controller.
2. Recommend a tier based on current API request concurrency and node count. The agent should fetch the customer's current usage from `apiserver_request_total` and present it next to the [tier capacity tables](https://docs.aws.amazon.com/eks/latest/userguide/eks-provisioned-control-plane.html#control-plane-scaling-tiers).
3. **Tier change is non-disruptive but takes minutes.** Schedule for a maintenance window if the customer is sensitive.
4. **Reversible.** The customer can switch back to standard mode at any time.

> **The agent should not initiate this change.** It is a billing and architecture decision. Draft the recommendation with the cost and tier rationale; the customer (or their account team) approves.

---

## Output format — how the agent surfaces remediations

Every finding the skill emits is paired with:

1. **The playbook ID** (e.g. `R-ETCD-1`) so the customer can read the full context.
2. **A one-line headline action** (the most important step).
3. **At most 3 concrete next steps** — code snippet or kubectl command, with safe defaults.
4. **A reference link** to the AWS doc that backs the recommendation.
5. **A confidence note** if the cause is ambiguous ("CP10 shows `jobs` dominating, but we cannot confirm a CronJob is the source — verify with `kubectl get cronjobs --all-namespaces -o wide`").

Example output (drawn from `cp_etcd_pressure`):

```json
{
  "tier": "high",
  "customer_facing_label": "Action required — control plane saturation risk",
  "observation": "etcd at 78% of 8 GB quota; 7-day growth +9.1%. 'jobs' resource = 49% of writes in last 60 min.",
  "remediation": {
    "playbook_id": "R-ETCD-1",
    "headline": "Set spec.ttlSecondsAfterFinished on CronJobs",
    "next_steps": [
      "Audit CronJobs cluster-wide: `kubectl get cronjobs -A -o json | jq '.items[].spec | select(has(\"jobTemplate\") and (.jobTemplate.spec.ttlSecondsAfterFinished == null))'`",
      "Patch CronJobs to add `ttlSecondsAfterFinished: 3600` and `successfulJobsHistoryLimit: 3`.",
      "Bulk-delete completed Jobs older than 7 days, in batches of 200."
    ],
    "references": [
      "https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/",
      "https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html"
    ],
    "confidence": "high",
    "estimated_recovery": "etcd size decreases on next defrag (within 24 h)."
  }
}
```

---

## What the agent should NOT do

The agent operates read-only and applies these safety guidance points:

- **Never delete production resources without explicit customer approval.** Bulk deletes always require user confirmation, even if the resource is "obviously" leaked.
- **Never disable safety protections** (PDBs, finalizers, admission webhooks marked security-critical, MFA delete, deletion protection) without explicit user confirmation.
- **Never raise `kubeAPIQPS` as a first response.** Raising QPS pushes load to etcd. The right answer is almost always to reduce demand, not raise the ceiling.
- **Never modify the control plane configuration directly.** EKS does not let you. The right path for control-plane sizing is Provisioned mode, which is a separate AWS API call.
- **Never echo Secret values.** Reference Secrets by name only when summarizing findings.
