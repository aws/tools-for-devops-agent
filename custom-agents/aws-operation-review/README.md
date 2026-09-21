# AWS Operation Review — Custom Agent

## Purpose

This custom agent performs comprehensive operational reviews of AWS services (EKS clusters, RDS instances, Aurora clusters, Bedrock workloads, and Bedrock AgentCore workloads) against best practices and the Well-Architected Framework. It identifies gaps in security, reliability, performance, cost optimization, and operational excellence, producing actionable recommendations and a structured report artifact.

## Key Capabilities

- Assesses EKS clusters for version currency, security posture, networking, logging, and node group configuration
- Evaluates RDS/Aurora instances for engine versions, backup configuration, encryption, Multi-AZ, parameter compliance, and cost optimization
- Reviews Bedrock workloads across security, performance, service quotas, cost optimization, and resilience
- Reviews Bedrock AgentCore workloads (agent runtimes, gateways, memories, browsers, code interpreters, workload identities) for runtime resilience, gateway health, memory effectiveness, and operational hygiene
- Assigns severity levels (critical, high, medium, low) based on security exposure, blast radius, and operational risk
- Generates a prioritized report with remediation steps and effort/impact estimates
- Produces a persisted Markdown artifact for sharing with stakeholders

## Prerequisites

- An AWS DevOps Agent space
- IAM permissions for EKS read APIs (`eks:DescribeCluster`, `eks:ListClusters`, `eks:ListNodegroups`, `eks:DescribeNodegroup`, `eks:ListAddons`, `eks:DescribeAddon`) and/or RDS read APIs (`rds:DescribeDBInstances`, `rds:DescribeDBClusters`, `rds:DescribeDBParameterGroups`, `rds:ListTagsForResource`)
- The [eks-operation-review skill](../../skills/eks-operation-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even that the skill's README file instructs to choose specific agent types
- The [rds-operation-review skill](../../skills/rds-operation-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even that the skill's README file instructs to choose specific agent types
- The [bedrock-operation-review skill](../../skills/bedrock-operation-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even that the skill's README file instructs to choose specific agent types
- The [agentcore-ops-review skill](../../skills/agentcore-ops-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill. Also note: the standard `AIDevOpsAgentAccessPolicy` does not include the `bedrock-agentcore:` namespace — grant the read-only AgentCore permissions (or use the skill's observability-only mode) per the skill's README

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" menu (on the bottom left pane)
2. Click "Create agent" (on the right side), then on the new menu that popped up, click "Form" (the left-most option)
3. In the "Name" field, use "aws-operation-review"
4. Copy the content of the "SYSTEM_PROMPT.md" file from this directory, and paste it into the "System prompt" field in the custom agent creation form
5. In the "Skills" drop-down list, select both the "eks-operation-review", "rds-operation-review", "bedrock-operation-review", and "agentcore-ops-review" skills, and click "Create agent"
6. Now we need to add the `use_aws` and `use_kubectl` tools - in the new custom agent's window, click "Edit"
7. In the new popped up window, select "Chat". A new chat will start on the left side. Wait for DevOps Agent to finish thinking, and it'll ask you what would you like to change
8. Type "Add the use_aws and use_kubectl tools to this custom agent". Once the chat is finished, verify in the custom agent's page that both `use_aws` and `use_kubectl` are shown under "Tools" for this custom agent

## Executing the Agent

You can execute the custom agent on-demand from the custom agent page, on schedule, or using chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also run it using custom prompt (for example, ask it to review a specific cluster by name or focus only on security findings).  
Once finished, the artifact is persisted on the **Artifacts** page in the DevOps Agent web app.

## Related

- [eks-operation-review skill](../../skills/eks-operation-review/) — domain knowledge for EKS cluster assessments
- [rds-operation-review skill](../../skills/rds-operation-review/) — domain knowledge for RDS/Aurora database assessments
- [bedrock-operation-review skill](../../skills/bedrock-operation-review/) — domain knowledge for Bedrock workload assessments
- [agentcore-ops-review skill](../../skills/agentcore-ops-review/) — domain knowledge for Bedrock AgentCore assessments
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
