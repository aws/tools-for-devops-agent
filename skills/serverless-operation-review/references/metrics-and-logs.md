# Metrics and Log Analysis Reference

Steps 4 and 5 of `SKILL.md` in detail: exactly which CloudWatch metrics to request per resource type,
the derived values to compute from them, and the log patterns to scan for.

Collection rules that apply throughout:

- **One** `cloudwatch.GetMetricData` call per resource, `Period: 21600` (6 hours), `StartTime` 7 days
  ago, `EndTime` now.
- Percentiles require `ExtendedStatistic` (for example `p99`), not `Statistic`. Mixing them in one
  metric query is a validation error.
- A metric that returns no data because the configuration does not emit it is **not** a finding.
  Omit the row.

---

Make **one** `cloudwatch.GetMetricData` call per resource. `Period: 21600` (6 hours).
`StartTime`: 7 days ago. `EndTime`: now. Percentiles require `ExtendedStatistic`, not `Statistic`.

## 4.1 Lambda — dimension `FunctionName`

| id | metricName | stat | unit |
|----|------------|------|------|
| `inv` | Invocations | Sum | count |
| `err` | Errors | Sum | count |
| `thr` | Throttles | Sum | count |
| `durAvg` | Duration | Average | ms |
| `durP99` | Duration | p99 (ExtendedStatistic) | ms |
| `durMax` | Duration | Maximum | ms |
| `conc` | ConcurrentExecutions | Maximum | count |
| `dlqErr` | DeadLetterErrors | Sum | count |
| `destFail` | DestinationDeliveryFailures | Sum | count |
| `iterAge` | IteratorAge | Maximum | ms |
| `asyncAge` | AsyncEventAge | Maximum | ms |
| `asyncDrop` | AsyncEventsDropped | Sum | count |
| `pcSpill` | ProvisionedConcurrencySpilloverInvocations | Sum | count |
| `pcUtil` | ProvisionedConcurrencyUtilization | Maximum | percent |
| `extDur` | PostRuntimeExtensionsDuration | Average | ms |

`IteratorAge` only exists for stream event sources; `AsyncEventAge`/`AsyncEventsDropped` only for
async invocation; `pcSpill`/`pcUtil` only when provisioned concurrency is configured. Absent metrics
are not findings.

## 4.2 Lambda — account level (once per Region, no dimensions)

| id | metricName | stat | unit |
|----|------------|------|------|
| `claimed` | ClaimedAccountConcurrency | Maximum | count |
| `unreserved` | UnreservedConcurrentExecutions | Maximum | count |

Compare `claimed` against the Region quota from `lambda.GetAccountSettings`
(`AccountLimit.ConcurrentExecutions`, default 1,000). CloudWatch's recommended alarm sits at ~90% of
that quota, so 90% is the HIGH threshold for concurrency headroom.

## 4.3 Event sources

| Service | Dimension | Metrics |
|---|---|---|
| SQS | `QueueName` | `ApproximateAgeOfOldestMessage` (Max), `ApproximateNumberOfMessagesVisible` (Avg), `ApproximateNumberOfMessagesNotVisible` (Avg), `NumberOfMessagesSent` (Sum), `NumberOfMessagesDeleted` (Sum) |
| SQS DLQ | `QueueName` | `ApproximateNumberOfMessagesVisible` (Max) — a non-zero DLQ depth is always reportable |
| SNS | `TopicName` | `NumberOfNotificationsFailed`, `NumberOfNotificationsRedrivenToDlq`, `NumberOfNotificationsFailedToRedriveToDlq`, `NumberOfNotificationsFilteredOut-InvalidAttributes` (all Sum) |
| EventBridge | `RuleName` | `FailedInvocations` (Sum), `ThrottledRules` (Sum), `DeadLetterInvocations` (Sum) |
| Scheduler | `ScheduleGroup` | `InvocationDroppedCount`, `InvocationsFailedToBeSentToDeadLetterCount`, `TargetErrorThrottledCount`, `InvocationThrottleCount` (all Sum) |
| Kinesis | `StreamName` | `GetRecords.IteratorAgeMilliseconds` (Max), `ReadProvisionedThroughputExceeded`, `WriteProvisionedThroughputExceeded`, `PutRecord.Success`, `GetRecords.Success` |

## 4.4 API Gateway

REST uses dimensions `ApiName, Stage`; HTTP and WebSocket use `ApiId, Stage`.

| id | metricName (REST / HTTP) | stat | unit |
|----|--------------------------|------|------|
| `count` | Count | Sum | count |
| `e4xx` | 4XXError / 4xx | Sum and Average | count / ratio |
| `e5xx` | 5XXError / 5xx | Sum and Average | count / ratio |
| `lat` | Latency | p90 (ExtendedStatistic) | ms |
| `intLat` | IntegrationLatency | p90 (ExtendedStatistic) | ms |
| `cacheHit` | CacheHitCount | Sum | count |
| `cacheMiss` | CacheMissCount | Sum | count |

WebSocket APIs additionally use `ClientError`, `IntegrationError`, `ExecutionError`, `MessageCount`.

Documented thresholds: 4XX and 5XX error **ratio** at 0.05 (5% of requests), `Latency` p90 at
2500 ms, `IntegrationLatency` p90 at 2000 ms.

## 4.5 Step Functions — dimension `StateMachineArn`

