# Check Catalog — AWS Lambda

Every row carries a check id, pillar, severity, detection rule, and its AWS source. Use the severity
as written. Adjust only for context the user has confirmed, and say so in the finding.

Pillar codes: **SEC** Security · **REL** Reliability · **PERF** Performance Efficiency ·
**COST** Cost Optimization · **OPS** Operational Excellence

Sources referenced throughout:

- [Lens — Failure management](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/failure-management.html)
- [Lens — Metrics and alerts](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/opex-metrics-and-alerts.html)
- [Lens — Limits](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/limits.html)
- [Lambda best practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
- [Lambda security best practices](https://docs.aws.amazon.com/lambda/latest/dg/lambda-security-best-practices.html)

---

## Reliability — asynchronous invocation

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-001 | REL | HIGH | Function is invoked asynchronously (has an EventBridge, SNS, S3, or `InvocationType: Event` caller) and has **neither** `DeadLetterConfig.TargetArn` **nor** `EventInvokeConfig.DestinationConfig.OnFailure` | Configure an `OnFailure` destination (SQS queue, SNS topic, EventBridge bus, or another function) | Lens — Failure management: "Use a dead-letter queue mechanism to retain, investigate, and retry failed transactions" |
| SLS-LMB-002 | REL | CRITICAL | `AsyncEventsDropped` > 0 over the 7-day window | Events are being lost. Add an `OnFailure` destination, then raise `MaximumEventAgeInSeconds` / `MaximumRetryAttempts` or fix the failing invocations | Lens — Failure management |
| SLS-LMB-003 | REL | MEDIUM | `EventInvokeConfig` absent or `MaximumRetryAttempts` left at the default `2` on a function whose failures are not idempotent-safe to replay | Set `MaximumRetryAttempts` deliberately (0 for non-retryable work with a destination, higher for transient-failure workloads) | Lambda async invocation defaults |
| SLS-LMB-004 | REL | MEDIUM | `MaximumEventAgeInSeconds` left at the default 21,600 s (6 h) on a latency-sensitive workload | Lower the maximum event age so stale events are discarded to the destination rather than retried hours later | Lambda async invocation defaults |
| SLS-LMB-005 | REL | HIGH | `DeadLetterErrors` > 0 | Lambda could not write to the configured DLQ — usually a missing `sqs:SendMessage`/`sns:Publish` permission on the execution role, or a deleted target | Lens — Metrics and alerts (alert on `DeadLetterErrors`) |
| SLS-LMB-006 | REL | HIGH | `DestinationDeliveryFailures` > 0 | The `OnFailure`/`OnSuccess` destination is unreachable or the execution role lacks permission to write to it | Lambda destinations |
| SLS-LMB-007 | REL | LOW | Function uses only the legacy `DeadLetterConfig` and no `OnFailure` destination | Migrate to an `OnFailure` destination: it carries the full invocation record including the response and error, where the DLQ carries only the payload | Lambda destinations |

## Reliability — errors, recursion, and idempotency

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-010 | REL | HIGH | Error rate (`Errors / Invocations`) ≥ 1% over the window | Investigate the top log error patterns from Step 5; add or tune `Retry` at the caller | CloudWatch recommended alarms — `Errors`, threshold "greater than zero", tolerance-based |
| SLS-LMB-011 | REL | CRITICAL | Error rate ≥ 10% over the window | Treat as an active incident, not a review finding | CloudWatch recommended alarms — `Errors` |
| SLS-LMB-012 | REL | CRITICAL | Log scan matches `Recursive invocation` / `recursive loop detected`, or the function writes to its own trigger | Lambda's recursive loop detection has fired. Break the loop; as immediate containment set reserved concurrency to `0` to throttle all invocations while the code is fixed | Lambda best practices: "Avoid using recursive invocations… set the function reserved concurrency to `0` immediately" |
| SLS-LMB-013 | REL | LOW | Function consumes from an event source mapping (SQS, Kinesis, DynamoDB Streams, MSK) — idempotency cannot be verified from configuration | Confirm the handler is idempotent. Event source mappings process each event **at least once** and duplicates do occur | Lambda best practices: "Write idempotent code"; ESM warning on duplicate processing |
| SLS-LMB-014 | REL | MEDIUM | `Timeout` is at or near the 900 s maximum on a synchronous, user-facing path | A long timeout converts a downstream hang into held concurrency. Bound the timeout to the real p99 plus headroom and fail fast | Lambda best practices: "Load test your Lambda function to determine an optimum timeout value" |
| SLS-LMB-015 | REL | MEDIUM | Function is VPC-attached and the log scan matches `EC2ThrottledException` or `ENILimitReached` | Hyperplane ENI capacity or subnet IP exhaustion. Add subnet IP space across more AZs and check the ENI quota | Lambda VPC networking |
| SLS-LMB-016 | REL | LOW | Function is VPC-attached with subnets in fewer than two Availability Zones | A single-AZ subnet set makes the function fail with the AZ | Lens — Reliability foundations |

## Reliability and scaling — concurrency

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-020 | REL | HIGH | `ClaimedAccountConcurrency` ≥ 90% of `AccountLimit.ConcurrentExecutions` | Request a concurrency quota increase, release unused reserved or provisioned concurrency, improve function throughput, or raise event source batch sizes | CloudWatch recommended alarms — `ClaimedAccountConcurrency`, "about 90% of the concurrency quota set for the account in the Region" |
| SLS-LMB-021 | REL | MEDIUM | `ClaimedAccountConcurrency` between 70% and 90% of the quota | Plan headroom before the next traffic increase; the default Region quota is 1,000 | CloudWatch recommended alarms; Lens — Limits |
| SLS-LMB-022 | REL | HIGH | `Throttles` > 0 on a synchronous, user-facing function | Requests are being rejected. Add reserved concurrency to protect this function, use provisioned concurrency for latency-critical paths, and add timeouts, retries, and backoff with jitter at the caller | CloudWatch recommended alarms — `Throttles`; Lambda best practices "Build in throttle tolerance" |
| SLS-LMB-023 | REL | MEDIUM | `Throttles` > 0 on an async or stream-driven function | Throttled async invocations are retried, but retries consume event age. Confirm the retry budget and destination are set | Lambda best practices |
| SLS-LMB-024 | REL | MEDIUM | A business-critical function has no `ReservedConcurrentExecutions` while other functions in the account are unreserved and high-volume | Without reserved concurrency, a noisy neighbour can consume the shared pool and starve this function | Lambda best practices: "If you need to limit how high your function can scale, you can configure reserved concurrency" |
| SLS-LMB-025 | REL | CRITICAL | `ReservedConcurrentExecutions` is `0` and the function is not intentionally disabled | Reserved concurrency of zero throttles the function completely. Confirm whether this is deliberate containment or an accident | Lambda concurrency |
| SLS-LMB-026 | REL | HIGH | Function calls a downstream with a fixed connection ceiling (RDS, self-managed database, third-party API) and has no reserved concurrency | Lambda scales faster than most downstreams. Cap it with reserved concurrency and pool connections (RDS Proxy for relational targets) | Lambda best practices: "Be familiar with your upstream and downstream throughput constraints" |

## Performance efficiency

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-030 | PERF | HIGH | `Duration` p99 ≥ 90% of the configured `Timeout` | The function is on the edge of timing out. Either raise the timeout with evidence or reduce the work per invocation | CloudWatch recommended alarms — `Duration`: "Make sure to set the threshold lower than the configured function timeout" |
| SLS-LMB-031 | PERF | MEDIUM | `Duration` p99 between 70% and 90% of `Timeout` | Little headroom for a slow downstream day | CloudWatch recommended alarms — `Duration` |
| SLS-LMB-032 | PERF | HIGH | REPORT line carries `Status: timeout`, or the log scan matches `Task timed out`, or `Duration` equals the configured `Timeout` almost exactly | Invocations are being killed at the timeout. Correlate with downstream latency before raising the timeout. Current managed runtimes record this as `Status: timeout` on the REPORT line and may emit no `Task timed out` message — scan for both | Lambda best practices; verified against a live test bed |
| SLS-LMB-033 | PERF | HIGH | Peak `Max Memory Used` ≥ 90% of `MemorySize`, **or** the log scan matches `Runtime.OutOfMemory` / `Runtime exited` (runtime killed) **or** a language-level allocator failure — `MemoryError` (Python), `JavaScript heap out of memory` (Node.js), `OutOfMemoryError` (Java) | Raise `MemorySize`; note this also raises CPU proportionally | Lambda best practices: analyse `Max Memory Used`; CloudWatch recommends alarming Lambda Insights `memory_utilization` at 90% |
| SLS-LMB-033a | PERF | HIGH | A language-level allocator failure appears in the logs while `Max Memory Used` reports a low figure | Do not dismiss the finding because the metric looks healthy. When the allocator refuses a large allocation up front the pages are never touched, so `Max Memory Used` under-reports. Observed in practice: a 128 MB function failing with `MemoryError` reported `Max Memory Used: 35 MB` | verified against a live test bed |
| SLS-LMB-034 | PERF | MEDIUM | Function is behind an API Gateway REST/HTTP integration and `Timeout` > 29 s | API Gateway's integration timeout caps the request well before the function's own timeout, so the client sees a 504 while the function keeps running and billing | API Gateway quotas |
| SLS-LMB-035 | PERF | MEDIUM | Cold starts exceed 5% of invocations on a synchronous, latency-sensitive path, or p99 `Init Duration` > 1 s | Move SDK client and connection setup outside the handler, trim the deployment package, consider SnapStart (Java) or provisioned concurrency | Lambda best practices: "Take advantage of execution environment reuse" |
| SLS-LMB-036 | PERF | MEDIUM | `ProvisionedConcurrencySpilloverInvocations` > 0 | Traffic is exceeding the provisioned pool and falling back to on-demand cold starts. Raise provisioned concurrency or add autoscaling on the alias | Lens — Metrics and alerts: "When provisioned concurrency is enabled, use `ProvisionedConcurrencySpilloverInvocations`" |
| SLS-LMB-037 | PERF | LOW | `PostRuntimeExtensionsDuration` is a material share of `Duration` | An extension or layer is adding billed time after the handler returns. Audit the extensions in use | Lambda extensions |
| SLS-LMB-038 | PERF | LOW | Java function with no `SnapStart` and a high `Init Duration` | SnapStart materially reduces Java cold start | Lambda SnapStart |
| SLS-LMB-039 | PERF | LOW | Log scan shows repeated `connect ETIMEDOUT` / `SocketTimeout` on a function that reuses connections | Apply the runtime's keep-alive directive; Lambda purges idle connections and reusing a dead one errors | Lambda best practices: "Use a keep-alive directive to maintain persistent connections" |

## Security

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-050 | SEC | CRITICAL | `Runtime` deprecation date is in the past | Upgrade to a supported runtime — see `lambda-runtime-deprecations.md` | Lambda runtime deprecation policy |
| SLS-LMB-051 | SEC | HIGH | `Runtime` deprecation date within 180 days, or the runtime is AL2-based (AL2 reached end of life 2026-06-30), or the runtime is a public preview runtime | Plan the upgrade now; preview runtimes must not carry production workloads | Lambda runtimes page |
| SLS-LMB-052 | SEC | CRITICAL | Execution role grants `AdministratorAccess`, or any statement with `"Action": "*"` and `"Resource": "*"` | Replace with least-privilege actions scoped to the specific resource ARNs the handler touches | Lambda best practices: "Use most-restrictive permissions when setting IAM policies" |
| SLS-LMB-053 | SEC | HIGH | Execution role grants a service-level wildcard (`s3:*`, `dynamodb:*`, `sqs:*`) or `iam:PassRole` on `Resource: "*"` | Enumerate the actions actually used and scope resources | Lambda best practices |
| SLS-LMB-054 | SEC | HIGH | Role trust policy allows a principal other than `lambda.amazonaws.com` with no condition, or allows a wildcard principal | Restrict the trust policy; add `aws:SourceAccount` / `aws:SourceArn` conditions | IAM best practices |
| SLS-LMB-055 | SEC | CRITICAL | Resource-based policy (`lambda:GetPolicy`) contains `"Principal": "*"` or `{"AWS": "*"}` with no `SourceArn` or `SourceAccount` condition | Scope the statement to the specific calling service or account | Lambda resource-based policies |
| SLS-LMB-056 | SEC | CRITICAL | Function URL with `AuthType: NONE` | This is a public unauthenticated HTTPS endpoint. Switch to `AWS_IAM`, or if it must stay public, front it with CloudFront and AWS WAF and confirm the handler validates every input. Drops to HIGH only when the user confirms the public exposure is intentional | Lambda function URLs |
| SLS-LMB-057 | SEC | MEDIUM | Function URL with permissive CORS (`AllowOrigins: ["*"]`) on an authenticated endpoint | Restrict allowed origins | Lambda function URL CORS |
| SLS-LMB-058 | SEC | MEDIUM | Environment variables present, `KMSKeyArn` absent, and at least one key name matches `PASSWORD`, `PASSWD`, `SECRET`, `TOKEN`, `API_KEY`, `APIKEY`, `PRIVATE_KEY`, `CREDENTIAL`, `CONNECTION_STRING`, `DSN`, `AUTH` | Move the value to AWS Secrets Manager or SSM Parameter Store and read it at init; if it must stay an environment variable, encrypt with a customer-managed KMS key. **Report the key name only — never the value** | Lambda security best practices; Lambda environment variable encryption |
| SLS-LMB-059 | SEC | LOW | Environment variables present with no `KMSKeyArn` and no secret-suggesting key names | Environment variables are encrypted at rest with an AWS-managed key by default; a customer-managed key adds auditability and key-policy control | Lambda environment variables |
| SLS-LMB-060 | SEC | LOW | No `CodeSigningConfigArn` | Code signing verifies the deployment package was produced by a trusted publisher | Lambda code signing |
| SLS-LMB-061 | SEC | HIGH | Log scan surfaces what appears to be a credential, token, or connection string in a log line | Report the log group and the pattern that matched — **never the value**. Redact at the source and rotate the exposed credential | Lambda best practices; Lens — logging |
| SLS-LMB-062 | SEC | MEDIUM | Function is VPC-attached with a security group allowing unrestricted egress `0.0.0.0/0` on all ports, where the workload only needs specific destinations | Scope egress rules to required destinations and use VPC endpoints for AWS services | Security best practices |
| SLS-LMB-063 | SEC | INFO | Account has neither GuardDuty Lambda Protection nor Security Hub Lambda controls enabled | Both give continuous detection that a point-in-time review cannot | Lambda best practices — security best practices section |

## Cost optimization

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-070 | COST | MEDIUM | Peak `Max Memory Used` < 60% of `MemorySize` | Over-provisioned memory. Validate with AWS Lambda Power Tuning before changing — lowering memory also lowers CPU and can raise duration and total cost | Lambda best practices: "By analyzing the `Max Memory Used:` field, you can determine if your function needs more memory or if you over-provisioned"; Lambda Power Tuning |
| SLS-LMB-071 | COST | MEDIUM | `Architectures: ["x86_64"]` on a supported runtime | All supported runtimes support `arm64`. Graviton gives better price/performance. Rebuild container images, native binaries, and architecture-specific layers first, then cut over with a weighted alias | Lambda runtimes: "All supported Lambda runtimes support both x86_64 and arm64 architectures" |
| SLS-LMB-072 | COST | MEDIUM | Log group `retentionInDays` is absent (never expire) | Set a retention period matched to the operational and compliance need — 30 days for most application logs, longer only where required | CloudWatch Logs retention |
| SLS-LMB-073 | COST | LOW | Log group `storedBytes` is large relative to invocation count | Reduce log verbosity, use `ApplicationLogLevel` to filter at source, and prefer EMF over verbose logging for metrics. Ingestion is typically the larger cost line than storage | Lambda advanced logging controls; Lambda best practices — EMF |
| SLS-LMB-074 | COST | MEDIUM | Provisioned concurrency configured with persistently low `ProvisionedConcurrencyUtilization` and no `ProvisionedConcurrencySpilloverInvocations` | The pool is paid for and idle. Reduce it, or replace with scheduled autoscaling that matches the traffic curve | Lambda provisioned concurrency: "Configuring provisioned concurrency incurs additional charges" |
| SLS-LMB-075 | COST | LOW | Zero `Invocations` over the window and `LastModified` older than 90 days | Delete unused functions — they count against the deployment package storage quota | Lambda best practices: "Delete Lambda functions that you are no longer using" |
| SLS-LMB-076 | COST | LOW | Very short `Duration` (single-digit ms) with a large `BatchSize` of 1 on a queue or stream source | Larger batches amortise invocation overhead across more records and raise throughput | Lambda best practices: "Test with different batch and record sizes" |
| SLS-LMB-077 | COST | INFO | Account has no AWS Cost Anomaly Detection monitor covering Lambda | Cost Anomaly Detection catches runaway invocation cost that a periodic review will miss | Lambda best practices: "Use AWS Cost Anomaly Detection" |

## Operational excellence

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-LMB-080 | OPS | MEDIUM | No CloudWatch alarm on `Errors` | See `cloudwatch-alarm-reference.md` for the recommended alarm definition | Lens — Metrics and alerts |
| SLS-LMB-081 | OPS | MEDIUM | No alarm on `Throttles` | as above | Lens — Metrics and alerts |
| SLS-LMB-082 | OPS | MEDIUM | No alarm on `Duration` | as above | Lens — Metrics and alerts |
| SLS-LMB-083 | OPS | MEDIUM | No alarm on `ConcurrentExecutions` or `ClaimedAccountConcurrency` | as above | Lens — Metrics and alerts |
| SLS-LMB-084 | OPS | MEDIUM | Stream-driven function with no alarm on `IteratorAge` | as above | Lens — Metrics and alerts; Lambda best practices recommends a 30,000 ms `IteratorAge` alarm |
| SLS-LMB-085 | OPS | MEDIUM | Async function with no alarm on `DeadLetterErrors` | as above | Lens — Metrics and alerts |
| SLS-LMB-086 | OPS | MEDIUM | `TracingConfig.Mode` is `PassThrough` | Enable Active tracing for distributed tracing across the invocation path | Lens — Distributed tracing |
| SLS-LMB-087 | OPS | LOW | `LoggingConfig.LogFormat` is `Text` | Structured JSON logging makes logs searchable and filterable; Powertools for AWS Lambda formats it automatically | Lambda best practices: "Use structured JSON logging for better observability" |
| SLS-LMB-088 | OPS | LOW | Function publishes custom metrics with synchronous CloudWatch API calls from handler code | Emit metrics asynchronously with the Embedded Metric Format instead — it removes the API call from the invocation path | Lambda best practices: "Emit custom metrics asynchronously using Embedded Metric Format (EMF)" |
| SLS-LMB-089 | OPS | LOW | No aliases, and callers or event sources point at `$LATEST` | Aliases and versions enable weighted deployments and rollback | Lambda aliases |
| SLS-LMB-090 | OPS | LOW | Missing operational tags — `Environment`, `Owner`, `Runbook`, `OnCall` | Tag for ownership routing and cost allocation | Well-Architected OPS |
| SLS-LMB-091 | OPS | INFO | `State` is not `Active` or `LastUpdateStatus` is `Failed`/`InProgress` | The function is mid-update or failed to update; re-check before trusting other findings | Lambda function states |
| SLS-LMB-092 | OPS | LOW | Function has more than 50 published versions | Version sprawl consumes the code storage quota and confuses rollback. Prune old versions | Lambda quotas |

---

## Remediation snippets

### Add an OnFailure destination (SAM)

```yaml
Resources:
  CheckoutProcessor:
    Type: AWS::Serverless::Function
    Properties:
      EventInvokeConfig:
        MaximumRetryAttempts: 2
        MaximumEventAgeInSeconds: 3600
        DestinationConfig:
          OnFailure:
            Type: SQS
            Destination: !GetAtt CheckoutFailureQueue.Arn
```

CLI equivalent:

```bash
aws lambda put-function-event-invoke-config \
  --function-name checkout-processor \
  --maximum-retry-attempts 2 \
  --maximum-event-age-in-seconds 3600 \
  --destination-config '{"OnFailure":{"Destination":"arn:aws:sqs:REGION:ACCOUNT:checkout-failures"}}'
```

### Cap concurrency to protect a downstream

```bash
aws lambda put-function-concurrency \
  --function-name checkout-processor \
  --reserved-concurrent-executions 50
```

### Emergency containment for a recursive loop

```bash
# Throttles ALL invocations of the function immediately. Confirm with the owner first.
aws lambda put-function-concurrency \
  --function-name looping-function \
  --reserved-concurrent-executions 0
```

### Move to arm64

```bash
aws lambda update-function-configuration \
  --function-name checkout-processor \
  --architectures arm64
```

Only after confirming the package has no x86-only native dependencies. Prefer publishing a new
version and shifting an alias gradually.

### Set log retention

```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/checkout-processor \
  --retention-in-days 30
```

### Switch to structured JSON logging

```bash
aws lambda update-function-configuration \
  --function-name checkout-processor \
  --logging-config LogFormat=JSON,ApplicationLogLevel=INFO,SystemLogLevel=WARN
```
