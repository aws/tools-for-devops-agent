# Cluster, version & add-on health (CA-series)

The AWS-side control-plane-object health that neither kubectl nor CloudWatch metrics show:
cluster status & health issues, Kubernetes version support (standard vs **extended**), EKS managed
add-on health, whether core components are actually running, and EKS Cluster Insights. Grade each
**✅ HEALTHY / ⚠️ ATTENTION / ❌ ACTION / ⚪ N/A** with the observed value as evidence.

> **Sources:** `use_aws` — `eks describe-cluster`, `eks list-addons` / `describe-addon`,
> `eks describe-addon-versions`, `eks list-insights` / `describe-insight`; `use_kubectl` for the
> core-component running check. All read-only.

## Cluster status & health issues

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| CA1 | Cluster status ACTIVE | `describe-cluster` → `status` | `ACTIVE` | Critical (CREATING/UPDATING transient; `FAILED`/`DELETING` = impaired) |
| CA2 | No cluster health issues | `describe-cluster` → `health.issues` | empty | Critical/High — surface each `ClusterIssue` code + message (e.g. deleted subnet → "could not create network interface", missing/again-assumable **cluster IAM role**, changed/deleted **cluster security group**, `Ec2SecurityGroupDeleted`, `IamRoleNotFound`, `SubnetNotFound`, `InsufficientFreeAddresses`). EKS can take up to 3 h to detect/clear. |
| CA3 | Control-plane logging enabled | `describe-cluster` → `logging` | ≥ `api`,`audit` | Medium — and it **gates CP1–CP11 audit-log grading**; if off, raise here and grade CP from metrics. |

## Kubernetes version & support (extended-support awareness)

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| CA4 | Version in **standard** support | `describe-cluster` → `version` vs the EKS version calendar | in standard support, not near end | **High** if in **extended support** (extra cost/cluster-hour + eligible for forced auto-upgrade at extended EOL); **High** if within 60 days of end-of-standard-support; Medium if 60–120 days out. |
| CA5 | Upgrade policy | `describe-cluster` → `upgradePolicy.supportType` (`STANDARD`/`EXTENDED`) | intentional | Info — `STANDARD` = auto-upgraded at end of standard support (plan the upgrade); `EXTENDED` = stays + billed. State which, and days remaining in the current period. |

> Standard support = 14 months from the version's EKS GA; extended support = the next 12 months
> (26 total) at additional cost. At the end of extended support the control plane is auto-upgraded.
> Report the cluster's version, `supportType`, current period, and the upgrade recommendation.

## EKS managed add-on health

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| CA6 | All managed add-ons healthy | `list-addons` → `describe-addon` → `status` | `ACTIVE` | Critical if `CREATE_FAILED`/`DELETE_FAILED`; High if `DEGRADED`/`UPDATE_FAILED`. Surface each add-on + status. |
| CA7 | No add-on health issues | `describe-addon` → `health.issues[].code` | empty | High — report each code: `InsufficientNumberOfReplicas`, `ConfigurationConflict`, `AccessDenied`, `AdmissionRequestDenied`, `AddonPermissionFailure`, `AddonSubscriptionNeeded`, `ClusterUnreachable`, `K8sResourceNotFound`, `UnsupportedAddonModification`, `InternalFailure`. Common root cause: missing IAM/Pod-Identity permission or a config conflict. |
| CA8 | Add-on versions current / compatible | `describe-addon` `addonVersion` vs `describe-addon-versions --kubernetes-version <v>` | on a supported version for the cluster K8s version | Medium — flag out-of-support or upgrade-incompatible add-on versions (also an upgrade blocker). |

## Core & installed add-on / controller health (kubectl)

An EKS cluster runs more than the EKS *managed* add-ons (CA6). Grade **every** installed
add-on/controller/operator, however it was installed (managed add-on, Helm, raw manifests) — if
it's running and unhealthy, it's a health problem.

| ID | Check | Source (`use_kubectl -n kube-system`) | Healthy | Severity if breached |
|----|-------|----------------------------------------|---------|----------------------|
| CA9 | Core data-path components Ready | Deployment/DaemonSet ready vs desired for **CoreDNS** (`deploy/coredns` availableReplicas ≥ 2), **kube-proxy** (`ds/kube-proxy` numberReady==desired), **VPC CNI** (`ds/aws-node` numberReady==desired), and the **EBS/EFS CSI** driver DaemonSets if installed | all Ready, no gap | Critical if CoreDNS or aws-node not Ready (cluster-wide DNS/networking impact); High if kube-proxy/CSI degraded. Catches "add-on installed but pods not running" (self-managed or a `DEGRADED` managed add-on). |
| CA14 | **All other add-ons & controllers Ready** (self-managed / Helm / third-party — not just EKS managed add-ons) | `use_kubectl` — enumerate Deployments/DaemonSets/StatefulSets across `kube-system` and add-on namespaces; for each, `availableReplicas`/`numberReady` == desired and no CrashLoopBackOff/ImagePullBackOff | every discovered controller fully Ready | High if any add-on/controller is not fully Ready; Critical if it's in the data path (networking/DNS/storage/ingress). Report **every** discovered add-on + its ready/desired, and whether it's an EKS **managed** add-on (CA6) or **self-managed**. |

