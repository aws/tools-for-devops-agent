# Windows remediations — shard 02

Canonical IDs: `W9,W10,W11,W12,W13,W14`

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

