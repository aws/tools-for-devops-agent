# Minimum RBAC and IAM permissions

## Contents

- Kubernetes RBAC — minimum ClusterRole (all 49 discovery areas)
- What this role does NOT grant
- AWS IAM — minimum permissions (incl. optional Security-services / Service-Quotas statements)
- Cross-account and scope restrictions

The EKS Operations Review skill is **strictly read-only**. This file defines the exact minimum
permissions required for the review to succeed. Use it when creating a custom access policy
(instead of the broader `AmazonAIOpsAssistantPolicy`) or when auditing what the review can access.

## Kubernetes RBAC — minimum ClusterRole

The following ClusterRole grants the minimum permissions for the full 49-area discovery.
All verbs are read-only (`get`, `list`). The skill **never** uses:
`watch` (not needed — point-in-time reads only), `create`, `update`, `patch`, `delete`,
`deletecollection`, `exec`, `attach`, `portforward`, `impersonate`, `bind`, `escalate`.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: eks-operations-review-readonly
rules:
  # Core resources (areas 1–9, 17–20)
  - apiGroups: [""]
    resources:
      - nodes
      - namespaces
      - pods
      - pods/log          # read container logs (area 7, 29)
      - services
      - endpoints
      - configmaps        # metadata only — never Secret .data
      - secrets           # metadata only (count, age, type) — never .data
      - serviceaccounts
      - persistentvolumes
      - persistentvolumeclaims
      - resourcequotas
      - limitranges
      - events
      - replicationcontrollers
    verbs: ["get", "list"]

  # Workload controllers (areas 4–6, 35)
  - apiGroups: ["apps"]
    resources:
      - deployments
      - statefulsets
      - daemonsets
      - replicasets
    verbs: ["get", "list"]

  # Batch (areas 15–16)
  - apiGroups: ["batch"]
    resources:
      - jobs
      - cronjobs
    verbs: ["get", "list"]

  # Autoscaling (areas 11–12)
  - apiGroups: ["autoscaling"]
    resources:
      - horizontalpodautoscalers
    verbs: ["get", "list"]
  - apiGroups: ["autoscaling.k8s.io"]
    resources:
      - verticalpodautoscalers
    verbs: ["get", "list"]

  # Policy (area 14)
  - apiGroups: ["policy"]
    resources:
      - poddisruptionbudgets
    verbs: ["get", "list"]

  # Networking (areas 8–10, 25, 26)
  - apiGroups: ["networking.k8s.io"]
    resources:
      - ingresses
      - ingressclasses
      - networkpolicies
    verbs: ["get", "list"]
  - apiGroups: ["discovery.k8s.io"]
    resources:
      - endpointslices
    verbs: ["get", "list"]
  - apiGroups: ["gateway.networking.k8s.io"]
    resources:
      - gatewayclasses
      - gateways
      - httproutes
      - grpcroutes
      - tcproutes
      - tlsroutes
    verbs: ["get", "list"]

  # Storage (areas 20, 45)
  - apiGroups: ["storage.k8s.io"]
    resources:
      - storageclasses
      - csinodes
      - csidrivers
      - volumeattachments
    verbs: ["get", "list"]
  - apiGroups: ["snapshot.storage.k8s.io"]
    resources:
      - volumesnapshots
      - volumesnapshotclasses
      - volumesnapshotcontents
    verbs: ["get", "list"]

  # RBAC (area 22)
  - apiGroups: ["rbac.authorization.k8s.io"]
    resources:
      - clusterroles
      - clusterrolebindings
      - roles
      - rolebindings
    verbs: ["get", "list"]

  # Admission webhooks (area 24)
  - apiGroups: ["admissionregistration.k8s.io"]
    resources:
      - validatingwebhookconfigurations
      - mutatingwebhookconfigurations
    verbs: ["get", "list"]

  # Scheduling (areas 44, plus PriorityClasses for Sc10)
  - apiGroups: ["scheduling.k8s.io"]
    resources:
      - priorityclasses
    verbs: ["get", "list"]

  # RuntimeClasses (area 44) + FlowSchemas (U5 deprecated-API probe)
  - apiGroups: ["node.k8s.io"]
    resources:
      - runtimeclasses
    verbs: ["get", "list"]
  - apiGroups: ["flowcontrol.apiserver.k8s.io"]
    resources:
      - flowschemas
      - prioritylevelconfigurations
    verbs: ["get", "list"]

  # CRDs — enumerate installed (area 23)
  - apiGroups: ["apiextensions.k8s.io"]
    resources:
      - customresourcedefinitions
    verbs: ["get", "list"]

  # Karpenter (area 28)
  - apiGroups: ["karpenter.sh"]
    resources:
      - nodepools
      - nodeclaims
    verbs: ["get", "list"]
  - apiGroups: ["karpenter.k8s.aws"]
    resources:
      - ec2nodeclasses
    verbs: ["get", "list"]

  # Cluster Autoscaler (area 27) — config lives in a Deployment; covered above

  # Pod Security (area 34) — labels on namespaces; covered by namespace get/list

  # KEDA (area 13)
  - apiGroups: ["keda.sh"]
    resources:
      - scaledobjects
      - triggerauthentications
    verbs: ["get", "list"]

  # Kueue (conditional)
  - apiGroups: ["kueue.x-k8s.io"]
    resources:
      - clusterqueues
      - localqueues
      - workloads
    verbs: ["get", "list"]

  # GitOps — Argo CD (conditional)
  - apiGroups: ["argoproj.io"]
    resources:
      - applications
      - applicationsets
    verbs: ["get", "list"]

  # GitOps — Flux (conditional)
  - apiGroups: ["source.toolkit.fluxcd.io"]
    resources:
      - gitrepositories
      - helmrepositories
    verbs: ["get", "list"]
  - apiGroups: ["kustomize.toolkit.fluxcd.io"]
    resources:
      - kustomizations
    verbs: ["get", "list"]
  - apiGroups: ["helm.toolkit.fluxcd.io"]
    resources:
      - helmreleases
    verbs: ["get", "list"]

  # Metrics API (area 47 — kubectl top)
  - apiGroups: ["metrics.k8s.io"]
    resources:
      - nodes
      - pods
    verbs: ["get", "list"]

  # Node feature — server version, cluster-info
  - nonResourceURLs: ["/version", "/healthz", "/metrics"]
    verbs: ["get"]
