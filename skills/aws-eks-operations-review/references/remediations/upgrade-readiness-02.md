# Upgrade Readiness remediations — shard 02

Canonical IDs: `U6,U7,U8,U9,U10,U11,U12,U13`

### U6 — Addon compatibility
**Why it matters:** EKS doesn't auto-update addons; a CNI/CoreDNS/kube-proxy/CSI version incompatible with the target minor breaks at upgrade.
**Steps:** Bump each managed addon to a version compatible with the target minor as part of the upgrade.
**References:**
- [EKS User Guide — Updating an add-on](https://docs.aws.amazon.com/eks/latest/userguide/updating-an-add-on.html)

### U7 — EKS-managed addons (not self-managed)
**Why it matters:** Self-managed core components make version-compatible upgrades manual and error-prone.
**Steps:** Migrate CNI/CoreDNS/kube-proxy/CSI to EKS managed addons.
**References:**
- [EKS User Guide — Amazon EKS add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)

### U8 — Managed nodes / Karpenter / Auto Mode
**Why it matters:** Unmanaged self-managed nodes require manual AMI/version handling during upgrades.
**Steps:** Move the data plane to MNG, Karpenter, or Auto Mode for automated node upgrades.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U9 — PDBs for upgrade availability
**Why it matters:** Node drains during the data-plane upgrade can take all replicas down without PDBs; blocking PDBs stall the drain entirely.
**Steps:** Ensure multi-replica workloads have non-blocking PDBs (see R6/R7) before upgrading.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U10 — Topology spread / anti-affinity
**Why it matters:** Without spread, draining one node during the upgrade can disrupt a whole app.
**Steps:** Ensure replicas spread across nodes/AZs (see R4/R5) before the rolling node upgrade.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U11 — Karpenter node expiry
**Why it matters:** `expireAfter` refreshes nodes onto patched AMIs automatically, smoothing data-plane upgrades. (Same as Op13.)
**Steps:** Set `expireAfter` (not Never) on NodePools.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### U12 — Karpenter Drift enabled
**Why it matters:** Drift auto-replaces nodes when the NodeClass/AMI changes — the mechanism that rolls a Karpenter data plane to the new version.
**Steps:** Ensure Drift remediation is enabled; updating the AMI/NodeClass then rolls nodes automatically (gated by PDBs).
**References:**
- [Karpenter — Disruption (Drift)](https://karpenter.sh/docs/concepts/disruption/)

### U13 — IP headroom for surge
**Why it matters:** Upgrades launch new (surge) nodes; if subnets are out of IPs the rollout stalls.
**Steps:** Confirm subnet/IP headroom for surge nodes (see N3/Sc11) before upgrading.
**References:**
- [EKS Best Practices — IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html)

