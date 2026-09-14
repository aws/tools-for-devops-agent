---
name: lambda-operational-review
description: >
  Comprehensive AWS Lambda operational review and troubleshooting aligned with
  the AWS Lambda operator guide and the AWS Well-Architected serverless lens.
  Assesses one or many Lambda functions across configuration, reliability,
  performance (cold starts, timeouts, memory sizing), concurrency and
  throttling, security, cost, and observability — using read-only control-plane,
  CloudWatch metrics, and CloudWatch Logs API calls — then produces a rated
  report with prioritized findings and remediation guidance. Also handles
  incident-style investigations of Lambda errors, throttles, and latency.

  Use when a user asks to review, audit, assess, or troubleshoot Lambda
  functions for best-practices compliance, errors, throttling, timeouts, cold
  starts, memory/right-sizing, concurrency, security posture, cost, or
  observability. Triggers on phrasings like "Lambda review", "Lambda best
  practices audit", "review my Lambda functions", "investigate Lambda errors in
  function X", "why is my Lambda throttling", "Lambda cold start problem",
  "Lambda timing out", "right-size Lambda memory", "Lambda cost optimization",
  or "ORR for Lambda".

  Do NOT use for EC2 instances (use the EC2 skill), EKS/ECS containers (use the
  EKS skills), Step Functions state-machine design, or for authoring
  CloudFormation, CDK, SAM, or Terraform templates.
metadata:
  author: aws-samples
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation, Incident RCA"
  aws-devops-agent-skills.aws-services: "AWS Lambda, Amazon CloudWatch, Amazon CloudWatch Logs"
  aws-devops-agent-skills.technical-domains: "Compute, Serverless"
---

# Lambda Operational Review & Troubleshooting

