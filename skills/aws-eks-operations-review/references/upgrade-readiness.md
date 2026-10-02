# Cross-cutting checklist: Upgrade readiness

Not a pillar — a **pre-upgrade assessment** that pulls signals from several pillars (Operations, Resilience, Scalability) plus AWS-API facts. Use when the user asks "is this cluster ready to upgrade?", a pre-upgrade / pre-migration check, or as a CWR section. Grade **PASS / FAIL / N/A** with evidence, severity, recommendation; AWS-API items stay N/A in kubectl-only mode.

Anchor: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

Reads discovery areas: 1 CLUSTER_INFO, 2 NODES, 4/5 workloads, 14 PDB, 23 CRDS, 27 KUBE_SYSTEM_RESOURCES, 28 AUTOSCALING_INFRA, 36 DATA_PLANE, 37 SCALABILITY.

## Currency framing (read first)

- **Version lifecycle:** EKS keeps ~3 active minor versions; a minor gets **14 months standard support + 12 months extended** (26 total) before **auto-upgrade**. Deprecation notices ≥60 days before end-of-standard-support. Don't let a cluster ride to auto-upgrade — plan it.
- **One minor at a time, in place:** in-place upgrades go one minor per step (1.29→1.30→1.31); multi-version jumps are sequential. For big jumps, **blue/green clusters** are the lower-risk alternative.
- **Control plane first, then data plane:** AWS upgrades the control plane on your trigger; **you** upgrade the data plane (nodes, Fargate, addons) after. Keep CP and kubelet within the supported skew.
- **Shared responsibility:** AWS = control plane; you = data plane + addons + workload API-compatibility.

## Readiness checks (U-series)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| U1 | Version in standard support | kubectl `version` + release calendar | not in extended support / near auto-upgrade | High | Upgrade before end-of-standard-support; don't rely on auto-upgrade. |
| U2 | One-minor-step plan | current vs target version | upgrade path is sequential single-minor steps | High | Multi-minor jumps need sequential upgrades or blue/green. |
| U3 | Control-plane/kubelet skew | area 2 kubeletVersion vs API server | nodes within supported skew of control plane | High | Upgrade lagging nodes first; don't widen skew. |
| U4 | Node version consistency | area 2/36 | all nodes one kubelet minor | High | Finish any stalled node rollout before upgrading. |
| U5 | Removed/deprecated API usage (live) | area 23/24 + Sc14/Sc15 + Cluster Insights + [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md) | no live CRD/webhook/FlowSchema/workload `apiVersion` whose **removed-in ≤ target** | Critical | Match observed apiVersions against [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md); run **EKS Cluster Insights** (AX1) + pluto/kube-no-trouble; remediate before CP upgrade. `kubectl-convert` for manifests. |
| U5b | Deprecated-API proactive warning | same | resources on an apiVersion **deprecated ≤ target but not yet removed** | Medium | Migrate ahead of the removal release so the *next* upgrade isn't blocked. |
| U5c | Deprecated APIs in Helm releases | Helm release Secrets (`owner=helm`) | no deprecated apiVersion in **stored chart manifests** (not visible via live API) | Critical | Decode the release Secret (base64 → gzip → base64 → JSON), scan the rendered manifest against [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md). `helm mapkubeapis` then `helm upgrade` to rewrite stored manifests. |
| U5d | Third-party CRD API deprecations | area 23 + [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md) | no Istio/cert-manager (etc.) CRD on a removed apiVersion | High | Bump the component to a version that serves the current CRD apiVersion; see its compatibility matrix. |
| U6 | Addon compatibility | area 27 + AWS-API | CNI/CoreDNS/kube-proxy/CSI addon versions compatible with target minor | High | EKS does not auto-update addons — bump them as part of the upgrade. |
| U7 | EKS-managed addons (not self-managed) | area 27 | core components are EKS managed addons | Medium | Managed addons simplify version-compatible upgrades. |
| U8 | Managed nodes / Karpenter / Auto Mode | area 28/36 | data plane on MNG, Karpenter, or Auto Mode (not unmanaged self-managed) | Medium | These automate node upgrades; self-managed needs eksctl/IaC. |
| U9 | PDBs for upgrade availability | area 14 (R6/R7) | multi-replica workloads have non-blocking PDBs | High | PDBs keep workloads available during node drains; blocking PDBs stall the drain. |
| U10 | Topology spread / anti-affinity | area 35 (R4/R5) | replicas spread across nodes/AZs | High | Avoids full-app disruption when a node is drained. |
| U11 | Karpenter node expiry | area 28 (Op13) | NodePools set `expireAfter` (not Never) | Medium | Expiry refreshes nodes onto patched AMIs automatically. |
| U12 | Karpenter Drift enabled | area 28 | Drift remediation in use | Medium | Drift auto-replaces nodes when NodeClass/AMI changes — smooths data-plane upgrades. |
| U13 | IP headroom for surge | area 25/26 + Sc11 | enough free IPs/subnet capacity for rolling surge nodes | High | Upgrades launch new nodes; IP exhaustion blocks the rollout. |
| U14 | EKS IAM role intact | AWS-API | cluster IAM role + required policies present | Medium | Missing role permissions fail the upgrade. |
| U15 | Node AMI family not end-of-life | area 2 node labels / AMI type | not on **AL2** when target ≥ 1.33 (AL2 deprecated 1.32, removed 1.33+) | Critical | Migrate MNG/Karpenter to **AL2023** or **Bottlerocket** before the upgrade; AL2 AMIs are unavailable on 1.33+. |
| U16 | kube-proxy not in deprecated IPVS mode | area 27 kube-proxy ConfigMap `mode` | not `ipvs` when target ≥ 1.35 (IPVS deprecated 1.35, removed 1.36) | High | Plan migration off IPVS mode; validate iptables/nftables mode for the service scale. |
| U17 | No unmaintained Ingress-NGINX community controller | area 33 controllers | not running the unmaintained `kubernetes/ingress-nginx` community controller | Medium | Migrate to a maintained ingress (AWS LB Controller / Gateway API / vendor-supported NGINX). |
| U18 | No docker.sock / dockershim mounts | area 4/5/7 volume mounts | no pod mounts `docker.sock`/`dockershim.sock` | High | Containerd is the only runtime since 1.24 — these mounts break. Use CRI/containerd APIs or remove. |
| U19 | StatefulSet minReadySeconds | area 5 `spec.minReadySeconds` | StatefulSets set `minReadySeconds > 0` | Medium | Prevents premature "ready" during rolling node replacement. |
| U20 | StatefulSet terminationGracePeriod not zero | area 5 pod spec | no StatefulSet with `terminationGracePeriodSeconds: 0` | High | Zero grace = unsafe termination during drain; set a real grace period. |
| U21 | No forgotten scaled-to-zero workloads | area 4/5 `replicas` | flag Deployments/StatefulSets at 0 replicas | Medium | Confirm intentional; zero-replica workloads are easy to miss during post-upgrade validation. |
| U22 | EC2 instance service-quota headroom | AWS-API service-quotas | vCPU/instance quota allows the rolling-surge node count | Medium | Node rolling replacement launches surge instances; a tight quota stalls the rollout. Request an increase first. |
| U23 | EBS gp3 volume quota headroom | AWS-API service-quotas | gp3 volume + storage quota covers PV re-attach during node replacement | Medium | PVs re-attach as nodes cycle; insufficient gp3 quota blocks pod restart. |
| U24 | EBS gp2 volume quota headroom | AWS-API service-quotas | gp2 volume + storage quota covers PV re-attach (if gp2 in use) | Medium | Same as U23 for any remaining gp2 PVs. |

