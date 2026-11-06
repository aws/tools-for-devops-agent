# Lambda Operational Review — AWS DevOps Agent Skill

A comprehensive AWS Lambda operational review and troubleshooting skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments and incident-style investigations aligned with the [AWS Lambda operator guide](https://docs.aws.amazon.com/lambda/latest/operatorguide/intro.html) and the [Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html). Generates a shareable report artifact per resource.

> **Disclaimer:** This skill is provided as **sample code**, not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions and findings against your organization's policies before relying on it.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover Lambda functions, their configuration, event source mappings, concurrency settings, function URLs, and execution roles in the configured account/regions.
2. Collect a 14-day CloudWatch metrics window (Errors, Throttles, Duration, InitDuration, ConcurrentExecutions, provisioned-concurrency, stream IteratorAge) and alarm coverage.
3. In incident mode, query the function's CloudWatch Logs for error, timeout, and networking signatures and correlate them with the metric window.
4. Analyze across seven dimensions: Configuration & Runtime, Reliability, Performance, Concurrency & Throttling, Security, Cost, and Observability.
5. Generate a shareable report artifact per function, named `lambda-review-<function-or-scope>-<YYYY-MM-DD>.md`.

All data is gathered through native AWS APIs (`lambda`, `cloudwatch`, `logs`, `iam`). The skill operates entirely in **read-only** mode and never invokes the function.

## Agent Types

- **On-demand** — conversational invocation in Chat ("review my Lambda functions", "why is function X throttling").
- **Evaluation** — proactive operational improvement recommendations.
- **Incident RCA** — root-cause investigation of Lambda errors, throttles, timeouts, and latency.

Select **Generic** to make it available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

The Agent Space's IAM role must have read access to Lambda, CloudWatch, CloudWatch Logs, and IAM (read-only). The AWS managed read-only policy typically covers these — verify in your account before running the review:

- `lambda:ListFunctions`, `lambda:GetFunction`, `lambda:GetFunctionConfiguration`, `lambda:GetFunctionConcurrency`, `lambda:GetAccountSettings`
- `lambda:ListProvisionedConcurrencyConfigs`, `lambda:ListEventSourceMappings`, `lambda:GetFunctionUrlConfig`, `lambda:GetPolicy`
- `lambda:ListAliases`, `lambda:ListVersionsByFunction`, `lambda:ListTags`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms`, `cloudwatch:DescribeAlarmsForMetric`
- `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:StartQuery`, `logs:GetQueryResults`
- `iam:GetRole`, `iam:GetRolePolicy`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion` (execution-role scope check)
- `xray:GetTraceSummaries`, `xray:BatchGetTraces` (optional — tracing analysis)
- `ce:GetCostAndUsage` (optional — cost analysis)
- `tag:GetResources` (optional — cross-service tag reporting)

The skill operates entirely in **read-only** mode: it never calls `UpdateFunctionConfiguration`, `UpdateFunctionCode`, `PutFunctionConcurrency`, `DeleteFunction`, `Invoke`, or any mutating API.

### 3. CloudWatch Logs (recommended for incident mode)

Log-pattern analysis (Runbooks A–F) requires the function's log group `/aws/lambda/<name>` to exist and be readable. If a function has no log group or retention is disabled, the skill reports that as a finding but cannot retrieve historical log events.

### 4. AWS X-Ray (optional)

Enabling [active tracing](https://docs.aws.amazon.com/lambda/latest/dg/services-xray.html) gives the skill segment-level latency breakdowns. Without it, latency analysis relies on the `Duration` and `InitDuration` CloudWatch metrics.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `skills/` directory in this repo:

```bash
cd skills
zip -r lambda-operational-review.zip lambda-operational-review/ -x 'lambda-operational-review/evals/*'
```

Constraints (enforced at upload time):

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

`evals/` is excluded from the upload (it's only used for offline evaluation).

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `lambda-operational-review.zip`.
4. Select agent types: **On-demand**, **Evaluation**, and **Incident RCA** (or leave **Generic**).
5. Review the validation results and click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

- *"Run a Lambda operational review for all functions in us-west-2."*
- *"Review my Lambda function `checkout-processor` for best practices."*
- *"Investigate the errors in Lambda function `order-worker`."*
- *"Why is my Lambda `image-resize` throttling?"*
- *"Right-size the memory for `report-generator` to cut cost."*
- *"ORR for our production Lambda functions."*

The agent collects data automatically and generates a report artifact per function, named `lambda-review-<function-or-scope>-<YYYY-MM-DD>.md`.

## Skill Contents

```
lambda-operational-review/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md
├── references/
│   ├── best-practices-checklist.md    # checklist mapped to Lambda best practices
│   ├── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
│   └── troubleshooting-runbooks.md    # decision-tree runbooks for incident mode
└── evals/                             # evaluation data (not included in upload zip)
```

## Dimensions Covered

| # | Dimension | Reference |
|---|-----------|-----------|
| 1 | Configuration & Runtime (deprecated runtimes, timeout, /tmp, package size) | [Runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) |
| 2 | Reliability (DLQ / destinations, event source error handling, idempotency) | [Async invocation](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html) |
| 3 | Performance (cold starts, memory right-sizing, SnapStart, provisioned concurrency) | [Performance optimization](https://docs.aws.amazon.com/lambda/latest/operatorguide/perf-optimize.html) |
| 4 | Concurrency & Throttling (reserved/provisioned concurrency, account limits) | [Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html) |
| 5 | Security (execution role, secrets, function URL auth, resource policy) | [Lambda security](https://docs.aws.amazon.com/lambda/latest/dg/lambda-security.html) |
| 6 | Cost (memory sizing, idle provisioned concurrency, arm64, log retention) | [Cost optimization](https://docs.aws.amazon.com/lambda/latest/operatorguide/cost-optimization.html) |
| 7 | Observability (X-Ray, log retention, alarms, structured logging) | [Monitoring](https://docs.aws.amazon.com/lambda/latest/dg/lambda-monitoring.html) |

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |
