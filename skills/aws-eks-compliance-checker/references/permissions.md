# Permissions

Load in Step 2 only when a Kubernetes or AWS read is denied.

## Kubernetes

`use_kubectl` reaches the cluster through an EKS access entry for the Agent Space's primary cloud source IAM role. See [AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html).

1. The cluster's authentication mode must include the EKS API.
2. Create an access entry with the Agent Space role ARN as principal.
3. Attach `AmazonEKSAdminViewPolicy` with access scope **Cluster**.

`AmazonEKSAdminViewPolicy` lets the agent read RBAC objects, NetworkPolicies, and every namespace, which the Section 4 controls need. It also allows reading Secrets; this skill never reads Secret objects. With the narrower `AmazonAIOpsAssistantPolicy`, controls whose reads are denied become `Not assessed`.

## AWS

Every AWS read in this skill is `Describe*`, `List*`, or `Get*` on EKS, EC2, Elastic Load Balancing, IAM, Amazon Inspector, Amazon GuardDuty, AWS CloudTrail, CloudWatch Logs, and AWS Backup. The `AIDevOpsAgentAccessPolicy` managed policy grants all of them. If a read is denied, an SCP or permissions boundary is restricting the role. Report the denied action and mark dependent checks `Not assessed`.
