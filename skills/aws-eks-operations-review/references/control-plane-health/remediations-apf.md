# API Priority & Fairness (APF) remediations

Control-plane APF throttling playbooks (R-APF-*). Symptom→playbook index and the least-disruptive decision rule are in [`remediations-etcd.md`](remediations-etcd.md).

### R-APF-1 — `workload-low` throttling

**Trigger:** 429s appear only in priority `workload-low`.

**Action:** **No action required.** This is APF working as designed — it is rejecting low-priority traffic to protect higher-priority traffic. Surface as informational so the operator knows; do not page anyone.

### R-APF-2 — `system` or `leader-election` throttling

**Trigger:** 429s in `system` or `leader-election` priority.

**Why:** This is *unhealthy* throttling. Operators / leader-election clients are starving and the cluster is becoming unstable.

**Action — in priority order:**

1. **Find the source of the load.** Run `cp_top_callers` and `cp_kcm_qps`. If a single user agent or controller is dominant, fix that first ([R-APF-3](#r-apf-3--single-caller-dominating)).
2. **Tune APF.** From [scale-control-plane.md — APF settings](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#preventing-dropped-requests):
   - Total APF concurrency on EKS is 600 by default and scales up to ~2000.
   - Adding extra FlowSchemas is fine; over-creating PriorityLevelConfigurations dilutes shares (default = 600 shares).
   - Take shares from underutilized buckets, give them to saturated ones.

   Example FlowSchema scoping a noisy SA into its own bucket:

   ```yaml
   apiVersion: flowcontrol.apiserver.k8s.io/v1
   kind: FlowSchema
   metadata:
     name: noisy-controller
   spec:
     matchingPrecedence: 1000   # valid 1–10000; lower = matched first. 1000 is a mid-range default that leaves room to slot schemas above or below it.
     priorityLevelConfiguration:
       name: workload-high
     rules:
     - subjects:
       - kind: ServiceAccount
         serviceAccount:
           namespace: kube-system
           name: noisy-controller
       resourceRules:
       - verbs: ["list", "get", "watch"]
         apiGroups: ["*"]
         resources: ["*"]
         clusterScope: true
   ```

3. **Escalate to Provisioned Control Plane** if the load is genuinely larger than the standard tier supports — see [R-CP-1](remediations-apiserver.md#r-cp-1--escalate-to-provisioned-control-plane).

### R-APF-3 — Single caller dominating

**Trigger:** One user agent or service account > 30% of LIST volume (CP5/CP6).

**Why:** Most often a misconfigured controller doing full-cluster LIST every reconcile, instead of using a shared informer cache. Common offenders: monitoring agents (`datadog-agent`, custom Prometheus exporters), CI/CD bots, kubectl in a for-loop.

**Action — in priority order:**

1. **Use shared informers.** From [scale-control-plane.md — Use Shared Informers](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#use-shared-informers): controllers should LIST once and WATCH for updates. If the offender is in your control, fix it in code.
2. **Add field selectors to LIST calls** so they only fetch what they need:
   ```text
   GET /api/v1/pods?fieldSelector=spec.nodeName=ip-10-0-1-2
   ```
3. **For kubectl-in-a-loop scripts:** use `kubectl --cache-dir=/tmp/kubecache` with shared cache, or batch via labels. Disable kubectl compression with `--disable-compression=true` to reduce server CPU ([scale-control-plane.md](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html#disable-kubectl-compression)).
4. **Rate-limit the offender** using a FlowSchema as in [R-APF-2](#r-apf-2--system-or-leader-election-throttling).

