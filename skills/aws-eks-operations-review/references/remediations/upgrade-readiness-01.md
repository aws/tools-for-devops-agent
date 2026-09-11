# Upgrade Readiness remediations — shard 01

Canonical IDs: `U1,U2,U3,U4,U5,U5b,U5c,U5d`

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