```

## What this role does NOT grant

| Verb/Resource | Why excluded |
|---------------|-------------|
| `pods/exec` | Not needed — the skill never executes commands inside containers |
| `pods/attach` | Not needed |
| `pods/portforward` | Not needed |
| `secrets` (`.data` field) | The skill reads Secret metadata (count, type, age) via `get`/`list` but MUST NOT output `.data` values. The RBAC `get` on secrets is required to count them; the skill's instructions prohibit echoing values. |
| `impersonate` | Not needed |
| `bind` / `escalate` | Not needed |
| Any `create/update/patch/delete` | Prohibited by the read-only contract |

## AWS IAM — minimum permissions

For the AWS-API checks (AX1–AX14) and CloudWatch (CP1–CP11, metrics-thresholds):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EKSReadOnly",
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:ListInsights",
        "eks:DescribeInsight",
        "eks:ListAccessEntries",
        "eks:DescribeAccessEntry",
        "eks:ListAssociatedAccessPolicies",
        "eks:ListNodegroups",
        "eks:DescribeNodegroup",
        "eks:ListAddons",
        "eks:DescribeAddon",
        "eks:ListPodIdentityAssociations",
        "eks:DescribePodIdentityAssociation",
        "eks:ListUpdates",
        "eks:DescribeUpdate"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EC2ReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeSubnets",
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeImages"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAMReadOnly",
      "Effect": "Allow",
      "Action": [
        "iam:ListAttachedRolePolicies",
        "iam:GetRolePolicy",
        "iam:SimulatePrincipalPolicy"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchReadOnly",
      "Effect": "Allow",
      "Action": [
        "logs:StartQuery",
        "logs:GetQueryResults",
        "logs:StopQuery",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "cloudwatch:DescribeAlarms"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudTrailReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AutoScalingReadOnly",
      "Effect": "Allow",
      "Action": [
        "autoscaling:DescribeAutoScalingGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EFSReadOnly",
      "Effect": "Allow",
      "Action": [
        "elasticfilesystem:DescribeMountTargets",
        "elasticfilesystem:DescribeMountTargetSecurityGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SecurityServicesReadOnly",
      "Effect": "Allow",
      "Action": [
        "securityhub:GetFindings",
        "securityhub:BatchGetStandardsControlAssociations",
        "guardduty:ListDetectors",
        "guardduty:ListFindings",
        "guardduty:GetFindings",
        "inspector2:ListFindings"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ServiceQuotasReadOnly",
      "Effect": "Allow",
      "Action": [
        "servicequotas:GetServiceQuota",
        "servicequotas:ListServiceQuotas"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Note:** `AmazonAIOpsAssistantPolicy` (the AWS-managed policy for DevOps Agent) covers most of
> these. The IAM policy above is the minimum if you need a custom, least-privilege policy. The
> Security Services (`SecurityServicesReadOnly`) and Service Quotas (`ServiceQuotasReadOnly`)
> statements are **optional** — if not granted, the corresponding checks (S37–S39, U22–U24) are
> graded N/A with the reason "IAM permission not available." The review proceeds normally without
> them; they enhance coverage but are not prerequisites.

## Cross-account and scope restrictions

- The access entry is cluster-scoped (covers all namespaces) unless intentionally restricted.
- The IAM role should be scoped to the specific account. Do not use a cross-account role that
  grants access to multiple unrelated accounts — this risks cross-account evidence contamination.
- If the review is namespace-scoped, the ClusterRole above can be replaced with a namespaced
  Role (but you lose cluster-scoped checks like node conditions, CRD count, RBAC audit).
