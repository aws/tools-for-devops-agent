---
name: serverless-operation-review
description: Operational review for AWS serverless workloads — Lambda, API Gateway, Step Functions, DynamoDB, and Lambda event sources (SQS, SNS, EventBridge, EventBridge Scheduler, DynamoDB Streams, Kinesis) — aligned with the AWS Well-Architected Framework and its Serverless Applications Lens. Use this skill when the user asks to review, audit, assess, or health-check serverless functions or applications, or raises Lambda timeouts, throttling, concurrency limits, cold starts, memory sizing, missing dead-letter queues, dropped asynchronous events, poison-pill records, growing stream IteratorAge, duplicate SQS message processing, deprecated Lambda runtimes, unauthenticated function URLs, or serverless cost and log-retention waste. Triggers on requests like 'serverless review', 'Lambda operational review', 'review my Lambda functions', 'serverless best practices audit', 'API Gateway review', 'Step Functions review', 'serverless ORR', or 'how healthy is my serverless workload?'.
metadata:
  version: "1.0.0"
  author: ankitsri-aws
---

# Serverless Operational Review

Conduct a structured operational review of an AWS serverless workload aligned with the
[AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
and the
[Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html),
the [Lambda best practices guide](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html),
and the
[CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
reference.

This skill uses **AWS Lambda, API Gateway, Step Functions, DynamoDB, SQS, SNS, EventBridge,
EventBridge Scheduler, Kinesis, CloudWatch, CloudWatch Logs, IAM, and Cost Explorer read-only APIs
only**. It never mutates a resource.

## When to Use

Activate this skill when the user asks to:

- Review, audit, or assess serverless functions, APIs, state machines, or tables
- Check serverless best-practice compliance or run a serverless operational readiness review (ORR)
- Evaluate serverless reliability, performance, security, cost, or observability posture
- Diagnose recurring Lambda timeouts, throttles, OOM kills, cold starts, or silent event loss
- Understand why SQS messages are processed twice, why a stream is falling behind, or where
  asynchronous invocations are disappearing
- Find serverless cost waste (over-provisioned memory, x86 on Graviton-eligible runtimes, unbounded
  log retention, idle provisioned concurrency)

Do **not** use this skill for container or database engine reviews. Amazon ECS, Amazon EKS, Amazon
RDS/Aurora, Amazon Redshift, and Amazon MSK have their own dedicated review skills.

## Review Scope Model

Five resource families, any subset of which is a valid scope:

| Family | Resources | Reviewed standalone? |
|---|---|---|
| Compute | Lambda functions, versions, aliases, function URLs | Yes |
| Event sources | SQS, SNS, EventBridge, EventBridge Scheduler, DynamoDB Streams, Kinesis | Only as attached to a function |
| API | API Gateway REST, HTTP and WebSocket APIs and their stages | Yes |
| Orchestration | Step Functions state machines | Yes |
| Data | DynamoDB tables and global secondary indexes | Yes |

## Guardrails

These rules are non-negotiable and apply to every step.

1. **Read-only.** Never call a mutating API. Recommend remediation; never apply it. If the user asks
   you to fix a finding, state the exact command or IaC change and let them run it.
2. **Never disclose secret material.** When reporting on environment variables, report the **key
   name only** — never the value, and never a partial value. The same applies to anything found in
   logs that looks like a credential, token, connection string, or private key.
3. **Bound the work.** Follow the budget agreed in Step 1. Never sweep every region without being
   asked.
4. **Disclose what you skipped.** Every report states which regions were skipped, which resources
   were truncated by the budget, and which checks could not run for lack of permission.
5. **Never invent a threshold.** Every severity comes from the check catalogs in `references/`, each
   of which cites its AWS source. If a check has no documented threshold, report the observation as
   `INFO` and say the threshold is workload-specific.

---

## Review Checklist

Work through these in order and track progress as you go. Each step depends on the output of the one
before it, and the detailed section for each carries the same step number.

- [ ] Step 1: Establish scope and budget, and state both before collecting anything
- [ ] Step 2: Discover the serverless inventory, skipping empty Regions
- [ ] Step 3: Collect configuration detail for the families in scope
- [ ] Step 4: Collect 7-day CloudWatch metrics and compute the derived values
- [ ] Step 5: Collect and analyse logs, including the REPORT-line extraction
- [ ] Step 6: Assess alarm coverage against the Serverless Lens metric list
- [ ] Step 7: Analyse security posture and execution-role breadth
- [ ] Step 8: Analyse cost and quantify the savings opportunities
- [ ] Step 9: Evaluate everything collected against the check catalogs and assign severities
- [ ] Step 10: Generate the report, then run the pre-presentation checks

Steps 4 through 8 are independent of each other once Step 3 is done, so collect them in whatever order
is convenient — but do not start Step 9 until they have all either completed or been recorded as
skipped.

---

## Step 1: Establish Scope and Budget

Ask the user what to review. Accept any of:

- Specific resource names or ARNs plus their Region (for example "review the `checkout-processor`
  function in `eu-west-1`")
- An application or stack boundary (a CloudFormation/SAM stack name, or a tag such as
  `Application=checkout`)
- All resources of a family in named Regions ("all Lambda functions in us-east-1 and us-west-2")
- All resources in all configured account Regions

If the user gives no scope, default to **all resource families in the caller's current Region** and
say so explicitly before collecting anything.

### Budget guardrail

A wide serverless account can hold thousands of functions. Before collecting, state the plan and the
cap:

| Scope given | Default cap | Selection rule when the cap binds |
|---|---|---|
| Named resources | none | review all named resources |
| Stack or tag boundary | 50 resources per family | highest 7-day `Invocations` first |
| Named Regions | 25 functions, 10 APIs, 10 state machines, 25 tables per Region | highest 7-day `Invocations` (functions), `Count` (APIs), `ExecutionsStarted` (state machines), `ConsumedReadCapacityUnits` (tables) |
| All Regions | 10 functions, 5 APIs, 5 state machines, 10 tables per Region | as above |

Announce the budget in one line before Step 2, for example:

> Reviewing up to 25 Lambda functions, 10 API Gateway APIs, 10 state machines and 25 DynamoDB tables
> in `us-east-1`, selected by 7-day invocation volume. I will list anything I skip.

If the user asks for a bigger sweep, raise the cap — but warn that a full multi-Region review of a
large account can take several hundred API calls and is best split by Region.

**State the scope in the report, not only in the conversation.** Whatever you examined goes in the
report's Scope Covered section: the Regions, the resource families, the selection rule, and the caps
applied. This holds even when the review finds nothing — "no serverless resources found in us-east-1"
is only meaningful alongside what was searched for and where. A reader must never have to guess at the
boundary of the review.

**Skip empty Regions.** Call the cheap list API first (`lambda:ListFunctions`,
`apigateway:GetRestApis`, `apigatewayv2:GetApis`, `states:ListStateMachines`,
`dynamodb:ListTables`); if a Region returns nothing for every family, record it as empty and move on
without further calls.

---

## Step 2: Discover Serverless Inventory

Per in-scope Region, enumerate the families in scope:

```
lambda.ListFunctions                 # paginated; FunctionVersion=ALL only if versions are in scope
lambda.GetAccountSettings            # account concurrency quota + code storage (once per Region)
apigateway.GetRestApis               # REST APIs
apigatewayv2.GetApis                 # HTTP + WebSocket APIs
states.ListStateMachines             # state machines
dynamodb.ListTables                  # tables
lambda.ListEventSourceMappings       # paginated; maps functions to SQS/streams/MSK/Kafka
```

Produce the inventory table before any deep collection, so the user can redirect scope cheaply:

| Type | Name | Region | Runtime / Protocol / Type | Key attribute |
|---|---|---|---|---|
| Lambda | `checkout-processor` | us-east-1 | python3.13, arm64 | 1024 MB / 30 s |
| API (HTTP) | `checkout-api` | us-east-1 | HTTP | 2 stages |
| State machine | `order-saga` | us-east-1 | STANDARD | logging OFF |
| Table | `orders` | us-east-1 | PAY_PER_REQUEST | PITR off |

---

## Step 3: Collect Configuration Detail

Collect per resource, for the families in scope. `references/collection-reference.md` lists the exact
API calls and the fields each one contributes to a check — use it rather than improvising a call list,
because a field you skip is a check that silently cannot fire.

| Family | Primary calls |
|---|---|
| Lambda | `GetFunctionConfiguration`, `GetFunctionConcurrency`, `GetFunctionEventInvokeConfig`, `ListProvisionedConcurrencyConfigs`, `ListAliases`, `ListFunctionUrlConfigs`, `GetPolicy`, `ListTags` |
| Event sources | `sqs.GetQueueAttributes` (with `AttributeNames=All`), `sns.GetSubscriptionAttributes`, `events.ListTargetsByRule`, `scheduler.GetSchedule`, `kinesis.DescribeStreamSummary`, plus the event source mapping fields |
| API Gateway | `apigateway.GetStages`/`GetMethod`/`GetAuthorizers`/`GetUsagePlans`, `apigatewayv2.GetStages`/`GetRoutes`, `wafv2.GetWebACLForResource` |
| Step Functions | `states.DescribeStateMachine` (parse the ASL definition), `states.ListExecutions` |
| DynamoDB | `dynamodb.DescribeTable`, `DescribeContinuousBackups`, `DescribeTimeToLive`, `application-autoscaling.DescribeScalableTargets` |

The single most important cross-check in this step: **an SQS queue's `VisibilityTimeout` against the
consuming function's `Timeout`**. A queue timeout below the function timeout produces duplicate
processing and is a CRITICAL finding — see `references/checks-event-sources.md`.

Report environment variables by **key name only**. Never the value.

---

## Step 4: Collect CloudWatch Metrics (7-Day)

Make **one** `cloudwatch.GetMetricData` call per resource. `Period: 21600` (6 hours).
`StartTime`: 7 days ago. `EndTime`: now. Percentiles require `ExtendedStatistic`, not `Statistic`.

`references/metrics-and-logs.md` lists the exact metric set per resource type — Lambda (per function
and account level), SQS, SNS, EventBridge, Scheduler, Kinesis, API Gateway, Step Functions, and
DynamoDB — as `| id | metricName | stat | unit |` tables. Use it rather than improvising a metric
list, so reports stay comparable between runs.

A metric that returns no data because the configuration does not emit it is not a finding. Omit the
row.

### Derived values

Compute these once and reuse them in Steps 6, 9, and 10:

| Derived value | Formula | Used by |
|---|---|---|
| Error rate | `Errors / Invocations` over the window | reliability findings |
| Throttle rate | `Throttles / (Invocations + Throttles)` | scaling findings |
| Timeout headroom | `Duration p99 / (Timeout × 1000)` | performance findings |
| Concurrency headroom | `ClaimedAccountConcurrency / AccountLimit.ConcurrentExecutions` | scaling findings |
| Memory utilization | `Max Memory Used / MemorySize` (from Step 5) | cost and performance findings |
| PC utilization | `ProvisionedConcurrencyUtilization` with `...SpilloverInvocations` | cost findings |
| Invocation cost weight | `Invocations × Duration(avg) × MemorySize` | cost split in Step 8 |

---

## Step 5: Collect and Analyze Logs

Per function, resolve the log group (`LoggingConfig.LogGroup`, default `/aws/lambda/<name>`) then:

```
logs.DescribeLogGroups   # logGroupNamePrefix; capture retentionInDays and storedBytes
logs.FilterLogEvents     # 7-day window, one call per pattern, limit results
```

A log group that does not exist means the function has never been invoked — report `INFO`, not a
failure.

Two things to extract:

1. **Error patterns** — `references/metrics-and-logs.md` carries the pattern table (timeouts, OOM
   kills, import failures, ENI exhaustion, downstream throttling, permission denials, recursive-loop
   detection, socket timeouts). Record occurrence counts plus first and last occurrence for anything
   above zero.
2. **Memory and cold starts** — every invocation emits a `REPORT` line carrying `Max Memory Used`,
   `Memory Size`, `Init Duration`, and `Billed Duration`. Parse **both** the text and JSON log
   formats; `LogFormat: JSON` moves these into `record.metrics`. Sample 200–500 REPORT lines across
   the window rather than scanning exhaustively, and state the sample size in the report.

---

## Step 6: Assess Alarm Coverage

For each in-scope resource, call `cloudwatch.DescribeAlarmsForMetric` for the metrics the Serverless
Applications Lens names for that service. A missing alarm is a `MEDIUM` finding, and every reported
gap must carry the recommended statistic, threshold, period, and datapoints-to-alarm so the gap list
doubles as an implementation plan.

The authoritative per-service list, with the recommended alarm settings, is in
`references/cloudwatch-alarm-reference.md`. In summary, the Lens expects alarms on:

| Service | Metrics |
|---|---|
| Lambda | `Errors`, `Throttles`, `Duration`, `ConcurrentExecutions`; `IteratorAge` for stream sources; `DeadLetterErrors` for async; `ProvisionedConcurrencySpilloverInvocations` when PC is enabled |
| API Gateway | `IntegrationLatency`, `Latency`, `5XXError`; WebSocket adds `ClientError`, `IntegrationError`, `ExecutionError` |
| SQS | `ApproximateAgeOfOldestMessage` |
| SNS | `NumberOfNotificationsFailed`, `NumberOfNotificationsFilteredOut-InvalidAttributes` |
| Step Functions | `ExecutionThrottled`, `ExecutionsFailed`, `ExecutionsTimedOut`, `ActivitiesTimedOut`, `LambdaFunctionsTimedOut` |
| EventBridge | `FailedInvocations`, `ThrottledRules` |
| DynamoDB | `ReadThrottleEvents`, `WriteThrottleEvents`, `SystemErrors`, `ThrottledRequests`, `UserErrors` |
| Kinesis | `ReadProvisionedThroughputExceeded`, `WriteProvisionedThroughputExceeded`, `GetRecords.IteratorAgeMilliseconds`, `PutRecord.Success`, `GetRecords.Success` |

Also assess the wider observability posture: `TracingConfig.Mode` on functions, `tracingEnabled` on
API stages and state machines, `LogFormat` (text logging is a `LOW` finding — the Lens asks for
structured JSON logging), and whether alarms exist at both the individual resource level and an
aggregate level.

---

## Step 7: Security and IAM Analysis

### 7.1 Runtime currency

Compare each function's `Runtime` against `references/lambda-runtime-deprecations.md`. Never guess a
deprecation date — if the runtime is absent from the table, say the date is unverified and link the
[runtime support policy](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html).

### 7.2 Execution role breadth

```
iam.GetRole
iam.ListAttachedRolePolicies      # then iam.GetPolicy + iam.GetPolicyVersion per ARN
iam.ListRolePolicies              # then iam.GetRolePolicy per inline policy
```

Flag: `AdministratorAccess` or any `"Action": "*"` with `"Resource": "*"` (CRITICAL), service-level
wildcards such as `s3:*` or `dynamodb:*` (HIGH), `iam:PassRole` with `Resource: "*"` (HIGH), and a
trust policy that allows a principal other than `lambda.amazonaws.com` without a condition (HIGH).

**Summarise the policy; do not reproduce it.** Report the policy name and the specific offending
actions and resources as a short list — for example "inline policy `far-too-broad` grants
`dynamodb:*`, `sqs:*`, `sns:*` on `Resource: "*"`". Do not paste the full policy JSON into the
report. Beyond keeping the finding readable, verbatim policy documents have been observed to trip
the agent's content safety filter, which aborts the response mid-review and loses the whole report.

### 7.3 Invocation exposure

- `lambda.GetPolicy` — a statement with `"Principal": "*"` or `"Principal": {"AWS": "*"}` and no
  `SourceArn`/`SourceAccount` condition is CRITICAL
- `lambda.GetFunctionUrlConfig` — `AuthType: NONE` is a public, unauthenticated HTTPS entry point.
  CRITICAL unless the user confirms it is intentionally public, in which case HIGH with a note to
  front it with CloudFront and WAF
- API Gateway stages with no authorizer and no API key and no WAF association — HIGH
- `disableExecuteApiEndpoint: false` on an API that is only meant to be reached through a custom
  domain — MEDIUM

### 7.4 Data protection

- Environment variables with no `KMSKeyArn` (Lambda-managed key only) — MEDIUM when a key name
  suggests secret material. **Report key names only.** Recommend AWS Secrets Manager or SSM
  Parameter Store rather than environment variables for secrets
- Key-name heuristics that warrant the finding: `PASSWORD`, `PASSWD`, `SECRET`, `TOKEN`, `API_KEY`,
  `APIKEY`, `PRIVATE_KEY`, `CREDENTIAL`, `CONNECTION_STRING`, `DSN`, `AUTH`
- SQS queues and SNS topics without `KmsMasterKeyId` — MEDIUM
- DynamoDB tables without a customer-managed key, where the workload handles regulated data — LOW
  (AWS-owned key encryption is on by default)
- Functions with no `CodeSigningConfigArn` — LOW

If a log-pattern scan surfaces what looks like a credential in a log line, report **that it happened
and in which log group**, never the value, and raise it as HIGH.

---

## Step 8: Cost Analysis

Once per review, not per resource:

```
costexplorer.GetCostAndUsage    # 3 months, MONTHLY, GroupBy USAGE_TYPE,
                                #   Filter Service IN ["AWS Lambda", "AmazonCloudWatch",
                                #   "Amazon API Gateway", "Amazon DynamoDB", "AWS Step Functions"]
```

Cost Explorer does not break Lambda spend down per function. Estimate a per-function share and label
it clearly:

1. Take the most recent full month's Lambda spend.
2. Weight each function by `Invocations × Duration(avg) × MemorySize` from Step 4.
3. Split the month total across functions by weight.
4. Mark every derived figure **(estimated)** in the report.

Opportunities to quantify, each with its own finding:

| Opportunity | Signal | Typical saving |
|---|---|---|
| Memory rightsizing | peak `Max Memory Used` below ~60% of `MemorySize`, or above 90% | proportional to the memory delta, but validate with Lambda Power Tuning before changing |
| Graviton migration | `Architectures: ["x86_64"]` on a runtime that supports `arm64` | up to ~20% cheaper per GB-second plus better price/performance |
| Log retention | `retentionInDays` absent (never expire) | ongoing storage cost on `storedBytes`, compounding monthly |
| Log volume | very high `storedBytes` relative to invocations, or `dataTraceEnabled` on an API stage | ingestion is usually the larger line item than storage |
| Idle provisioned concurrency | `pcUtil` persistently low with no `pcSpill` | full PC charge for unused capacity |
| Unused functions | zero `Invocations` over the window and `LastModified` older than 90 days | small direct cost, but counts against the code storage quota |
| DynamoDB capacity mode | provisioned table with consumed capacity far below provisioned, or on-demand table with steady predictable traffic | switch modes |
| Step Functions type | high-volume short Standard workflow | Express is cheaper per transition for that shape |

Always state that memory changes should be validated with
[AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning) rather than
applied blind, because reducing memory also reduces CPU.

---

## Step 9: Evaluate Against Best Practices

Evaluate every collected value against the check catalogs, and assign exactly one severity per
finding:

| Catalog | Covers |
|---|---|
| `references/checks-lambda.md` | function configuration, concurrency, performance, security, cost |
| `references/checks-event-sources.md` | SQS, SNS, EventBridge, Scheduler, DynamoDB Streams, Kinesis |
| `references/checks-apigateway.md` | REST, HTTP, WebSocket APIs and stages |
| `references/checks-stepfunctions.md` | state machines and ASL definitions |
| `references/checks-dynamodb.md` | tables, GSIs, backups, capacity |
| `references/cloudwatch-alarm-reference.md` | alarm coverage and recommended alarm settings |
| `references/api-quirks.md` | API responses whose obvious reading is wrong |
| `references/collection-reference.md` | the API calls and fields to collect per resource family |
| `references/metrics-and-logs.md` | the metric set per resource type and the log pattern table |
| `references/lambda-runtime-deprecations.md` | runtime end-of-support dates |

Each catalog row carries a check id, pillar, severity, detection rule, remediation, and its AWS
documentation citation. Use the catalog severity as-is.

**Quote the check id in every finding you report** — for example "SLS-SQS-002" — so the reader can look
up the detection rule and its AWS source, and so two runs of the review can be compared line by line.
A finding without its check id is not traceable and is not acceptable output. Adjust it only for stated context, and say so
in the finding — for example, a public function URL on a resource the user has confirmed is a public
webhook drops from CRITICAL to HIGH.

Group findings by Well-Architected pillar for the report: Security, Reliability, Performance
Efficiency, Cost Optimization, Operational Excellence.

---

## Step 10: Generate Report

Use the structure in `references/report-template.md`.

**Artifact naming and granularity:**

- Targeted review of one to three named resources — one artifact per resource, named
  `serverless-review-<resource-name>-<YYYY-MM-DD>.md`
- Anything wider (stack, tag, Region, account) — a single consolidated artifact named
  `serverless-review-<scope-label>-<YYYY-MM-DD>.md` with a per-resource section inside

Section order, which matches the other operation-review skills in this repository:

1. Report Header
2. Executive Summary — health verdict, finding counts by severity, top 3 critical/high items
3. Scope Covered — Regions reviewed, Regions skipped as empty, resources truncated by budget, checks
   skipped for missing permissions
4. Configuration Snapshot
5. Findings by Pillar — Security, Reliability, Performance, Cost, Operational Excellence
6. CloudWatch Metrics (7-Day)
7. Log Pattern Analysis
8. Alarm Coverage
9. Cost Summary
10. Priority Matrix
11. Next Steps — Immediate / Short-term / Long-term, per the severity SLAs
12. Appendix — reference links

Every finding must carry: what was observed (with the concrete value), why it matters, the
recommendation, and a remediation snippet (AWS CLI, SAM/CloudFormation, or CDK). Never present a
finding without evidence.

### Before you present the report — check your own output

A review that is confidently wrong is worse than one that admits a gap. Verify each of these against
the draft, and fix what fails, before showing it to anyone:

- [ ] **Evidence on every finding.** Each one names the observed value, not just the conclusion. If a
      finding says "no DLQ configured" without naming the absent fields, add them.
- [ ] **Severities match the catalogs.** Re-read the check id you assigned. If you adjusted a severity
      for context, the finding says so and says why.
- [ ] **No invented thresholds.** Every numeric threshold traces to a catalog row. Where AWS publishes
      none, the finding says the threshold is workload-specific.
- [ ] **Absent metrics are not findings.** A metric with no datapoints because the configuration does
      not emit it was omitted, not reported as a failure.
- [ ] **Cost figures are marked (estimated)** and the split method is stated. No estimate is presented
      as a bill.
- [ ] **No secret values anywhere.** Environment variables appear by key name only. Nothing
      credential-shaped from a log line was reproduced.
- [ ] **Scope Covered is complete.** Every Region skipped, resource truncated, and check that could not
      run is listed — including the ones denied by permission or platform restriction.
- [ ] **Counts reconcile.** The severity counts in the Executive Summary equal the findings in the body.
- [ ] **The verdict follows the rule.** Any CRITICAL means ❌; otherwise any HIGH means ⚠️; otherwise ✅.

If a check in this list cannot be satisfied, say so in the report rather than quietly dropping it.

---

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | Fix within 24–48 hours |
| HIGH | Significant gap that could lead to incidents | Fix within 1 week |
| MEDIUM | Notable improvement opportunity | Plan within 30 days |
| LOW | Minor optimization or hardening | Address when convenient |
| INFO | Observation, no action required | N/A |

---

## Error Handling

`references/api-quirks.md` carries the error table — what each failure means and whether it is a
finding, a skipped check, or nothing at all. The rule that matters most: an `AccessDeniedException`
never silently disappears. Skip that check, record the missing action, and report it in the report's
Scope Covered section.

---

## Known API Quirks

`references/api-quirks.md` records the API responses whose obvious reading is wrong — several
confirmed against a live account. Read it before interpreting a response as a finding. The two that
most often cause a false finding:

- `lambda.GetFunctionEventInvokeConfig` raising `ResourceNotFoundException` means **defaults apply**
  (2 retries, 6-hour maximum event age, no destination), not that something is broken.
- `lambda.GetFunctionConcurrency` returning empty means the function is **unreserved**, not that its
  concurrency is zero. Reserved concurrency of `0` is a very different thing — it throttles the
  function completely.

---

## Appendix — Reference Links

The authoritative sources for every threshold this skill applies:

- [Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html)
  — which metrics to alarm on, and the stream error-handling controls
- [Lambda best practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
  — SQS visibility timeout, memory sizing, recursion containment
- [CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
  — statistic, threshold, period and datapoints per metric
- [Lambda runtime support policy](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
  — runtime deprecation dates

`references/report-template.md` carries the fuller link list to reproduce in each report.
