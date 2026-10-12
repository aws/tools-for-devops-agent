# Upgrade Readiness remediations — shard 02
Canonical IDs: `U14,U15,U16,U17,U18,U19,U20,U21,U22,U23,U24,UM1,UM2,UM3,UM4,UM5,UM6,UM7,UM8`

### U14 — EKS IAM role intact *(AWS-API)*
**Why it matters:** Missing cluster IAM role permissions fail the upgrade.
**How to verify / fix:** Confirm the cluster IAM role and required policies are present and unchanged before upgrading.
**References:**
- [EKS User Guide — Cluster IAM role](https://docs.aws.amazon.com/eks/latest/userguide/service_IAM_role.html)

### U15 — Node AMI family not end-of-life
**Why it matters:** Amazon Linux 2 EKS AMIs are **deprecated in 1.32 and unavailable on 1.33+**. A node group still on AL2 cannot launch new nodes after the upgrade — node replacement and scaling break.
**Steps:**
1. Identify AMI type per MNG (`aws eks describe-nodegroup`) / Karpenter `EC2NodeClass.amiFamily`.
2. Migrate to **AL2023** or **Bottlerocket** before upgrading to 1.33+; test workloads on the new AMI in non-prod (cgroup v2, kernel differences).
**References:**
- [EKS User Guide — Amazon Linux 2 deprecation](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html)
- [EKS User Guide — AL2023 AMIs](https://docs.aws.amazon.com/eks/latest/userguide/al2023.html)

### U16 — kube-proxy not in deprecated IPVS mode
**Why it matters:** kube-proxy **IPVS mode is deprecated in K8s 1.35 and removed in 1.36**. A cluster on IPVS will lose kube-proxy service routing on the removal release.
**Steps:**
1. Check: `kubectl -n kube-system get configmap kube-proxy-config -o yaml | grep mode` (or the kube-proxy DaemonSet args).
2. Plan migration to `iptables` (or `nftables`) mode; validate at your service scale before 1.36.
**References:**
- [Kubernetes — kube-proxy IPVS](https://kubernetes.io/docs/reference/networking/virtual-ips/)

### U17 — No unmaintained Ingress-NGINX community controller
**Why it matters:** The community `kubernetes/ingress-nginx` project is on an announced retirement path (verify current upstream status); running it leaves you on an unmaintained, security-exposed ingress data path.
**Steps:** Inventory ingress controllers; migrate to a supported option — AWS Load Balancer Controller, Gateway API, or a vendor-supported NGINX — and cut traffic over before the community controller goes EOL.
**References:**
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/)
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)

### U18 — No docker.sock / dockershim mounts
**Why it matters:** EKS nodes have run **containerd only since K8s 1.24** — there is no `docker.sock`/`dockershim.sock`. Pods (CI runners, build tools, log shippers) mounting it fail on modern nodes.
**Steps:**
1. Find them: `kubectl get pods -A -o json | jq -r '.items[] | select(.spec.volumes[]?.hostPath.path | tostring | test("docker.*sock")) | .metadata.namespace + "/" + .metadata.name'`
2. Replace with the containerd CRI socket, a rootless builder (BuildKit/Kaniko), or the Kubernetes API — remove the hostPath mount.
**References:**
- [Kubernetes — dockershim removal FAQ](https://kubernetes.io/blog/2022/02/17/dockershim-faq/)

### U19 — StatefulSet minReadySeconds
**Why it matters:** With `minReadySeconds: 0`, a StatefulSet pod is considered available the instant it reports Ready during a rolling node replacement — before it has truly settled — so the rollout can march to the next replica too early and cause a quorum/availability dip.
**Steps:** Set `spec.minReadySeconds` (e.g. 10–30s) on StatefulSets so each pod must stay Ready before the rollout proceeds.
**Snippet:**
```yaml
spec:
  minReadySeconds: 15
```
**References:**
- [Kubernetes — StatefulSet rolling updates](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/#rolling-update)

### U20 — StatefulSet terminationGracePeriod not zero
**Why it matters:** `terminationGracePeriodSeconds: 0` force-kills pods immediately during a node drain — no graceful shutdown, risking data corruption for stateful apps (databases, queues) during the upgrade.
**Steps:** Set a real grace period (≥ the app's clean-shutdown time) on StatefulSets; pair with a `preStop` hook where the app needs to flush.
**References:**
- [Kubernetes — Pod termination](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)

### U21 — No forgotten scaled-to-zero workloads
**Why it matters:** Workloads at 0 replicas are easy to miss during post-upgrade validation — a deprecated API or broken image only surfaces when something scales them back up, long after the upgrade.
**Steps:** List `replicas: 0` Deployments/StatefulSets; confirm each is intentional, and validate they still admit (no removed APIs / valid image) so a later scale-up doesn't fail.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U22 — EC2 instance service-quota headroom *(AWS-API)*
**Why it matters:** Rolling node replacement launches **surge** instances before terminating old ones. If the EC2 vCPU / instance quota is near its ceiling, the surge can't launch and the node rollout stalls mid-upgrade.
**How to verify / fix:** Compare running instances against the relevant quota (`aws service-quotas get-service-quota --service-code ec2 --quota-code <vCPU quota>`); request an increase before upgrading if headroom is tight.
**References:**
- [Service Quotas — Requesting a quota increase](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html)
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### U23 — EBS gp3 volume quota headroom *(AWS-API)*
**Why it matters:** As nodes cycle, EBS-backed PVs detach and re-attach on the replacement node. Insufficient gp3 volume / storage quota blocks PV re-attachment, leaving stateful pods stuck Pending.
**How to verify / fix:** Check the gp3 volume + storage quota (`aws service-quotas get-service-quota --service-code ebs ...`) against current usage plus the expected churn; request an increase if tight.
**References:**
- [Service Quotas — Amazon EBS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-resource-quotas.html)

### U24 — EBS gp2 volume quota headroom *(AWS-API)*
**Why it matters:** Same re-attachment risk as U23 for any remaining gp2 PVs during node replacement.
**How to verify / fix:** Check the gp2 volume + storage quota against usage; migrate gp2→gp3 (cheaper, faster — see cost pillar) and ensure quota headroom before upgrading.
**References:**
- [Service Quotas — Amazon EBS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-resource-quotas.html)

## Upgrade — manual / process (UM)

### UM1 — Run EKS Cluster Insights
**Why / fix:** Authoritative removed-API + readiness signal. [`ListInsights`](https://docs.aws.amazon.com/eks/latest/APIReference/API_ListInsights.html) / [`DescribeInsight`](https://docs.aws.amazon.com/eks/latest/APIReference/API_DescribeInsight.html) (`aws eks list-insights`) or console. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM2 — Control-plane logging on for the upgrade
**Why / fix:** Enable api/audit logs to catch upgrade-time errors. `aws eks update-cluster-config`. Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).

### UM3 — Backup before upgrade
**Why / fix:** Take a Velero / etcd-level backup before upgrading (recommended). Link: [Velero](https://velero.io/docs/).

### UM4 — Non-prod rehearsal
**Why / fix:** Rehearse the upgrade in a lower environment / CI first. Process check.

### UM5 — Restart Fargate deployments post-CP-upgrade
**Why / fix:** Roll Fargate pods after the control-plane upgrade so they land on the new kubelet version. Process check.

### UM6 — Upgrade runbook + cadence
**Why / fix:** Maintain a documented runbook and upgrade at least annually. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM7 — Blue/green for large jumps
**Why / fix:** For multi-minor jumps, stand up a new cluster and shift traffic rather than chained in-place upgrades. Link: [Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html).

### UM8 — Specific feature removals
**Why / fix:** Account for dockershim (1.25 → containerd/DDS), PSP (1.25 → PSA/PaC), in-tree storage (→ CSI). Check release notes for the target version. Link: [Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/).
