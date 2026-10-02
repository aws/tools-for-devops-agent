# Upgrade Readiness remediations — shard 05

Canonical IDs: `UM5,UM6,UM7,UM8`

### UM5 — Restart Fargate deployments post-CP-upgrade
**Why / fix:** Roll Fargate pods after the control-plane upgrade so they land on the new kubelet version. Process check.

### UM6 — Upgrade runbook + cadence
**Why / fix:** Maintain a documented runbook and upgrade at least annually. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM7 — Blue/green for large jumps
**Why / fix:** For multi-minor jumps, stand up a new cluster and shift traffic rather than chained in-place upgrades. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM8 — Specific feature removals
**Why / fix:** Account for dockershim (1.25 → containerd/DDS), PSP (1.25 → PSA/PaC), in-tree storage (→ CSI). Check release notes for the target version. Link: [Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/).