Conduct a comprehensive, read-only operational review — or a focused incident
investigation — of AWS Lambda functions aligned with the
[AWS Lambda operator guide](https://docs.aws.amazon.com/lambda/latest/operatorguide/intro.html)
and the [Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html).

## When to Use

Activate this skill when the user asks to:
- Review, audit, or assess Lambda functions for best practices
- Investigate Lambda errors, throttling, timeouts, or latency
- Diagnose cold-start problems or tune memory / right-size a function
- Evaluate Lambda concurrency, reserved/provisioned concurrency, or DLQ setup
- Review Lambda security (IAM, secrets, VPC, public function URLs)
- Assess Lambda cost or observability posture
- Perform a Lambda operational readiness review (ORR)

Do **not** activate for EC2 (use `ec2-operation-review`), EKS/ECS containers,
Step Functions design, or IaC template authoring.

## Operating Modes

| Mode | Trigger | Behavior |
|---|---|---|
| Full Review | "Lambda review", "best practices audit", "ORR", "assess my functions" | Run all dimensions across the target set, produce a scored report |
| Incident Investigation | "investigate errors in function X", "why is X throttling / timing out" | Focus on errors, throttles, timeouts, and cold starts for the named function; correlate metrics with log patterns |
| Right-Sizing | "right-size", "tune memory", "reduce cost / duration" | Focus on memory vs duration vs cost tradeoff |

## Critical Warnings

- **This skill is read-only.** Every command is a `Get*`, `List*`, or read-only
  CloudWatch / Logs call. The agent does NOT call `UpdateFunctionConfiguration`,
  `UpdateFunctionCode`, `PutFunctionConcurrency`, `DeleteFunction`, `Invoke`, or
  any mutating API. All remediations are recommendations for the operator.
- **Do not invoke the function to reproduce an issue.** Diagnose from metrics
  and logs only.
- **UNKNOWN ≠ PASS.** Any check that cannot be assessed MUST be reported as
  `NOT_ASSESSED` with the reason, never silently marked passing.

## Step 1: Identify Target Functions

Ask the user which functions to review. Accept:
- Specific function names or ARNs and regions
- Functions with a given tag
- "all functions" in specific regions
- "all functions in all regions"

If no scope is given, default to all configured account regions. Do not silently
substitute a target — if a named function is not found, list the closest
candidates (including same name in another region) and ask before assessing.

## Step 2: Discover Function Configuration

Per region (skip empty regions):

```
lambda.ListFunctions                       # inventory: runtime, memory, timeout, arch, last modified
lambda.GetFunctionConfiguration            # per function: full config
lambda.GetFunctionConcurrency             # reserved concurrency
lambda.ListProvisionedConcurrencyConfigs   # provisioned concurrency per alias/version
lambda.GetPolicy                           # resource policy (who can invoke)
lambda.ListEventSourceMappings             # SQS/Kinesis/DynamoDB/Kafka triggers + batch settings
lambda.GetFunctionUrlConfig                # function URL + auth type (if present)
lambda.ListAliases / ListVersionsByFunction
lambda.ListTags
lambda.GetAccountSettings                  # account concurrency limit + usage
iam.GetRole / GetRolePolicy / ListAttachedRolePolicies  # execution role scope
```

Capture per function: runtime (and deprecation status), architecture
(x86_64/arm64), memory size, timeout, ephemeral storage, environment variable
count and whether secrets look inlined, DLQ / on-failure destination, VPC
config, layers, code size, `SnapStart` status, tracing (X-Ray) mode, reserved
and provisioned concurrency, function URL auth type, and tags.

## Step 3: Collect CloudWatch Metrics

Retrieve a 14-day window (`Period=3600`) via `cloudwatch.GetMetricData` for each
function (Namespace `AWS/Lambda`, Dimension `FunctionName`). See
`references/metrics-thresholds.md` for the metric list and thresholds. Also:

```
cloudwatch.DescribeAlarmsForMetric         # alarm coverage (Errors, Throttles, Duration)
```

## Step 4: Analyze Logs (Incident mode, or when errors present)

Query the function's log group (`/aws/lambda/<name>`) via
`logs.FilterLogEvents` / `logs.StartQuery` (Logs Insights) for the error and
timeout patterns in `references/troubleshooting-runbooks.md`. Correlate log
signatures with the metric window. Never invoke the function to reproduce.

## Step 5: Analyze Against the Dimensions

Apply `references/best-practices-checklist.md`. Summary:

1. **Configuration & Runtime** — deprecated/soon-deprecated runtime, timeout too
   high or too low, ephemeral storage sizing, code package size, too many layers.
2. **Reliability** — DLQ or on-failure destination for async, event source
   mapping batch/retry/bisect settings, error and DLQ metrics, idempotency for
   at-least-once sources.
3. **Performance** — cold-start rate and `InitDuration`, `Duration` p95 vs
   timeout, memory sizing (Lambda CPU scales with memory), SnapStart / provisioned
   concurrency candidacy, VPC-attached cold-start considerations.
4. **Concurrency & Throttling** — `Throttles` > 0, account concurrency headroom,
   reserved concurrency starving/hoarding, provisioned concurrency utilization,
   `ConcurrentExecutions` vs limit.
5. **Security** — execution role least privilege (no `*`), no secrets in plaintext
   env vars (use Secrets Manager / SSM Parameter Store), function URL auth
   (`AuthType != NONE` unless intentional), resource policy not overly broad,
   VPC/security-group scope, KMS on env vars.
6. **Cost** — over-provisioned memory (duration flat above a memory point),
   idle provisioned concurrency, arm64 (Graviton) candidacy, excessive invocation
   volume / retries, log retention driving CloudWatch Logs cost.
7. **Observability** — X-Ray tracing enabled, structured logging, log retention
   set (not "never expire"), alarms on Errors/Throttles/Duration, Lambda Insights.

## Step 6: Assign Severity

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |

## Step 7: Generate the Report

Produce one report artifact per function (or a fleet report for multi-function
reviews), named `lambda-review-<function-or-scope>-<YYYY-MM-DD>.md`.

Report structure:
1. **Summary** — function identity, overall rating, findings-by-severity counts.
2. **Assessment table** — one row per dimension (GOOD / NEEDS ATTENTION /
   NOT_ASSESSED) with a headline.
3. **Findings** — grouped by severity (CRITICAL first). Each includes the
   observation with the concrete metric/config value, the risk, and a specific
   remediation with expected outcome and any impact precondition.
4. **Right-sizing appendix** (when duration/memory data available) — observed
   `Duration` distribution vs memory, with a recommended memory setting and the
   cost/latency tradeoff.
5. **Coverage note** — assessed vs `NOT_ASSESSED` (missing metrics, logs,
   permissions) and why.

## Prerequisites

Requires the DevOps Agent's primary cloud-source role to have read access to
Lambda, CloudWatch, CloudWatch Logs, and IAM (read-only), plus optional Cost
Explorer and X-Ray. See the README for the exact IAM action list. The skill
never calls a mutating API and never invokes the function.
