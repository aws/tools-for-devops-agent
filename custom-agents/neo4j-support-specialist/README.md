# Neo4j Support Specialist - Custom Agent

**Version: 1.0.0** (see [`CHANGELOG.md`](https://github.com/aws/tools-for-devops-agent/blob/main/custom-agents/neo4j-support-specialist/CHANGELOG.md)) | Requires skill version 1.0.0+ (see [`skills/neo4j-support-specialist/`](https://github.com/aws/tools-for-devops-agent/tree/main/skills/neo4j-support-specialist))

## Purpose

This custom agent runs the [`neo4j-support-specialist`](https://github.com/aws/tools-for-devops-agent/tree/main/skills/neo4j-support-specialist)
skill on its own against one self-managed Neo4j Enterprise 2026.x deployment on Amazon EKS, Amazon ECS or Amazon EC2.
An alarm or webhook starts an incident diagnosis, and a schedule starts a health check. Each run publishes one report
artifact with quoted evidence, the commands an operator needs for anything the agent couldn't check, and what to send
Neo4j Support.

## Key Capabilities

- Diagnoses startup failures, restart loops, memory kills, heap exhaustion, full volumes, unclean shutdowns, cluster
  formation failures and plugin mismatches from container output, orchestrator state and configuration
- Uses debug.log, query.log, security.log and application logs when the deployment ships them, and lists them as gaps
  when it doesn't
- On a schedule, checks memory headroom, a missing `-XX:+ExitOnOutOfMemoryError`, stop timeouts, file limits, an
  exposed backup port, the APOC version, volume fill, EBS saturation, and whether every cluster member started
- Gives the operator the exact Cypher, `neo4j-admin`, `kubectl` and SSM commands for checks that need database or host
  access

## Important behavior notes

**Scope comes from the prompt, the trigger or the defaults.** The system prompt has a "Default scope" block with
placeholders in angle brackets; replace them with your deployment before saving. An invocation prompt or webhook
payload that names a deployment overrides the defaults, and so does a CloudWatch alarm whose dimensions identify one.
Custom agents can't ask questions mid-run. When no deployment is named, the agent looks for Neo4j deployments in one
Region (EKS Helm releases, ECS services, EC2 instances with `neo4j` in the Name tag) and checks a few of them, starting
with any that show trouble. In testing it didn't always keep to one Region or five targets, so name the deployment or
fill in the Default scope when you want a predictable run. For an interactive session, use the skill from DevOps Agent
chat.

**Read only, with no database access.** The agent runs `use_kubectl` with read verbs only, read-only AWS APIs and
CloudWatch Logs queries. It never connects to Neo4j, never runs SSM commands and never reads Secret values.

**Default Neo4j logging limits what it can see.** The Neo4j Docker image and Helm chart write only neo4j.log to
container output. An offline database, replication lag and slow queries show up only in debug.log or query.log. If
your deployment doesn't ship those files to CloudWatch Logs, the report lists them under "Evidence not available" with
the command to check by hand.

**Results arrive as an artifact.** A run started from chat returns a task ID, not the report. Read the report on the
**Artifacts** page, or in the task's journal.

## Prerequisites

- An AWS DevOps Agent Space associated with the account that runs Neo4j
- The [neo4j-support-specialist skill](../../skills/neo4j-support-specialist/) uploaded to the Agent Space. The agent
  loads it by ID through `list_skills_metadata`, which in testing worked with the skill's own agent types (Chat,
  Incident Triage, Incident RCA), so you don't need to import it as Generic
- EKS: an EKS access entry for the Agent Space's primary cloud source IAM role with the `AmazonAIOpsAssistantPolicy`
  access policy, at cluster scope if possible
  ([AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html)).
  Namespace scope works, but the agent then can't read PVs, StorageClasses or nodes
- ECS: a log driver (`awslogs` or FireLens) on the Neo4j container
- EC2: the CloudWatch agent shipping the Neo4j journal and `/var/log/neo4j/*.log`, and `ec2:GetConsoleOutput` on the
  agent role (`EnableNeo4jSupportSpecialist` in the
  [skill policies template](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)).
  `AIDevOpsAgentAccessPolicy` covers every other API the agent calls
- Optional: Container Insights for memory and restart trends, and debug.log, query.log and security.log in CloudWatch
  Logs for findings about database state

## Creating the Agent

1. In the DevOps Agent web app, go to the **Agents** page.
2. In the **Custom Agents** section, choose **Create agent**, then **Form**.
3. Fill out the form:
   - **Name:** `neo4j-support-specialist`
   - **System prompt:** paste `SYSTEM_PROMPT.md` from this directory and replace the placeholders in "Default scope"
     (platform, target, region, optional log groups). If you'd rather name the deployment in each invocation prompt,
     import the prompt from this file on GitHub and leave the defaults alone
   - **Skills:** select `neo4j-support-specialist`
4. Choose **Create agent**.
5. Assign the tools through Chat, because the Form can't assign them.

### Skills to add

| Skill | Why it's needed |
| ------- | ----------------- |
| `neo4j-support-specialist` | The A1 to A12 runbooks, evidence sources, log queries, operator commands and the report template. The system prompt tells the agent not to diagnose Neo4j from memory, so it needs this skill. |

### Tools to add

On the agent's page, choose **Edit**, then **Chat**, and paste:

```text
Add the following tools to this custom agent: use_kubectl, use_aws, query_cloudwatch_logs,
lookup_cloudtrail_events, create_or_update_artifact, list_skills_metadata, get_skill_resource,
get_skill_resource_manifest
```

Afterwards, check that every tool appears under **Tools** on the agent's page.

| Tool | Used for |
| ------ | ---------- |
| `use_kubectl` | Pods, events, container output (current and `--previous`), ConfigMaps, StatefulSets, PVCs and Services on EKS |
| `use_aws` | ECS services, tasks and task definitions; EC2 instances, console output and volumes; EBS and Container Insights metrics; load balancers, security groups, ACM; SSM command output |
| `query_cloudwatch_logs` | Logs Insights over container output and any shipped Neo4j or application logs |
| `lookup_cloudtrail_events` | Changes in the window: task definitions, services, volumes, security groups |
| `create_or_update_artifact` | Publishing the report |
| `list_skills_metadata`, `get_skill_resource_manifest`, `get_skill_resource` | Finding the skill's ID, then loading the runbooks and references the evidence points to |

For ECS-only or EC2-only deployments, you can leave out `use_kubectl`.

## Executing the Agent

Run the agent on demand from its page, through chat, on a schedule or from a webhook. See
[Executing custom agents](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html).

- On demand or from chat, name the deployment and the symptom, for example "Run neo4j-support-specialist on ECS
  cluster data-prod, service graph-db, in eu-west-1: the task restarted at 02:10 UTC."
- For alarms, create an event trigger on the agent for the Agent Space webhook that receives your CloudWatch alarms,
  with a JMESPath filter that selects the Neo4j alarms
  ([Creating an event trigger](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html#creating-an-event-trigger)).
  The [alarm investigations template](https://github.com/aws/tools-for-devops-agent/tree/main/cloudformation/devops-agent-alarm-investigations)
  forwards alarms to that webhook with the alarm name and ARN. The agent finds the deployment from the alarm's
  dimensions, so alarm on metrics with `ClusterName`/`Namespace`/`PodName`, `ClusterName`/`ServiceName`, `InstanceId`
  or `VolumeId` dimensions.
- A daily schedule with the Default scope filled in produces a health check.

The report appears on the **Artifacts** page as `Neo4j diagnosis: <target>, <date>` or
`Neo4j health check: <target>, <date>`.

## Related

- [neo4j-support-specialist skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/neo4j-support-specialist)
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
