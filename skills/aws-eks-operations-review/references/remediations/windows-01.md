# Windows remediations — shard 01

Canonical IDs: `W1,W2,W3,W4,W5,W6,W7,W8`

### W1 — OS nodeSelector on Windows workloads
**Why it matters:** Without `nodeSelector: kubernetes.io/os=windows`, Windows pods can be scheduled onto Linux nodes and fail to start.
**Steps:** Add the OS nodeSelector (and matching toleration for the Windows taint, W2) to every Windows workload.
**Snippet:**
```yaml
spec:
  nodeSelector: { kubernetes.io/os: windows }
  tolerations: [{ key: os, operator: Equal, value: windows, effect: NoSchedule }]
```
**References:**
- [EKS Best Practices — Windows scheduling](https://docs.aws.amazon.com/eks/latest/best-practices/windows-scheduling.html)

### W2 — Windows nodes tainted
**Why it matters:** Without a taint, existing Linux Deployments can land on Windows nodes (and fail) without anyone editing them.
**Steps:** Taint Windows nodes `os=windows:NoSchedule`; only Windows pods with the matching toleration schedule there.
**References:**
- [EKS Best Practices — Windows scheduling](https://docs.aws.amazon.com/eks/latest/best-practices/windows-scheduling.html)

### W3 — windows-build matching
**Why it matters:** A Windows container's base-image build must match the node's Windows build; a mismatch fails to run.
**Steps:** In multi-build clusters, select on `node.kubernetes.io/windows-build` so pods land on a matching kernel build.
**References:**
- [EKS Best Practices — Windows AMI](https://docs.aws.amazon.com/eks/latest/best-practices/windows-ami.html)

### W4 — RuntimeClass for Windows
**Why it matters:** Repeating OS selectors/tolerations on every Windows pod is error-prone; a RuntimeClass centralizes it.
**Steps:** Define a Windows RuntimeClass with the nodeSelector/tolerations and reference it from Windows pods.
**References:**
- [EKS Best Practices — Windows scheduling](https://docs.aws.amazon.com/eks/latest/best-practices/windows-scheduling.html)

### W5 — Memory requests + limits on Windows pods
**Why it matters:** Windows has **no OOM killer** — it pages to disk under memory pressure, so one over-using pod can slow the whole node. Limits are more important, not less.
**Steps:** Set memory `requests` **and** `limits` on every Windows container; size to the working set including the base image.
**References:**
- [EKS Best Practices — Windows OOM](https://docs.aws.amazon.com/eks/latest/best-practices/windows-oom.html)

### W6 — Realistic memory baseline
**Why it matters:** Under-requesting Windows images (which are large: Server Core ~45MB+ base, plus .NET/IIS) causes scheduling and paging problems.
**Steps:** Set requests accounting for the Windows base image + runtime + app.
**References:**
- [EKS Best Practices — Windows OOM](https://docs.aws.amazon.com/eks/latest/best-practices/windows-oom.html)

### W7 — kubelet/system memory reservation
**Why it matters:** Without reserving memory for the OS+kubelet, node-wide paging can occur under load.
**Steps:** Reserve ≥2GB via `--kube-reserved`/`--system-reserved` in the Windows node bootstrap config.
**References:**
- [EKS Best Practices — Windows OOM](https://docs.aws.amazon.com/eks/latest/best-practices/windows-oom.html)

### W8 — IP capacity for pod density
**Why it matters:** Windows nodes use a **single ENI**, so default secondary-IP mode tightly caps pods/node.
**Steps:** Do the single-ENI IP math for required density; enable prefix delegation (W9) if you need more.
**References:**
- [EKS Best Practices — Windows networking](https://docs.aws.amazon.com/eks/latest/best-practices/windows-networking.html)

