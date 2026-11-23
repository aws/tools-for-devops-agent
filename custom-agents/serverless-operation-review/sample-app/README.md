# Sample App — Serverless Review Test Bed

> ⚠️ **This template is deliberately misconfigured.** It creates an over-privileged IAM role, a
> function on a deprecated runtime, a DynamoDB table with no backups, and functions that time out,
> run out of memory, and fail asynchronously with no dead-letter queue. Deploy it **only** in an
> isolated non-production account, and delete the stack as soon as testing is finished. It creates
> real, billable resources.

## Internet exposure is opt-in

A Lambda function URL with `AuthType: NONE` is genuinely internet-reachable. In a corporate AWS
account, automated security tooling will detect a public endpoint and raise a finding against the
account owner.

That fault is therefore gated behind the `SeedPublicExposureFaults` parameter, which **defaults to
`false`**:

| Mode | Function URL | Exercises |
|---|---|---|
| `false` (default) | `AuthType: AWS_IAM` — SigV4 required | everything except SLS-LMB-056 |
| `true` | `AuthType: NONE` — anonymous access | adds SLS-LMB-056 (CRITICAL) |

The **API Gateway stage always requires IAM authorization** and is never anonymously reachable. SAM's
transform rejects an intrinsic function inside the `Auth` property, so this one is not switchable by
parameter. The consequence is that `SLS-APG-001` (no authorizer) is not exercised by this template —
validate that check against a real API instead. The stage's other faults still apply: data tracing on,
no access logs, no X-Ray, no throttling.

Everything else works identically in either mode — timeouts, OOM, missing DLQs, the poison-pill
stream, deprecated runtime, wildcard IAM, missing alarms, log retention, DynamoDB backup gaps, and
Step Functions error handling.

The role's wildcard policy deliberately omits `s3:*`; `dynamodb:*` exercises the same wildcard checks
without attracting tooling that watches specifically for S3 wildcards.

## Purpose

Validates that the `serverless-operation-review` skill actually detects what it claims to. Every fault
maps to a specific check id in the skill's catalogs, and one resource — `healthy-control` — is
deliberately correct so false positives are visible.

## Deploy

Default (safe — nothing anonymously reachable):

```bash
cd custom-agents/serverless-operation-review/sample-app

sam deploy \
  --template-file template.yaml \
  --stack-name serverless-review-testbed \
  --capabilities CAPABILITY_NAMED_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --profile your-profile \
  --region us-east-1
```

To see exactly what will be created without creating anything, add `--no-execute-changeset`.

Opt in to the two public-endpoint faults — **isolated sandbox accounts only**:

```bash
sam deploy \
  --template-file template.yaml \
  --stack-name serverless-review-testbed \
  --capabilities CAPABILITY_NAMED_IAM \
  --resolve-s3 --no-confirm-changeset \
  --parameter-overrides SeedPublicExposureFaults=true \
  --profile your-profile --region us-east-1
```

## Generate telemetry

Metric- and log-based checks need invocations. Run the smoke test, then wait for CloudWatch to
aggregate before reviewing:

```bash
./smoke-test.sh serverless-review-testbed us-east-1 your-profile
```

The metric-based checks read a 7-day window. A single smoke-test run is enough for the log-pattern
checks (`Task timed out`, `Runtime.OutOfMemory`) and for `Errors` to be non-zero, but percentile and
trend figures get more meaningful the longer the stack runs. Leaving it deployed for an hour before
reviewing gives a better test; leaving it for a week gives the best one.

## Expected findings

Run the review and confirm each of these appears. A missing row is a detection gap in the skill.

