# Serverless Operational Review (AWS DevOps Agent Skill)

> ⚠️ **Non-Production Notice**: This skill is sample code, not intended for production use without additional review and testing. Validate in a non-production environment first, and review the IAM permissions below against your organization's policies before granting them.

## What It Does

Teaches the DevOps Agent to run a structured operational review of an AWS serverless workload, aligned with the AWS Well-Architected Framework and its [Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html), the [Lambda best practices guide](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html), and the [CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html) reference.

The review covers five resource families:

| Family | Resources |
|---|---|
| Compute | Lambda functions, versions, aliases, function URLs |
| Event sources | SQS, SNS, EventBridge, EventBridge Scheduler, DynamoDB Streams, Kinesis |
| API | API Gateway REST, HTTP, and WebSocket APIs and stages |
| Orchestration | Step Functions state machines |
| Data | DynamoDB tables and global secondary indexes |

It produces a shareable markdown report with findings grouped by Well-Architected pillar, each carrying a severity, the observed value as evidence, a remediation snippet, and its AWS documentation citation.

## Key Capabilities

- **Finds silent failure modes.** Asynchronous events dropped with no dead-letter queue or `OnFailure` destination, SQS visibility timeouts below the consuming function's timeout (which causes duplicate processing), poison-pill records blocking a stream shard, and stream `IteratorAge` approaching the retention window.
- **Quantifies headroom.** `Duration` p99 against the configured timeout, account concurrency against the Region quota, memory utilization from `Max Memory Used`, and DynamoDB capacity against the documented 80% threshold.
- **Turns alarm gaps into a plan.** Every missing alarm is reported with the recommended statistic, threshold, period and datapoints, plus a ready-to-run `put-metric-alarm` command.
- **Checks runtime currency against verified dates,** including which runtimes sit on Amazon Linux 2 after its end of life.
- **Reviews the invocation path, not just the function.** API Gateway stage settings, Step Functions retry, catch and timeout coverage in the state machine definition, and DynamoDB backup and capacity posture.
- **Quantifies cost waste.** Never-expire log retention, x86 functions on Graviton-eligible runtimes, over-provisioned memory, idle provisioned concurrency, and unused functions and indexes.
- **Read-only and evidence-based.** Every finding names the value it is based on and carries a check id. Environment variables are reported by key name only, never by value.

## Prerequisites

- AWS DevOps Agent with an active Agent Space.

**If your Agent Space uses the default role, no extra permissions are needed.** The AWS managed policy [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html) already grants every action the skill uses, including the IAM read actions and `ce:GetCostAndUsage`.

Two checks can be denied under that policy, and the skill reports the gap in its Scope Covered section rather than failing: `apigateway:GET` is scoped to resource paths that exclude usage plans and authorizers.

**If your Agent Space uses a custom, narrower role**, grant it the actions listed below.

A denied call is not always a permissions problem. An Agent Space can return `NO_ELEVATED_ROLE_FOR_ACCOUNT` on a call the role is allowed to make. That is a platform restriction, not an IAM gap, and the skill distinguishes the two.

### IAM permissions

Lambda and event sources:

```
lambda:ListFunctions              lambda:GetFunction
lambda:GetFunctionConfiguration   lambda:GetFunctionConcurrency
lambda:GetFunctionEventInvokeConfig
lambda:GetFunctionUrlConfig       lambda:ListFunctionUrlConfigs
lambda:ListEventSourceMappings    lambda:ListProvisionedConcurrencyConfigs
lambda:ListAliases                lambda:ListVersionsByFunction
lambda:GetPolicy                  lambda:ListTags
lambda:GetAccountSettings         lambda:GetCodeSigningConfig
sqs:GetQueueAttributes            sqs:ListQueues
sns:GetTopicAttributes            sns:ListSubscriptionsByTopic
sns:GetSubscriptionAttributes
events:ListRules                  events:ListRuleNamesByTarget
events:ListTargetsByRule          events:DescribeRule
scheduler:ListSchedules           scheduler:GetSchedule
kinesis:DescribeStreamSummary     kinesis:ListStreams
```

API Gateway, Step Functions, DynamoDB:

