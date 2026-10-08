# Decision tree: Pending pods

Use this when discovery finds `pods_pending > 0`. Do NOT conclude "scheduler failure" or
"add more nodes" without walking this tree.

## Entry point

`kubectl describe pod <pending-pod>` → read the **Events** and **Conditions** sections.

## Branches

### Branch 1 — Insufficient capacity

**Signal:** Event `FailedScheduling` with message "Insufficient cpu/memory"
**Evidence required:** Node allocatable vs. total pod requests; all nodes at capacity.
**Conclusion:** Cluster needs more capacity OR requests are over-sized.
**Check:** Are Karpenter/CAS configured? If yes, why didn't they provision?

### Branch 2 — Resource fragmentation

**Signal:** Total cluster allocatable > pod requests, but no single node can fit the pod.
**Evidence required:** Pod requests vs. largest available node capacity gap.
**Conclusion:** Capacity exists but is fragmented. Consider consolidation or larger instances.
**NOT:** "Cluster is out of capacity."

### Branch 3 — Taints and tolerations

**Signal:** `FailedScheduling` with "node(s) had untolerated taint"
**Evidence required:** Node taints vs. pod tolerations.
**Conclusion:** Pod doesn't tolerate existing node taints. Fix: add toleration or use untainted nodes.
**NOT:** "Scheduler is broken."

### Branch 4 — Node selector / node affinity

**Signal:** `FailedScheduling` with "node(s) didn't match Pod's node affinity/selector"
**Evidence required:** Pod's `nodeSelector` or `nodeAffinity` vs. available node labels.
**Conclusion:** No nodes match the pod's placement requirements.
**NOT:** "Insufficient capacity" (capacity may exist on non-matching nodes).

### Branch 5 — Pod affinity / anti-affinity

**Signal:** `FailedScheduling` with "node(s) didn't match pod anti-affinity rules"
**Evidence required:** Anti-affinity rules, existing pod placement, topology keys.
**Conclusion:** Anti-affinity prevents co-location. May need more topology domains.
**NOT:** "Scheduler failure."

### Branch 6 — Topology spread constraints

**Signal:** `FailedScheduling` with "doesn't satisfy topology spread constraint"
**Evidence required:** TopologySpreadConstraint spec, current pod distribution, `whenUnsatisfiable`.
**Conclusion:** Spread can't be satisfied in available topology. May need nodes in more zones.
**NOT:** "Add more nodes" (may need nodes in a specific zone, not just more).

### Branch 7 — Volume topology (EBS AZ mismatch)

**Signal:** `FailedScheduling` with "node(s) had volume node affinity conflict"
**Evidence required:** PV's `nodeAffinity` (EBS AZ) vs. schedulable node AZs.
**Conclusion:** The PV is in one AZ but no schedulable nodes exist in that AZ.
**Fix:** Add nodes to the PV's AZ, or use `WaitForFirstConsumer` StorageClass for new PVCs.
**NOT:** "Storage is broken."

### Branch 8 — Scheduling gates (K8s 1.26+)

**Signal:** Pod has `.spec.schedulingGates` set; no FailedScheduling event (pod never reached scheduler).
**Evidence required:** `kubectl get pod -o jsonpath='{.spec.schedulingGates}'`
**Conclusion:** An external controller (e.g. Kueue, custom admission) gated the pod.
**NOT:** "Scheduler failure" — the pod was intentionally held from scheduling.

### Branch 9 — Karpenter / Cluster Autoscaler provisioning failure

**Signal:** Pod is pending, CAS/Karpenter logs show errors or no provisioning attempt.
**Evidence required:** Karpenter controller logs (`kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter`), CAS logs, NodePool/NodeClaim status, instance-type availability, Service Quotas.
**Conclusion:** Autoscaler failed to provision. Root causes: no matching instance type available, Service Quotas exhausted, subnet IP exhaustion, launch template error, AMI not found.
**NOT:** "Scheduler is broken" — scheduler correctly reported unschedulable; the autoscaler should have responded.

### Branch 10 — Scheduler internal error

**Signal:** CP18 log query shows scheduler errors; events show `FailedScheduling` with internal error messages.
**Evidence required:** Scheduler logs (non-audit stream), `scheduler_pending_pods` metric, scheduler pod health.
**Conclusion:** Actual scheduler issue — rare on EKS (AWS-managed). Check for webhook interference, API server connectivity from scheduler, or version-specific bugs.
**THIS is the only branch that supports a "scheduler problem" conclusion.**

## Summary decision matrix

| Pending reason | Root cause | Fix direction | Severity |
|---------------|-----------|---------------|----------|
| Insufficient cpu/memory + no scale-up | Capacity gap | Add nodes / fix autoscaler | High |
| Fragmentation | Instance sizing | Consolidate or use larger instances | Medium |
| Taint mismatch | Configuration | Add toleration or dedicated pool | Medium |
| Selector/affinity miss | Configuration | Fix labels or relax constraints | Medium |
| Anti-affinity | Design constraint | More topology domains | Medium |
| Topology spread | AZ distribution | Nodes in needed zones | Medium |
| Volume AZ conflict | Storage topology | Nodes in PV's AZ | High |
| Scheduling gates | Intentional hold | Check gating controller | Low (unless stuck) |
| Autoscaler failure | Provisioning | Fix autoscaler config/quotas/IPs | High |
| Scheduler error | Control-plane issue | Investigate scheduler health | Critical |
