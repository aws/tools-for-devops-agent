# Upgrade Readiness remediations — shard 01
Canonical IDs: `U1,U2,U3,U4,U5,U5b,U5c,U5d,U6,U7,U8,U9,U10,U11,U12,U13`

### U1 — Version in standard support
**Why it matters:** Riding into extended support costs more and ends in forced auto-upgrade — plan the upgrade instead of being upgraded.
**Steps:** Check the cluster minor against the EKS release calendar; schedule the upgrade before end-of-standard-support.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U2 — One-minor-step plan
**Why it matters:** In-place upgrades go one minor at a time; skipping minors isn't supported and risks incompatibilities.
**Steps:** Plan sequential single-minor steps (1.29→1.30→1.31); for large jumps use blue/green clusters.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U3 — Control-plane/kubelet skew
**Why it matters:** Nodes outside the supported skew of the API server can fail after the control-plane upgrade.
**Steps:** Upgrade lagging nodes first so kubelet stays within supported skew; don't widen the gap.
**References:**
- [Kubernetes — Version skew policy](https://kubernetes.io/releases/version-skew-policy/)

### U4 — Node version consistency
**Why it matters:** A stalled node rollout mid-upgrade compounds skew and risk.
**Steps:** Finish any in-progress node rollout before starting the next upgrade.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U5 — Removed/deprecated API usage
**Why it matters:** Manifests using APIs removed in the target version (PSP, old Ingress, in-tree storage) break immediately after the control-plane upgrade — a hard outage.
**Steps:**
1. Run **EKS Cluster Insights** (authoritative) + pluto/kube-no-trouble as a fast pass.
2. Migrate each: PSP→PSA/policy engine, `extensions/v1beta1` Ingress→`networking.k8s.io/v1`, in-tree volumes→CSI. Use `kubectl-convert` for manifests. Remediate **before** the CP upgrade.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [Kubernetes — Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)

### U5b — Deprecated-API proactive warning
**Why it matters:** APIs already deprecated for the target version (but not yet removed) will be removed in a later minor. Migrating now keeps the *next* upgrade from being blocked.
**Steps:** Cross-reference observed apiVersions against [`k8s-deprecated-apis.md`](../k8s-deprecated-apis.md) for `deprecated-in ≤ target < removed-in`; schedule migration ahead of the removal release.
**References:**
- [Kubernetes — Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)

### U5c — Deprecated APIs in Helm releases
**Why it matters:** Helm stores the rendered manifest in a release Secret. A deprecated apiVersion there is invisible to the live API but still breaks the next `helm upgrade` after the cluster upgrade — a silent landmine.
**Steps:**
1. List release secrets: `kubectl get secret -A -l owner=helm -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'`
2. The release data is base64 → gzip → base64 → JSON; scan the `.manifest` field's apiVersion/kind pairs against [`k8s-deprecated-apis.md`](../k8s-deprecated-apis.md).
3. Remediate: `helm mapkubeapis ${RELEASE} -n ${NS}` then `helm upgrade` to rewrite the stored manifest.
**N/A** if Helm / secret read access is unavailable — flag for follow-up.
**References:**
- [helm-mapkubeapis plugin](https://github.com/helm/helm-mapkubeapis)
- [Kubernetes — Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)

### U5d — Third-party CRD API deprecations
**Why it matters:** Istio, cert-manager, and similar ship CRDs on their own apiVersions. A removed third-party apiVersion breaks the controller after upgrade even when core K8s is clean.
**Steps:** Match third-party CRD apiVersions against the third-party table in [`k8s-deprecated-apis.md`](../k8s-deprecated-apis.md); upgrade the component to a version that serves the current apiVersion (check its compatibility matrix).
**References:**
- [cert-manager — API compatibility](https://cert-manager.io/docs/installation/upgrading/)
- [Istio — Supported releases](https://istio.io/latest/docs/releases/supported-releases/)

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
