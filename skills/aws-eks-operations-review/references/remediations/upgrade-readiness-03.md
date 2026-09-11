# Upgrade Readiness remediations — shard 03

Canonical IDs: `U14,U15,U16,U17,U18,U19,U20,U21`

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

