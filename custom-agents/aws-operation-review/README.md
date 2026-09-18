# AWS Operation Review — Custom Agent

## Purpose

This custom agent performs comprehensive operational reviews of AWS services (EKS clusters, RDS instances, Aurora clusters, Amazon SageMaker AI workloads) against best practices and the Well-Architected Framework. It identifies gaps in security, reliability, performance, cost optimization, and operational excellence, producing actionable recommendations and a structured report artifact.

## Key Capabilities

- Assesses EKS clusters for version currency, security posture, networking, logging, and node group configuration
- Evaluates RDS/Aurora instances for engine versions, backup configuration, encryption, Multi-AZ, parameter compliance, and cost optimization
- Reviews Amazon SageMaker AI workloads across eight pillars and twenty checks — endpoint encryption and VPC isolation, Studio domain network posture, endpoint autoscaling and staleness, service quota headroom, AWS Health lifecycle events, data capture, and Well-Architected guidance
- Assigns severity levels (critical, high, medium, low) based on security exposure, blast radius, and operational risk
- Generates a prioritized report with remediation steps and effort/impact estimates
- Produces a persisted Markdown artifact for sharing with stakeholders

## Prerequisites

- An AWS DevOps Agent space
- IAM permissions for EKS read APIs (`eks:DescribeCluster`, `eks:ListClusters`, `eks:ListNodegroups`, `eks:DescribeNodegroup`, `eks:ListAddons`, `eks:DescribeAddon`) and/or RDS read APIs (`rds:DescribeDBInstances`, `rds:DescribeDBClusters`, `rds:DescribeDBParameterGroups`, `rds:ListTagsForResource`). For SageMaker AI reviews, the managed `AIDevOpsAgentAccessPolicy` already covers every API the skill calls except `savingsplans:DescribeSavingsPlans`, which is an optional add-on — see the [sagemaker-ops-review prerequisites](../../skills/sagemaker-ops-review/README.md#2-iam-permissions)
- The [eks-operation-review skill](../../skills/eks-operation-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even that the skill's README file instructs to choose specific agent types
- The [rds-operation-review skill](../../skills/rds-operation-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even that the skill's README file instructs to choose specific agent types
- For SageMaker AI reviews, the [sagemaker-ops-review skill](../../skills/sagemaker-ops-review/) uploaded to your Agent Space with "All agents" selected in the "Agent Type" field

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" menu (on the bottom left pane)
2. Click "Create agent" (on the right side), then on the new menu that popped up, click "Form" (the left-most option)
3. In the "Name" field, use "aws-operation-review"
4. Copy the content of the "SYSTEM_PROMPT.md" file from this directory, and paste it into the "System prompt" field in the custom agent creation form
5. In the "Skills" drop-down list, select the skills for the services you want to review — "eks-operation-review", "rds-operation-review", and/or "sagemaker-ops-review" — and click "Create agent"
6. Now we need to add the `use_aws` and `use_kubectl` tools - in the new custom agent's window, click "Edit"
7. In the new popped up window, select "Chat". A new chat will start on the left side. Wait for DevOps Agent to finish thinking, and it'll ask you what would you like to change
8. Type "Add the use_aws and use_kubectl tools to this custom agent". Once the chat is finished, verify in the custom agent's page that both `use_aws` and `use_kubectl` are shown under "Tools" for this custom agent

## Executing the Agent

You can execute the custom agent on-demand from the custom agent page, on schedule, or using chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also run it using custom prompt (for example, ask it to review a specific cluster by name or focus only on security findings).  
Once finished, the artifact is persisted on the **Artifacts** page in the DevOps Agent web app.

## Related

- [eks-operation-review skill](../../skills/eks-operation-review/) — domain knowledge for EKS cluster assessments
- [rds-operation-review skill](../../skills/rds-operation-review/) — domain knowledge for RDS/Aurora database assessments
- [sagemaker-ops-review skill](../../skills/sagemaker-ops-review/) — domain knowledge for Amazon SageMaker AI operational reviews
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
