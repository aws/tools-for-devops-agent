# Windows remediations — shard 01
Canonical IDs: `W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,W13,W14,W15,W16,W17,W18`

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

### W9 — Prefix delegation (Windows)
**Why it matters:** `/28` prefixes (×16 IPs) per node are the density lever on Windows' single-ENI model.
**Steps:** Enable prefix delegation in the VPC Resource Controller config for Windows.
**References:**
- [EKS Best Practices — Prefix Mode (Windows)](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-win.html)

### W10 — Services-per-node port exhaustion
**Why it matters:** >100 services on a Windows node can exhaust ports (`hcnCreateLoadBalancer ... port already exists`).
**Steps:** Watch nodes with many services; enable Direct Server Return (DSR) to mitigate.
**References:**
- [EKS Best Practices — Windows networking](https://docs.aws.amazon.com/eks/latest/best-practices/windows-networking.html)

### W11 — Windows pod security context
**Why it matters:** Linux securityContext fields (`runAsNonRoot`, seccomp) don't apply to Windows — using them is ineffective; Windows has its own options.
**Steps:** Use Windows-valid options (`runAsUserName`, `windowsOptions`); don't rely on Linux PSS fields.
**References:**
- [EKS Best Practices — Windows security](https://docs.aws.amazon.com/eks/latest/best-practices/windows-security.html)

### W12 — gMSA for AD-integrated workloads
**Why it matters:** Apps needing Active Directory should use gMSA, not embedded credentials.
**Steps:** Configure the gMSA webhook + `GMSACredentialSpec` and reference it from the pod.
**References:**
- [EKS Best Practices — Windows gMSA](https://docs.aws.amazon.com/eks/latest/best-practices/windows-gmsa.html)

### W13 — Windows image hardening + scanning
**Why it matters:** Same supply-chain risk as Linux, Windows-appropriate — large/unscanned Windows images carry CVEs.
**Steps:** Scan Windows images; use a minimal base (NANO/Server Core); run as a non-default user.
**References:**
- [EKS Best Practices — Windows hardening of containers/images](https://docs.aws.amazon.com/eks/latest/best-practices/windows-hardening-containers-images.html)

### W14 — Windows worker node hardening
**Why it matters:** The Windows host/AMI should be CIS-aligned hardened.
**Steps:** Apply Windows node hardening guidance to the AMI/host.
**References:**
- [EKS Best Practices — Windows hardening](https://docs.aws.amazon.com/eks/latest/best-practices/windows-hardening.html)

## Windows — manual (W15–W18)

### W15 — EKS-optimized Windows AMI currency
**Why / fix:** Microsoft patches monthly — keep the Windows AMI current and plan node refresh cadence. Link: [Windows patching](https://docs.aws.amazon.com/eks/latest/best-practices/windows-patching.html).

### W16 — Patching strategy
**Why / fix:** Patch Windows Server + container base images; node rotation/expiry covers AMI updates. Link: [Windows patching](https://docs.aws.amazon.com/eks/latest/best-practices/windows-patching.html).

### W17 — Licensing
**Why / fix:** Understand the Windows Server licensing model (included in EC2 Windows pricing). Link: [Windows licensing](https://docs.aws.amazon.com/eks/latest/best-practices/windows-licensing.html).

### W18 — Logging & monitoring agents
**Why / fix:** Deploy Windows-capable agents (Fluent Bit for Windows, CloudWatch agent). Link: [Windows logging](https://docs.aws.amazon.com/eks/latest/best-practices/windows-logging.html).