**Enumerating add-ons/controllers for CA14.** Don't rely on a fixed list — discover what's actually
deployed and check each. Look across `kube-system` and common add-on namespaces (`cert-manager`,
`karpenter`, `kube-system`, `external-dns`, `amazon-cloudwatch`, `opentelemetry-operator-system`,
`adot`, `kube-system`/`secrets-store-csi-driver`, `argocd`, `flux-system`, `istio-system`,
`gpu-operator`/`nvidia-device-plugin`, `amazon-guardduty`). Commonly present: **AWS Load Balancer
Controller, Karpenter, Cluster Autoscaler, metrics-server, cert-manager, ExternalDNS, Secrets Store
CSI + provider, EFS/EBS CSI (if self-managed), Fluent Bit / CloudWatch agent, ADOT / OpenTelemetry
operator, Node Monitoring Agent, GuardDuty agent, service mesh (Istio/Linkerd), GitOps
(ArgoCD/Flux), GPU/Neuron device plugins**. For each: is `availableReplicas`/`numberReady` ==
desired, and are pods free of CrashLoopBackOff/ImagePullBackOff? A controller that's scaled to 0,
crash-looping, or stuck pending is a CA14 finding. Cross-reference the managed-add-on list (CA6) so
each is labeled **managed** vs **self-managed**.

## EKS Cluster Insights

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| CA10 | Upgrade insights passing | `list-insights` (category `UPGRADE_READINESS`) → `describe-insight` | all `PASSING` | High for any non-`PASSING` — deprecated/removed API usage, incompatible add-ons, kubelet/kube-proxy skew, AL2 EOL. **These are Cluster-Insights findings — report them here, never as `CP*` checks.** |
| CA11 | Configuration insights passing | `list-insights` (category `MISCONFIGURATION`) | all `PASSING` | Medium — misconfigurations (esp. Hybrid Nodes). N/A if none apply. |
| CA12 | Rollback-readiness insights | `list-insights` (category `ROLLBACK_READINESS`) | `PASSING` / N/A | Info — only generated within 7 days of an upgrade; else ⚪ N/A. |

> Cluster Insights refresh every 24 h (or on-demand). `UNKNOWN` is not a pass — note it and
> recommend a manual refresh / verification before an upgrade.

## Node monitoring & auto-repair (cluster-level enablement)

| ID | Check | Source | Healthy | Severity if breached |
|----|-------|--------|---------|----------------------|
| CA13 | Node Monitoring Agent enabled | `eks-node-monitoring-agent` add-on ACTIVE, or `kubectl get ds -n kube-system eks-node-monitoring-agent` | present (Linux nodes) | Medium — recommended; it surfaces the node conditions in `node-health.md` (NH33) and drives auto-repair (NH27). N/A on Fargate/Windows-only. |

## Remediation pointers

All read-only recommendations (draft for human approval; never mutate):
- **CA2 cluster health issues** — recreate the missing subnet/IAM role/security group named in the issue; EKS re-detects within ~3 h. See [Cluster health FAQs & error codes](https://docs.aws.amazon.com/eks/latest/userguide/troubleshooting.html).
- **CA4/CA5 extended support** — plan a sequential single-minor upgrade to a version in standard support to stop extended-support charges and avoid a forced auto-upgrade. See [Kubernetes version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html).
- **CA6/CA7 add-on health** — read `health.issues`; the usual fix is attaching the add-on's IAM/Pod-Identity permission or re-running the update with the right `resolveConflicts` strategy. See [Managing add-ons](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html) / [describe-addon](https://docs.aws.amazon.com/cli/latest/reference/eks/describe-addon.html).
- **CA9 core components** — a `DEGRADED` managed add-on maps back to CA6/CA7; a self-managed component needs its Deployment/DaemonSet inspected (`kubectl describe`).
- **CA10 upgrade insights** — follow each insight's `recommendation` (migrate off removed APIs, bump add-on versions) before upgrading. See [Cluster insights](https://docs.aws.amazon.com/eks/latest/userguide/cluster-insights.html).
- **CA13 node monitoring** — enable the Node Monitoring Agent + [automatic node repair](https://docs.aws.amazon.com/eks/latest/userguide/node-health.html).