## Process / manual checks (UM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| UM1 | Run EKS Cluster Insights | AWS-API | `ListInsights` / `DescribeInsight` (`aws eks list-insights`) / console — authoritative removed-API + readiness signal. See the AWS-API component (AX1, `aws-api-checks.md`). |
| UM2 | Control-plane logging on for the upgrade | AWS-API | enable api/audit logs to catch upgrade-time errors. |
| UM3 | Backup before upgrade | external | Velero / etcd-level backup taken (optional but recommended). |
| UM4 | Non-prod rehearsal | process | upgrade tested in a lower environment / CI first. |
| UM5 | Restart Fargate deployments post-CP-upgrade | process | roll Fargate pods so they land on the new kubelet. |
| UM6 | Upgrade runbook + cadence | process | documented runbook; upgrade at least annually. |
| UM7 | Blue/green for large jumps | architecture | evaluate a new cluster + traffic shift when skipping multiple minors. |
| UM8 | Specific feature removals | release notes | dockershim (1.25 → DDS), PSP (1.25 → PSA/PaC), in-tree storage (→ CSI). |

## How to run

Discover once, then grade U1–U24 from the inventory + area detail, and flag UM1–UM8 as manual/AWS-API. Lead the report with U5/U5c (removed APIs — live **and** Helm-stored) and U9/U10 (availability during drain) — those are the most common upgrade-breakers — followed by U15 (AL2 AMI) for any target ≥ 1.33. For the authoritative removed-API list, **EKS Cluster Insights** (UM1) is the source of truth; kubectl discovery + [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md) is a fast first pass. The service-quota checks (U22–U24) and Helm-secret scan (U5c) need AWS-API / Helm access — mark N/A and flag for follow-up when unavailable.

### Decoding Helm release manifests (U5c)

Helm stores the rendered manifest in a Secret of type `helm.sh/release.v1`. Deprecated apiVersions there are invisible to the live API but still break `helm upgrade` after a cluster upgrade. To inspect (read-only):

```
kubectl get secret -A -l owner=helm -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'
# release data is base64 → gzip → base64 → JSON; the .manifest field holds the rendered YAML
```

Scan the rendered manifest's `apiVersion`/`kind` pairs against [`k8s-deprecated-apis.md`](k8s-deprecated-apis.md). Remediate with `helm mapkubeapis <release> -n <ns>` then `helm upgrade`. If Helm/secret access isn't available, mark U5c **N/A** and recommend the user run `helm mapkubeapis --dry-run` per release.