`ExecutionsStarted`, `ExecutionsSucceeded`, `ExecutionsFailed`, `ExecutionsTimedOut`,
`ExecutionThrottled`, `ExecutionsAborted` (Sum), `ExecutionTime` (Average and p99),
`LambdaFunctionsTimedOut` and `ActivitiesTimedOut` (Sum).

## 4.6 DynamoDB — dimension `TableName`

`ConsumedReadCapacityUnits`, `ConsumedWriteCapacityUnits` (Sum), `ReadThrottleEvents`,
`WriteThrottleEvents`, `ThrottledRequests`, `SystemErrors`, `UserErrors` (Sum),
`SuccessfulRequestLatency` (Average, per `Operation`), and for provisioned tables the account-level
`AccountProvisionedReadCapacityUtilization` / `AccountProvisionedWriteCapacityUtilization` (Maximum)
against the documented 80% threshold. Repeat throttle metrics per GSI with the
`GlobalSecondaryIndexName` dimension.

The derived values computed from these metrics (error rate, throttle rate, timeout
headroom, concurrency headroom, memory utilization, cost weight) are defined in `SKILL.md` Step 4.

---

# Step 5 — Log Collection and Analysis

Per function, resolve the log group (`LoggingConfig.LogGroup`, default `/aws/lambda/<name>`) and:

```
logs.DescribeLogGroups   # logGroupNamePrefix; capture retentionInDays and storedBytes
logs.FilterLogEvents     # 7-day window, one call per pattern, limit results
```

A log group that does not exist means the function has never been invoked — report `INFO`, not a
failure.

## 5.1 Pattern scan

The patterns below were validated against a live test bed. Two of them are easy to get wrong, so scan
for **all** the listed variants rather than the one you expect:

| Pattern | What it indicates |
|---|---|
| `Status: timeout` (in the REPORT line) **or** `Task timed out` | invocation hit the configured timeout. Current managed runtimes record the timeout as a `Status: timeout` field on the REPORT line and may emit no `Task timed out` message at all — scan for both |
| `Runtime.OutOfMemory` / `Runtime exited` | the runtime process was killed for exceeding the memory allocation |
| `MemoryError` (Python) / `JavaScript heap out of memory` (Node.js) / `OutOfMemoryError` (Java) | the language runtime's allocator refused the allocation. This is a memory failure that `Max Memory Used` will **not** reveal — see 5.2 |
| `Status: error` (in the REPORT line) | the invocation ended in an unhandled error. When the runtime itself failed, the REPORT line also carries an `Error Type` field — `Error Type: Runtime.OutOfMemory` is the clearest OOM signal available and needs no message-level scan |
| `Unable to import module` / `Cannot find module` | packaging or layer defect |
| `errorType` / `ERROR` / `Traceback` | handled and unhandled application errors |
| `EC2ThrottledException` / `ENILimitReached` | VPC ENI exhaustion for VPC-attached functions |
| `Rate exceeded` / `ThrottlingException` / `TooManyRequestsException` | downstream AWS throttling |
| `ProvisionedThroughputExceededException` | DynamoDB or Kinesis throttling from inside the function |
| `AccessDenied` / `not authorized to perform` | execution-role permission gaps |
| `Recursive invocation` / `recursive loop detected` | Lambda recursive-loop detection fired |
| `connect ETIMEDOUT` / `SocketTimeout` / `Connection refused` | downstream dependency or NAT/keep-alive issue |

Record occurrence counts per pattern over the 7-day window, and the first and last occurrence
timestamp for anything above zero.

A timeout is also visible without any log scan: a REPORT `Duration` that equals the configured
`Timeout` almost exactly (for example `Duration: 5000.00 ms` on a 5-second timeout) is a timed-out
invocation. Use that as corroboration when log retention is short.

## 5.2 Memory and cold-start extraction

Every Lambda invocation emits a `REPORT` line. Extract `Max Memory Used`, `Memory Size`,
`Init Duration` (cold starts only), `Billed Duration`, and `Status` when present.

Handle **both** log formats:

- Text (`LogFormat: Text`) — parse
  `REPORT RequestId: ... Duration: 12.34 ms Billed Duration: 100 ms Memory Size: 128 MB Max Memory Used: 18 MB Init Duration: 250.00 ms Status: timeout`
- JSON (`LogFormat: JSON`) — read `record.metrics.maxMemoryUsedMB`, `record.metrics.memorySizeMB`,
  `record.metrics.initDurationMs`, `record.metrics.billedDurationMs`

From the sampled REPORT lines compute peak `Max Memory Used`, memory utilization against
`MemorySize`, cold-start count as a share of invocations, and p99 `Init Duration`. The Lambda best
practices guide names `Max Memory Used` as the signal for over- and under-provisioning, and CloudWatch
recommends alarming Lambda Insights `memory_utilization` at 90%.

**`Max Memory Used` does not always reveal a memory failure.** When the language runtime's allocator
refuses a large allocation up front — a Python `MemoryError`, for instance — the pages are never
touched, so `Max Memory Used` can report a low figure on the very invocation that failed for lack of
memory. Observed in practice: a 128 MB function that failed with `MemoryError` reported
`Max Memory Used: 35 MB`. Treat the log evidence as authoritative for memory failures and
`Max Memory Used` as the signal for right-sizing a *healthy* function.

Sample rather than scan exhaustively: 200–500 REPORT lines spread across the window is enough to
size memory, and keeps the log-read cost bounded.
