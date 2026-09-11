# Operations remediations — shard 01

Canonical IDs: `Op1,Op2,Op3,Op4,Op5,Op6,Op7,Op8`

### Op1 — Kubernetes version currency
**Why it matters:** Versions in extended support cost more and stop getting features; at end-of-life EKS auto-upgrades you, risking unplanned disruption. Each minor gets 14 months standard + 12 months extended support.
**Steps:**
1. Check current vs supported: `kubectl version` and the EKS release calendar.
2. Plan sequential single-minor in-place upgrades (run the upgrade-readiness checklist first). Adopt a regular cadence (at least annually).
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [EKS User Guide — Kubernetes version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)

### Op2 — Node version consistency
**Why it matters:** Nodes lagging the control plane (or each other) widen version skew, risk unsupported kubelet/API-server combinations, and signal a stalled rollout that will compound at the next upgrade.
**Steps:**
1. List kubelet versions: `kubectl get nodes -o custom-columns=NAME:.metadata.name,KUBELET:.status.nodeInfo.kubeletVersion`
2. Finish the stalled node rollout (cycle MNG/Karpenter nodes) so all nodes are one kubelet minor and within 1 of the control plane.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [Kubernetes — Version skew policy](https://kubernetes.io/releases/version-skew-policy/)

### Op3 — Core addon presence (CNI/CoreDNS/kube-proxy/CSI)
**Why it matters:** These are the cluster's data-path foundation. A missing or unhealthy core addon degrades networking, DNS, or storage cluster-wide.
**Steps:**
1. Check kube-system: `kubectl get ds,deploy -n kube-system` — confirm `aws-node`, `kube-proxy`, `coredns`, and the EBS/EFS CSI driver are present and Ready.
2. Install/repair any missing managed addon (prefer EKS managed addons over self-managed manifests).
**References:**
- [EKS User Guide — Amazon EKS add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)

### Op4 — Managed vs self-managed nodes
**Why it matters:** Self-managed nodes put AMI patching, version upgrades, and lifecycle on you. Managed node groups / Karpenter / Auto Mode automate that and reduce upgrade risk.
**Steps:**
1. Inspect node labels for `eks.amazonaws.com/nodegroup` (MNG) or Karpenter ownership.
2. Migrate unmanaged self-managed nodes to MNG or Karpenter for automated AMI lifecycle.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [EKS User Guide — Managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)

### Op5 — Resource governance tags / labels
**Why it matters:** Namespaces without team/owner/env labels break cost allocation, ownership routing, and policy targeting.
**Steps:** Apply organizational labels (`team`, `env`, `cost-center`) to workload namespaces; enforce with a policy engine so new namespaces inherit the standard.
**Snippet:**
```yaml
metadata:
  labels: { team: payments, env: prod, cost-center: "1234" }
```
**References:**
- [EKS Best Practices — Cost Optimization: Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html)

### Op6 — IaC / GitOps management
**Why it matters:** Click-ops / imperative changes drift from source control, are hard to audit, and can't be reliably reproduced or rolled back.
**Steps:** Manage cluster state declaratively — ArgoCD or Flux for in-cluster manifests, Terraform/CloudFormation/CDK for the AWS-side cluster + nodegroups.
**References:**
- [EKS Best Practices — Cluster Upgrades (IaC)](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### Op7 — Addon versions current *(AWS-API)*
**Why it matters:** EKS does not auto-update addons. A CNI/CoreDNS/kube-proxy/CSI version far behind the cluster minor can break at upgrade time or miss security fixes.
**How to verify / fix:** `aws eks describe-addon --cluster-name ${CLUSTER} --addon-name vpc-cni` (repeat per addon); compare to `aws eks describe-addon-versions`. Bump addons as part of each upgrade.
**References:**
- [EKS User Guide — Updating an add-on](https://docs.aws.amazon.com/eks/latest/userguide/updating-an-add-on.html)

### Op8 — Node Monitoring Agent present
**Why it matters:** The EKS Node Monitoring Agent surfaces node-level health (kernel, networking, storage) as NodeConditions and is the **prerequisite** for Node Auto Repair (Op26). Without it, node faults go undetected. It is configured independently from auto-repair.
**Steps:** Enable the `eks-node-monitoring-agent` EKS add-on. Node Auto Repair is a separate setting — see **Op26**.
**References:**
- [EKS User Guide — Node health and auto repair](https://docs.aws.amazon.com/eks/latest/userguide/node-health.html)