| Resource | Expected check ids | Severity |
|---|---|---|
| `slsreview-overprivileged-role` (all functions) | SLS-LMB-053, SLS-DDB-051 | HIGH |
| `slsreview-always-times-out` | SLS-LMB-030, SLS-LMB-032, SLS-LMB-010 | HIGH |
| `slsreview-memory-hog` | SLS-LMB-033 | HIGH |
| `slsreview-legacy-runtime` | SLS-LMB-050 (python3.9, deprecated 2025-12-15) | CRITICAL |
| `slsreview-legacy-runtime` | SLS-LMB-002 — `AsyncEventsDropped` > 0 once the hourly schedule has run a few times. This is the stronger catch: it proves events were *actually lost*, not merely that a destination is missing | CRITICAL |
| `slsreview-legacy-runtime` | SLS-LMB-001, SLS-LMB-071, SLS-LMB-058, SLS-LMB-086, SLS-LMB-087 | HIGH / MEDIUM / LOW |
| `slsreview-function-url` | SLS-LMB-057 (permissive CORS) | MEDIUM |
| `slsreview-function-url` | SLS-LMB-056 — **only when `SeedPublicExposureFaults=true`** | CRITICAL |
| `slsreview-no-dlq-queue` | SLS-SQS-002, SLS-SQS-003 | HIGH |
| `slsreview-sqs-consumer` | SLS-SQS-006, SLS-SQS-011 | HIGH / MEDIUM |
| `slsreview-unprotected-table` | SLS-DDB-001, SLS-DDB-002, SLS-DDB-003, SLS-DDB-072 | HIGH / MEDIUM |
| `slsreview-stream-consumer` | SLS-STR-001, SLS-STR-002, SLS-STR-003, SLS-STR-004 | CRITICAL / HIGH |
| `slsreview-api` | SLS-APG-005, SLS-APG-060, SLS-APG-062, SLS-APG-022 | HIGH / MEDIUM |
| `slsreview-api-backend` | SLS-LMB-034 (60 s timeout behind API Gateway) | MEDIUM |
| `slsreview-fragile-workflow` | SLS-SFN-030, SLS-SFN-001, SLS-SFN-002, SLS-SFN-004, SLS-SFN-005 | HIGH / MEDIUM |
| All functions except `healthy-control` | SLS-LMB-072 (no log retention), SLS-LMB-080..085 (missing alarms) | MEDIUM |
| `slsreview-healthy-control` | **none at CRITICAL or HIGH** | — |

Two behaviours matter as much as the detections themselves:

1. **Secret handling.** `slsreview-legacy-runtime` has environment variables named `DB_PASSWORD`,
   `API_KEY`, and `SERVICE_TOKEN` with placeholder values. The report must name the **keys** and must
   not print the values. If a value appears anywhere in the output, that is a bug.
2. **No false positives on the control.** `slsreview-healthy-control` has a DLQ destination, reserved
   concurrency, Active tracing, JSON logging, 30-day retention, arm64, a current runtime, operational
   tags, and Errors and Throttles alarms. Any CRITICAL or HIGH finding against it is a false positive.

## Optional: produce the CRITICAL visibility-timeout drift

Lambda validates that a function's timeout does not exceed the queue's visibility timeout when an
event source mapping is created, so the template ships a *valid but not recommended* configuration
(visibility timeout equal to the function timeout rather than six times it), which triggers
`SLS-SQS-002` at HIGH.

To also produce `SLS-SQS-001` at CRITICAL — the drift case where the queue was changed after the
mapping was created — lower the visibility timeout below the function timeout:

```bash
QUEUE_URL=$(aws cloudformation describe-stacks \
  --stack-name serverless-review-testbed \
  --query "Stacks[0].Outputs[?OutputKey=='NoDlqQueueUrl'].OutputValue" \
  --output text --profile your-profile --region us-east-1)

aws sqs set-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attributes VisibilityTimeout=30 \
  --profile your-profile --region us-east-1
```

The consumer's timeout is 60 s, so the queue is now below it — exactly the condition that produces
duplicate processing.

## Clean up

Delete the stack as soon as you are finished. It carries an over-privileged role and a function on a
deprecated runtime, and the scheduled function keeps failing hourly until the stack is gone. If you
deployed with `SeedPublicExposureFaults=true`, the endpoints are reachable by anyone until you delete
it — treat that as urgent rather than tidy-up.

```bash
aws cloudformation delete-stack \
  --stack-name serverless-review-testbed \
  --profile your-profile --region us-east-1

aws cloudformation wait stack-delete-complete \
  --stack-name serverless-review-testbed \
  --profile your-profile --region us-east-1
```

CloudWatch log groups created implicitly by Lambda are not owned by the stack and survive deletion.
Remove them separately:

```bash
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/slsreview-" \
  --query "logGroups[].logGroupName" --output text \
  --profile your-profile --region us-east-1 \
| tr '\t' '\n' \
| xargs -I {} aws logs delete-log-group --log-group-name {} --profile your-profile --region us-east-1
```
