# Resilience remediations — shard 03

Canonical IDs: `R17,RM1,RM2,RM3,RM4,R18`

### R17 — Immutable Secrets/ConfigMaps for static data
**Why it matters:** By default the kubelet watches every Secret/ConfigMap a pod mounts. At scale that watch traffic pressures the API server and etcd. Marking rarely-changed Secrets/ConfigMaps `immutable: true` stops the watches (a scalability win) and prevents an accidental edit from silently rolling every consumer.
**Steps:** Set `immutable: true` on Secrets/ConfigMaps that don't change at runtime (config, certs, static credentials). To change one later, delete and recreate it (and roll consumers intentionally).
**Snippet:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata: { name: app-config }
immutable: true
data: { ... }
```
**References:**
- [Kubernetes — Immutable Secrets and ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/#configmap-immutable)
- [EKS Best Practices — Scalability (control plane load)](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

## Resilience — manual / process (RM)

### RM1 — Rollback mechanism
**Why / fix:** Confirm a tested rollback path exists — `kubectl rollout undo deploy/${APP}` for imperative, or a GitOps revert for Argo/Flux. Link: [Updating applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html).

### RM2 — Blue-green / canary strategy
**Why / fix:** Risky changes should use progressive delivery (Argo Rollouts, Flux Flagger, or LBC weighted target groups) rather than a straight rolling update. Confirm the tooling is in place. Link: [Application HA](https://docs.aws.amazon.com/eks/latest/best-practices/application.html).

### RM3 — Chaos engineering
**Why / fix:** Resilience claims should be validated with fault injection — AWS FIS, Litmus, or Chaos Mesh exercising AZ/node/pod failure. Confirm a practice exists. Link: [AWS FIS](https://docs.aws.amazon.com/fis/latest/userguide/what-is.html).

### RM4 — Auto Mode disruption controls
**Why / fix:** On Auto Mode, tune NodePool `disruption` budgets so maintenance doesn't disrupt more than the workload tolerates. Review the NodePool. Link: [Auto Mode](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html).

### R18 — preStop hook for LB-fronted workloads
**Why it matters:** The #1 cause of 502/504 during deployments — the container can get SIGKILL before the ALB/NLB target group and `kube-proxy` stop routing to it, so in-flight requests hit a dead pod.
**Steps:** Add a `preStop` `sleep` that meets or exceeds the target-group deregistration delay, and set `terminationGracePeriodSeconds` above it.
**Snippet:**
```yaml
lifecycle:
  preStop:
    exec: { command: ["/bin/sh","-c","sleep 20"] }   # >= target-group deregistration delay
```
**References:**
- [EKS Best Practices — Load Balancing (gracefully handle client requests)](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html)

