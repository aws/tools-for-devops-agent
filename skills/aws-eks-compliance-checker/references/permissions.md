# Permissions

Load in Step 2 when a Kubernetes or AWS read is denied, or when the user asks how to grant access.

## Kubernetes

`use_kubectl` reaches the cluster through an EKS access entry for the Agent Space's primary cloud source IAM role. See [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html). The cluster's authentication mode must include the EKS API. Choose one of these options.

### Option 1 (recommended): read-only ClusterRole without Secrets

Create this ClusterRole and Role, then create the access entry with Kubernetes group `devops-agent-cis-readers` and no access policy. It allows every read in the "Evidence collection" table of `cis-eks-controls.md` and denies Secrets, other ConfigMaps, and pod logs.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: devops-agent-cis-reader
rules:
  - apiGroups: [""]
    resources: [namespaces, pods, serviceaccounts]
    verbs: [get, list]
  - apiGroups: [rbac.authorization.k8s.io]
    resources: [clusterroles, clusterrolebindings, roles, rolebindings]
    verbs: [get, list]
  - apiGroups: [networking.k8s.io]
    resources: [networkpolicies]
    verbs: [get, list]
  - apiGroups: [apps]
    resources: [daemonsets, deployments, statefulsets]
    verbs: [get, list]
  - apiGroups: [apiextensions.k8s.io]
    resources: [customresourcedefinitions]
    verbs: [get, list]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: devops-agent-cis-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: devops-agent-cis-reader
subjects:
  - kind: Group
    name: devops-agent-cis-readers
    apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: devops-agent-cis-aws-auth-reader
  namespace: kube-system
rules:
  - apiGroups: [""]
    resources: [configmaps]
    resourceNames: [aws-auth]
    verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: devops-agent-cis-aws-auth-reader
  namespace: kube-system
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: devops-agent-cis-aws-auth-reader
subjects:
  - kind: Group
    name: devops-agent-cis-readers
    apiGroup: rbac.authorization.k8s.io
```

```bash
aws eks create-access-entry --cluster-name <cluster> \
  --principal-arn <agent-space-role-arn> --kubernetes-groups devops-agent-cis-readers
```

Pod specs can still hold plain-text environment variable values, and the `aws-auth` ConfigMap lists IAM role and user ARNs. Both are read.

### Option 2: `AmazonEKSAdminViewPolicy`

Associate `AmazonEKSAdminViewPolicy` at access scope **Cluster**. It covers every read, but it also grants `get`, `list`, and `watch` on all resources, Secrets included. The skill avoids Secret values by instruction, not by permission.

### Option 3: `AmazonAIOpsAssistantPolicy` (DevOps Agent default)

This policy allows pods, namespaces, nodes, workloads, ConfigMaps, and pod logs, and denies Secrets. It also denies these evidence reads, so the controls that need them are `Not assessed`:

| Denied read | Controls affected |
|---|---|
| K1–K4 (ClusterRoleBindings, RoleBindings, ClusterRoles, Roles) | 4.1.1, 4.1.2, 4.1.3, 4.1.4, 4.1.8–4.1.12; 4.5.1 loses the RoleBinding count |
| K5 (ServiceAccounts) | 4.1.5, 4.1.6, 5.2.1 |
| K8 (NetworkPolicies) | 4.3.2, and 5.4.4 unless 4.3.1 fails |
| K13 (CustomResourceDefinitions) | 4.4.2 when K12 finds no Secrets Store CSI volume |

### For all options

Grant the extra access for the assessment only and remove it afterwards. An access entry can carry both Kubernetes groups and access policies, so if the Agent Space role already has an entry with `AmazonAIOpsAssistantPolicy`, add the group to it instead of creating a second entry:

```bash
aws eks update-access-entry --cluster-name <cluster> \
  --principal-arn <agent-space-role-arn> --kubernetes-groups devops-agent-cis-readers
# After the assessment:
aws eks update-access-entry --cluster-name <cluster> \
  --principal-arn <agent-space-role-arn> --kubernetes-groups '[]'
```

## AWS

Every AWS read in this skill is `Describe*`, `List*`, or `Get*` on EKS, EC2, Elastic Load Balancing, IAM, Amazon Inspector, Amazon GuardDuty, AWS CloudTrail, CloudWatch Logs, and AWS Backup. The `AIDevOpsAgentAccessPolicy` managed policy grants all of them. If a read is denied, an SCP or permissions boundary is restricting the role. Report the denied action and mark dependent checks `Not assessed`.
