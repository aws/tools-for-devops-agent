# Security Pods Rbac remediations — shard 01

Canonical IDs: `S1,S2,S3,S4,S5,S6,S7,S8`

### S1 — No privileged containers
**Why it matters:** A privileged container has effectively root on the host — a container escape becomes a node compromise, then lateral movement.
**Steps:**
1. Find them: `kubectl get pods -A -o json | jq -r '.items[] | .metadata as $m | .spec.containers[] | select(.securityContext.privileged==true) | "\($m.namespace)/\($m.name)/\(.name)"'`
2. Remove `privileged: true`; grant only the specific Linux capability needed. Enforce with Pod Security Admission `restricted` or a policy engine.
**Snippet:**
```yaml
securityContext:
  privileged: false
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]   # only if required
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)
- [Kubernetes — Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

### S2 — No host namespaces
**Why it matters:** `hostNetwork`/`hostPID`/`hostIPC` break the container isolation boundary — a pod can see host processes, sniff node traffic, or share IPC with the host.
**Steps:** Remove host-namespace flags from workloads (legitimate only for specific system DaemonSets). Enforce via PSA `baseline`/`restricted`.
**Snippet:**
```yaml
spec:
  hostNetwork: false
  hostPID: false
  hostIPC: false
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)

### S3 / S4 / S5 — Pod hardening (allowPrivilegeEscalation / drop ALL caps / seccomp RuntimeDefault)
**Why it matters:** These three together close the most common privilege-escalation and syscall-abuse paths and are exactly what the PSA `restricted` profile enforces.
**Steps:**
1. Set `allowPrivilegeEscalation: false`, drop `ALL` capabilities, and set `seccompProfile: RuntimeDefault` on every workload container.
2. Enforce cluster-wide via PSA labels on namespaces or a policy engine (Kyverno/Gatekeeper) so new workloads can't regress.
**Snippet (container + pod securityContext):**
```yaml
spec:
  securityContext:
    seccompProfile: { type: RuntimeDefault }
  containers:
    - name: ${APP}
      securityContext:
        allowPrivilegeEscalation: false
        runAsNonRoot: true
        capabilities: { drop: ["ALL"] }
```
**Snippet (enforce restricted on a namespace):**
```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)
- [EKS Best Practices — Runtime Security](https://docs.aws.amazon.com/eks/latest/best-practices/runtime-security.html)
- [Kubernetes — Enforce Pod Security Standards with Namespace Labels](https://kubernetes.io/docs/tasks/configure-pod-container/enforce-standards-namespace-labels/)

### S6 — readOnlyRootFilesystem
**Why it matters:** A writable root filesystem lets an attacker drop binaries, modify config, or persist inside a running container.
**Steps:** Set `readOnlyRootFilesystem: true`; mount `emptyDir` for the few paths the app must write (tmp, cache).
**Snippet:**
```yaml
securityContext:
  readOnlyRootFilesystem: true
volumeMounts:
  - { name: tmp, mountPath: /tmp }
volumes:
  - { name: tmp, emptyDir: {} }
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)

### S7 — runAsNonRoot
**Why it matters:** Containers running as UID 0 inherit host-root capabilities on escape. Running as a non-root user is a cheap, high-value hardening.
**Steps:** Set `runAsNonRoot: true` (and a concrete `runAsUser`) on workloads; rebuild images with a non-root `USER` where the process requires a fixed UID.
**Snippet:**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
```
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)

### S8 — No hostPath volumes
**Why it matters:** A `hostPath` mount exposes the node filesystem to the pod — a path to read host secrets or escape to the node.
**Steps:** Replace hostPath with `emptyDir`, PVCs, or CSI volumes. Where a host mount is unavoidable (system agents), restrict to a specific path and mount read-only.
**References:**
- [EKS Best Practices — Pod Security](https://docs.aws.amazon.com/eks/latest/best-practices/pod-security.html)

