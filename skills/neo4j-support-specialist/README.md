# Neo4j Support Specialist Skill

This skill lets AWS DevOps Agent diagnose self-managed Neo4j 2026.x on Amazon EKS, Amazon ECS or Amazon EC2 from the evidence the agent can already read, using runbooks built from the issues that most often reach Neo4j Support and checked against Neo4j 2026.10.1.

## Purpose

Neo4j problems on AWS usually show up first as platform symptoms: a pod in CrashLoopBackOff, an ECS task stopped with
exit 137, a disk alarm, driver errors in an application. The cause is often a single Neo4j log line, setting or
orchestrator field, and it takes Neo4j experience to know which one. The skill maps symptoms and exact 2026.x error
texts to runbooks, tells the agent which evidence confirms or rules out each cause, and reports what the agent
couldn't see along with the command the operator should run to check it.

The skill only reads. It never changes Neo4j, its configuration, the workload or AWS resources, and you don't have to
change anything in Neo4j before using it. With the optional Neo4j connector connected, it also checks the live
database through a fixed list of read-only queries.

## Key Capabilities

- Diagnoses startup failures and restart loops from container output and exit codes: store lock, unknown settings,
  volume permissions, file-descriptor limits, SSL policy paths and APOC version mismatch
- Distinguishes a container memory kill (`OOMKilled`, nothing logged) from a heap `OutOfMemoryError` (container still
  running, probes still passing), and compares heap and page cache with the container limit
- Detects full volumes, slow EBS storage, shutdowns cut short by the stop timeout, and cluster members that never form
  a cluster
- Analyzes query.log, debug.log and security.log when the deployment already ships them, with CloudWatch Logs Insights
  queries for both the JSON and text layouts
- Checks connectivity configuration: advertised addresses, URI scheme and TLS, NLB idle timeouts, security groups and
  an exposed backup port
- Translates settings, commands and procedures from 3.x, 4.x and 5.x to their 2026.x names
- With the Neo4j connector, reads running transactions, settings changed at runtime, effective memory and timeout
  settings, indexes that aren't online, constraints and the APOC version
- Lists the evidence it couldn't read and gives the operator the exact Cypher, `neo4j-admin`, `kubectl` or SSM command
  for each check it can't run
- Prepares what to send Neo4j Support when a case is likely

## Prerequisites

- An AWS DevOps Agent Space associated with the AWS account that runs Neo4j.
- EKS: an EKS access entry for the Agent Space role with the `AmazonAIOpsAssistantPolicy` access policy
  ([AWS EKS access setup](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-aws-eks-access-setup.html)).
  At cluster scope the agent can read PVs, StorageClasses and nodes. Namespace scope works, but the agent skips the
  volume and node checks.
- ECS: a log driver on the Neo4j container (`awslogs` or FireLens), so container output reaches CloudWatch Logs.
- EC2: the CloudWatch agent shipping the Neo4j journal and `/var/log/neo4j/*.log`, which gives the agent Neo4j's own
  logs. Without it the agent reads instance state, metrics and serial console output, plus the output of SSM commands
  an operator already ran.
- IAM: `AIDevOpsAgentAccessPolicy` covers every API the skill uses except `ec2:GetConsoleOutput`, which only Neo4j on
  EC2 needs. Add it to the Agent Space's IAM role as an inline policy.
- Optional: Container Insights on the EKS or ECS cluster for memory and restart trends.
- Optional: the Neo4j connector, registered as `neo4j`, for live database checks. It needs Enterprise Edition, APOC on
  the server and a Neo4j user that holds only the `devops_agent_diag` role, which can list transactions, settings,
  indexes and constraints but can't see graph data.

## Limitations

- Without the Neo4j connector the agent has no database access: it can't run Cypher or `neo4j-admin`, so it can't
  read running transactions, runtime settings or index state. Reports give the operator the commands instead.
- With the connector, the agent runs only the queries in `references/live-database.md`. It still can't read database
  status, cluster members, JMX or the `system` database. The connector also fails while the `neo4j` database is
  stopped, and the agent then works from logs.
- Default logging hides some failures. The Neo4j Docker image and Helm chart write only neo4j.log to container output.
  An offline database, a lagging secondary, slow queries and transaction memory errors appear only in debug.log,
  query.log or client logs, and the agent can use those only if the deployment already ships them.
- A passing probe doesn't mean Neo4j is healthy. The Helm chart's TCP probes pass while a database is offline or the
  JVM is hung after a heap `OutOfMemoryError`.
- The agent doesn't read Kubernetes Secrets or Secrets Manager values, so it can see where certificates and credentials
  are mounted but not their contents.
- An investigation can end with a mitigation plan from DevOps Agent's own mitigation step, with or without this skill.
  Those plans can contain write commands such as `aws ec2 create-snapshot` or `aws ssm send-command`, so check them
  against the runbook before running them.
- Community Edition writes no query.log or security.log, and has no clustering, roles, LDAP, SSO or online backup. The
  runbook issues for those don't apply there, and failing or slow queries show only in client logs.
- The skill covers Neo4j 2026.x. It doesn't cover Aura, Bloom, GDS, GraphQL, Kafka, NOM, Desktop, Cypher modeling
  questions or Neo4j 4.x.

## Agent Types

This skill is used by the following agent types:

- Chat tasks: questions and diagnosis requests about a Neo4j deployment
- Incident Triage: recognizing a Neo4j failure from an alarm or webhook
- Incident RCA: root cause analysis of Neo4j incidents

A custom agent loads the skill by ID through `list_skills_metadata`, so it works with these agent types and doesn't
need the skill imported as Generic.

## Uploading to AWS DevOps Agent

You can add the skill to an Agent Space in three ways.

### Option A: Import from GitHub (recommended)

If your Agent Space has a [GitHub connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html),
import the skill straight from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from
repository, and point it at the `skills/neo4j-support-specialist` directory. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

### Option B: Upload as a zip file

1. Zip the `neo4j-support-specialist/` directory with only the allowed extensions:

   ```bash
   cd skills
   zip -r neo4j-support-specialist.zip neo4j-support-specialist/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, open the **Skills** page.
3. Choose **Add skill** → **Upload skill**.
4. Drop `neo4j-support-specialist.zip`.
5. Select the agent types **Chat tasks**, **Incident Triage** and **Incident RCA**.
6. Choose **Upload**.

### Option C: Upload via the Asset API

Use the AWS DevOps Agent Asset API and assign the skill to the `CHAT`, `INCIDENT_TRIAGE` and `INCIDENT_RCA` agent types.
See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

Name the deployment in the prompt (EKS cluster and namespace, ECS cluster and service, or EC2 instances) so the agent
doesn't have to guess.

### Chat

- "The Neo4j pod neo4j-0 in namespace graph on EKS cluster prod-eks keeps restarting. Why?"
- "Our Neo4j ECS service graph-db in cluster data-prod had a task stop with exit code 137 an hour ago. What happened?"
- "Check whether the memory settings of the Neo4j StatefulSet in namespace graph fit its container limit."
- "Applications get ServiceUnavailable connecting to Neo4j behind the NLB in front of namespace graph. What's wrong?"
- "What should we send Neo4j Support about last night's Neo4j outage on ECS service graph-db?"

### Investigation

- "Investigate the alarm: Neo4j pod restarts in namespace graph on cluster prod-eks."
- "Disk usage alarm on the Neo4j data volume for ECS service graph-db."
- "The Neo4j cluster in namespace graph didn't come back after the node group upgrade."

## Related

- The `aws-eks-operations-review` and `ecs-operation-review` skills cover platform reviews when the problem isn't
  specific to Neo4j.
