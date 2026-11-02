# DR Starting Point Skill

A skill for AWS DevOps Agent that gives a team its first disaster recovery (DR)
readiness report for one workload, whatever its architecture. It checks every
layer of the workload read-only, says where it stands today for each failure
scenario, turns business answers into RPO and RTO targets, picks the cheapest
strategy that meets them, and proposes the first tests that prove recovery works.

## Purpose

Most teams that ask "how do we survive a Region failure?" have no RPO, no RTO and
no strategy yet. AWS Backup, Resilience Hub, AWS FIS and ARC all help, but they
assume you already know your targets. Without the skill, the agent is good at
listing configuration gaps, but it tends to:

- skip the choice of strategy, or pick one stricter (and more expensive) than the
  targets need;
- recommend expensive options without a cost warning;
- stop at "fix these settings" without a test that proves recovery works.

This skill adds the planning and the proving.

## Key capabilities

- Separates four scenarios (service failure, AZ failure, Region failure, bad data)
  and states which protection covers which.
- Separates source-of-truth data from rebuildable data (for example caches), so
  effort goes where data can actually be lost.
- Maps RPO and RTO per tier to one of the four Well-Architected strategies, and
  explains why the cheaper one is enough when it is.
- Finds the workloads in the account when none is named (CloudFormation stacks,
  myApplications, resource groups, shared tags) and asks which one to assess.
- Maps and checks every layer of the workload read-only: entry and routing
  (Route 53, CloudFront, API Gateway, load balancers), compute (EC2, Auto Scaling,
  Amazon ECS, Amazon EKS, AWS Lambda, Step Functions), data (RDS, Aurora, DynamoDB,
  ElastiCache, DocumentDB, Neptune, Redshift, OpenSearch), storage (EBS, EFS, FSx,
  S3), messaging and events (SQS, SNS, Kinesis, EventBridge), identity (Cognito)
  and shared dependencies (network, secrets, KMS keys, container images,
  certificates, IaC, service quotas). Any other service gets six generic questions.
- Starts the answer with where the workload stands today, marking each scenario
  as covered, partly covered or not covered.
- Proposes restore tests, AWS FIS failure tests and failover drills.
- Returns the full report in the chat. When asked for a report, it also saves it
  as an artifact, `dr-starting-point-<workload>-<YYYY-MM-DD>.md`, where the runtime
  supports artifacts.
- Hands off to `aws-backup-coverage-review` for account-wide backup audits,
  `storage-s3-resiliency-expertise` for S3 buckets, `service-quota-check` for quotas
  in the recovery Region and `msk-operations` for Amazon MSK.

## Prerequisites

The skill uses up to 62 read-only IAM actions. The DevOps Agent managed policy
`AIDevOpsAgentAccessPolicy` already allows 60 of them; this was checked with
`iam:SimulateCustomPolicy`. The two it does not allow, `drs:DescribeSourceServers`
and `lambda:GetFunction`, are optional: without them the skill says what it could
not read and uses `lambda:GetFunctionConfiguration` instead. To grant them, deploy
the `EnableDrStartingPoint` parameter in
[cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)
on the role of each Agent Space where the skill is installed.

## Limitations

- One workload at a time. It does not audit the whole account.
- It does not run failovers, restores or FIS experiments. It proposes them.
- It does not quote prices it has not checked. It names cost levels and known traps.
- Amazon S3 and account-wide AWS Backup coverage are handed off to other skills.

## Agent types

- **Chat tasks** (`CHAT`): conversational questions about DR for a workload.

If your Agent Space shows different agent type names, choose **All agents**.

## Uploading to AWS DevOps Agent

- **Import from GitHub:** in the Operator Web App, open **Knowledge**, then **Skills**,
  choose **Add skill**, then **Import from repository**, and point to the skill directory.
- **Upload a zip:** from the `skills/` directory, run the command below, then use
  **Upload skill**:

  ```bash
  zip -r dr-starting-point.zip dr-starting-point/ -i '*.md' -x '*/README.md' '*/CHANGELOG.md' '*/evals/*'
  ```
- **Asset API:** `aws devops-agent create-asset` with `--asset-type skill`, then
  `create-asset-file` for each file under `references/` and `assets/`.

## How to use this skill

Ask in plain words. You do not need to name the skill.

- "We run our customer portal in eu-central-1. We want disaster recovery if the
  Region fails. Where do we start?"
- "Our order data needs RPO 15 minutes and RTO 1 hour. Which DR strategy fits?"
- "Assess the DR readiness of the booking-api stack and give me a report."
- "How well would our workloads in eu-west-1 survive a disaster?" (it lists the
  workloads it finds and asks which one to assess first)
- "We run our API on ECS in us-east-1. Where do we start with disaster recovery?"

## Related skills

- `aws-backup-coverage-review` — account-wide AWS Backup coverage audit. This skill
  hands off to it instead of repeating it.
- `storage-s3-resiliency-expertise` — S3 bucket versioning, replication and Object
  Lock review.
- `service-quota-check` — quotas in the recovery Region.
- `rds-operation-review`, `ecs-operation-review`, `aws-eks-operations-review` —
  best-practices reviews of one service. Use them for a full review of that service;
  use this skill for "would the workload survive a disaster, and where do we start".

## Non-production disclaimer

This is sample content, not intended for production use without additional review
and testing. Validate it in a non-production environment first. You are responsible
for testing, securing and optimizing it for your own use.