```
apigateway:GET
states:ListStateMachines          states:DescribeStateMachine
states:ListExecutions
dynamodb:ListTables               dynamodb:DescribeTable
dynamodb:DescribeContinuousBackups
dynamodb:DescribeTimeToLive       dynamodb:ListTagsOfResource
application-autoscaling:DescribeScalableTargets
wafv2:GetWebACLForResource
```

Observability, IAM inspection, quotas, and cost:

```
cloudwatch:GetMetricData          cloudwatch:GetMetricStatistics
cloudwatch:ListMetrics            cloudwatch:DescribeAlarms
cloudwatch:DescribeAlarmsForMetric
logs:DescribeLogGroups            logs:FilterLogEvents
logs:GetLogEvents
iam:GetRole                       iam:ListAttachedRolePolicies
iam:ListRolePolicies              iam:GetRolePolicy
iam:GetPolicy                     iam:GetPolicyVersion
servicequotas:GetServiceQuota     servicequotas:ListServiceQuotas
ce:GetCostAndUsage
```

Every action is read-only. The skill never calls a mutating API.

## Limitations

**Ask for a review, not a single question.** Prompts containing "review", "audit", "assess", or "how healthy is" activate the skill. The agent already answers narrow questions like "are any runtimes deprecated?" well without it, so the skill adds least value there and most when you want the whole picture.

**A review costs more than a question.** Expect roughly two to three times the runtime and spend of asking the agent directly, because the skill collects configuration, metrics, logs, alarms, IAM and cost data before reporting. Scope it to the resources you care about, and let the budget caps apply on wide scopes.

**Configuration and telemetry only.** The skill cannot read function code, so it cannot verify idempotency, input validation, or error handling. Those appear as advisory findings naming what a human must confirm.

**Cost figures are estimates.** Cost Explorer does not break Lambda spend down per function, so per-resource costs are a proportional split and are labelled (estimated).

**Log analysis is sampled.** REPORT-line extraction uses 200 to 500 lines across the window. Enough to size memory, not an exhaustive scan.

**A 7-day window can miss** monthly batch jobs, seasonal peaks, and rare failures. Ask for a wider window when the workload is periodic.

**Runtime deprecation dates change.** The reference table is verified as of 2026-09-10. AWS states these forecast dates are subject to change, so re-check before acting on a date.

**No remediation.** The skill reports findings and provides the commands to fix them. It never changes a resource.

**Security-scoped prompts can be cut short.** A review scoped only to IAM or security posture is sometimes blocked by the hosted agent's content safety filter, which ends the response and loses the report. Run a general review instead: it includes the same security findings.

## Agent Types

| Agent type | Use |
|---|---|
| Chat tasks | on-demand review, targeted or account-wide |
| Evaluation | scheduled or repeated posture assessment |

Also usable from a custom agent. See `custom-agents/serverless-operation-review/` for a scheduled weekly variant.

## Uploading to AWS DevOps Agent

```bash
cd skills
zip -r serverless-operation-review.zip serverless-operation-review/ \
  -x '*/evals/*' '*/README.md' '*/CHANGELOG.md' '*/.skilleval.yaml' '*/eval_results.json'
```

Then in the AWS Console:

1. Open your DevOps Agent Agent Space and go to **Skills**.
2. Upload `serverless-operation-review.zip`.
3. Select the agent types: **Chat tasks** and **Evaluation**.
4. Confirm the Agent Space role has the permissions listed above.

## How to Use This Skill

### Chat tasks

```
"Run a serverless operational review for us-east-1"
"Review the checkout-processor Lambda function"
"How healthy is my serverless workload?"
"Audit my Lambda functions against serverless best practices"
"Review everything tagged Application=checkout"
"Are any of my Lambda functions on deprecated runtimes?"
"Review my API Gateway APIs and Step Functions state machines in eu-west-1"
```

### Diagnostic prompts that also activate it

```
"Why are my SQS messages being processed twice?"
"My Lambda function keeps timing out, what should I check?"
"Where are my asynchronous Lambda events going?"
"My DynamoDB stream consumer is falling behind"
"Why am I seeing Lambda throttling?"
"Where is my serverless cost going?"
```

### Evaluation

```
"Assess serverless operational readiness for the payments workload"
"Produce a serverless posture report for this account"
```

## Version History

See [CHANGELOG.md](CHANGELOG.md).
