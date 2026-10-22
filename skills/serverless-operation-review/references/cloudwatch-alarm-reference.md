# CloudWatch Alarm Reference for Serverless Workloads

Two sources drive the alarm-coverage check in Step 6 of the skill:

1. **Which** metrics to alarm on comes from the Serverless Applications Lens,
   [Metrics and alerts](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/opex-metrics-and-alerts.html),
   which publishes an explicit per-service list.
2. **What settings** to use comes from
   [CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html),
   which publishes statistic, threshold, period, datapoints-to-alarm, evaluation periods, and
   comparison operator per metric.

Where a metric appears in the Lens list but **not** in the CloudWatch recommended alarms page, the
threshold is workload-specific. Say so in the finding rather than inventing a number. Those rows are
marked *(no published threshold)* below.

The Lens also asks for alarms at two levels: individual (per function, per stage) and aggregate
(per workload). Report a workload that only has one of the two as a `LOW` finding.

`DTA/EP` below is datapoints-to-alarm over evaluation periods.

---

## AWS Lambda

Lens list: `Duration`, `Errors`, `Throttles`, `ConcurrentExecutions`; `IteratorAge` for stream-based
invocations; `DeadLetterErrors` for asynchronous invocations; `ProvisionedConcurrencySpilloverInvocations`
when provisioned concurrency is enabled.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `Errors` | `FunctionName` | Sum | greater than zero, tuned to the application's error tolerance | 60 | 3/3 | `GREATER_THAN_THRESHOLD` |
| `Throttles` | `FunctionName` | Sum | greater than zero, tuned to the function's scaling requirements | 60 | 5/5 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `Duration` | `FunctionName` | p90 | **must be set below the configured function timeout** | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `ConcurrentExecutions` | `FunctionName` | Maximum | about 90% of the account's Region concurrency quota | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |
| `ClaimedAccountConcurrency` | none (account) | Maximum | about 90% of the account's Region concurrency quota (default 1,000 — confirm in Service Quotas) | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |
| `IteratorAge` | `FunctionName` | Maximum | 30,000 ms is the example in the Lambda best practices guide; tune to the stream retention period | 60 | 15/15 | `GREATER_THAN_THRESHOLD` *(no published CloudWatch threshold)* |
| `DeadLetterErrors` | `FunctionName` | Sum | 0 — any value means Lambda could not preserve a failed event | 60 | 1/1 | `GREATER_THAN_THRESHOLD` *(no published threshold)* |
| `ProvisionedConcurrencySpilloverInvocations` | `FunctionName` | Sum | 0 for a workload sized to avoid cold starts | 60 | 5/5 | `GREATER_THAN_THRESHOLD` *(no published threshold)* |

CloudWatch notes that `ClaimedAccountConcurrency` gives better visibility than `ConcurrentExecutions`
when reserved or provisioned concurrency is in use, so prefer it for the account-level alarm.

### Lambda Insights (only when the Lambda Insights extension is enabled)

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `memory_utilization` | `function_name` | Average | 90 | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |

---

## Amazon API Gateway

Lens list: `IntegrationLatency`, `Latency`, `5XXError`; for WebSocket APIs `ClientError`,
`IntegrationError`, and `ExecutionError`.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `5XXError` (REST) / `5xx` (HTTP) | `ApiName, Stage` / `ApiId, Stage` | Average | 0.05 (5% of requests) | 60 | 3/3 | `GREATER_THAN_THRESHOLD` |
| `4XXError` (REST) / `4xx` (HTTP) | `ApiName, Stage` / `ApiId, Stage` | Average | 0.05 (5% of requests) | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `Latency` | `ApiName, Stage` / `ApiId, Stage` | p90 | 2500 ms | 60 | 5/5 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `IntegrationLatency` | `ApiId, Stage` | p90 | 2000 ms | 60 | 5/5 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `Count` | `ApiName, Stage` / `ApiId, Stage` | SampleCount | baseline-dependent; only for APIs with predictable traffic | 60 | 10/10 | `LESS_THAN_THRESHOLD` |
| `ClientError` (WebSocket) | `ApiId, Stage` | Average | 0.05 | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `ExecutionError` (WebSocket) | `ApiId, Stage` | Average | 0.05 | 60 | 3/3 | `GREATER_THAN_THRESHOLD` |
| `MessageCount` (WebSocket) | `ApiId, Stage` | SampleCount | baseline-dependent | 60 | 10/10 | `LESS_THAN_THRESHOLD` |

CloudWatch recommends `IntegrationLatency` alarms for WebSocket APIs and treats them as optional for
HTTP APIs, which already have a `Latency` recommendation. Both need detailed metrics enabled to alarm
per route or per method.

---

## Amazon SQS

Lens list: `ApproximateAgeOfOldestMessage`.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `ApproximateAgeOfOldestMessage` | `QueueName` | Maximum | 50% higher than the maximum expected message processing time | 60 | 15/15 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `ApproximateNumberOfMessagesNotVisible` | `QueueName` | Average | 50% over the maximum expected in-flight count (FIFO queues cap at 20,000) | 60 | 15/15 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `ApproximateNumberOfMessagesVisible` | `QueueName` | Average | baseline-dependent backlog size | 60 | 15/15 | `GREATER_THAN_OR_EQUAL_TO_THRESHOLD` |
| `NumberOfMessagesSent` | `QueueName` | Sum | 0 — detects a producer that has stopped | 60 | 15/15 | `LESS_THAN_OR_EQUAL_TO_THRESHOLD` |

For a dead-letter queue, alarm on `ApproximateNumberOfMessagesVisible` greater than 0: in a healthy
system nothing should be sitting in the DLQ.

---

## Amazon SNS

Lens list: `NumberOfNotificationsFailed`, `NumberOfNotificationsFilteredOut-InvalidAttributes`.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `NumberOfNotificationsFailed` | `TopicName` | Sum | 0 for topics with only SQS, Lambda, or Firehose subscriptions | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `NumberOfNotificationsFilteredOut-InvalidAttributes` | `TopicName` | Sum | 0 | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `NumberOfNotificationsFilteredOut-InvalidMessageBody` | `TopicName` | Sum | 0 | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `NumberOfNotificationsRedrivenToDlq` | `TopicName` | Sum | 0 | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `NumberOfNotificationsFailedToRedriveToDlq` | `TopicName` | Sum | 0 | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `NumberOfMessagesPublished` | `TopicName` | Sum | baseline-dependent minimum | 60 | 5/5 | `LESS_THAN_THRESHOLD` |
| `NumberOfNotificationsDelivered` | `TopicName` | Sum | baseline-dependent minimum | 60 | 5/5 | `LESS_THAN_THRESHOLD` |

---

## Amazon Kinesis Data Streams

Lens list: `ReadProvisionedThroughputExceeded`, `WriteProvisionedThroughputExceeded`,
`GetRecords.IteratorAgeMilliseconds`, `PutRecord.Success`, `PutRecords.Success`, `GetRecords.Success`.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `GetRecords.IteratorAgeMilliseconds` | `StreamName` | Maximum | retention-dependent; past 50% of the retention period there is a data-loss risk | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `ReadProvisionedThroughputExceeded` | `StreamName` | Average | above the accepted throttle rate — zero is too sensitive because throttles are retried | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `WriteProvisionedThroughputExceeded` | `StreamName` | Average | as above | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `GetRecords.Success` | `StreamName` | Average | success ratio floor for the workload | 60 | 5/5 | `LESS_THAN_THRESHOLD` |
| `PutRecord.Success` | `StreamName` | Average | success ratio floor for the workload | 60 | 5/5 | `LESS_THAN_THRESHOLD` |
| `PutRecords.FailedRecords` | `StreamName` | Sum | failure count the application tolerates | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `SubscribeToShardEvent.MillisBehindLatest` | `StreamName, ConsumerName` | Average | tolerated processing delay (enhanced fan-out consumers) | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |

---

## EventBridge Scheduler

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `InvocationDroppedCount` | none | Sum | 0 | 60 | 1/1 | `GREATER_THAN_THRESHOLD` |
| `InvocationsFailedToBeSentToDeadLetterCount` | none | Sum | 0 | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `TargetErrorThrottledCount` | none | Sum | 0 | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `InvocationThrottleCount` | none | Sum | 0 | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |

CloudWatch notes that if a DLQ is correctly configured on every schedule, dropped invocations land in
the DLQ and the `InvocationDroppedCount` alarm can be skipped.

---

## Amazon DynamoDB

Lens list: `ReadThrottleEvents`, `WriteThrottleEvents`, `SystemErrors`, `ThrottledRequests`,
`UserErrors`.

| Metric | Dimensions | Statistic | Threshold | Period | DTA/EP | Comparison |
|---|---|---|---|---|---|---|
| `AccountProvisionedReadCapacityUtilization` | none | Maximum | 80 | 300 | 2/2 | `GREATER_THAN_THRESHOLD` |
| `AccountProvisionedWriteCapacityUtilization` | none | Maximum | 80 | 300 | 2/2 | `GREATER_THAN_THRESHOLD` |
| `ReadThrottleEvents` | `TableName` (and `GlobalSecondaryIndexName`) | Sum | above the accepted throttle level for the table | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `WriteThrottleEvents` | `TableName` (and `GlobalSecondaryIndexName`) | Sum | as above | 60 | 5/5 | `GREATER_THAN_THRESHOLD` |
| `SystemErrors` | `TableName` | Sum | above the accepted 5xx level | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `UserErrors` | none | Sum | 0, or higher to avoid noise | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |
| `SuccessfulRequestLatency` | `TableName, Operation` | Average | operation-dependent; singleton operations are single-digit ms on average | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |
| `ReplicationLatency` | `TableName, ReceivingRegion` | Average | over 3 minutes generally warrants investigation | 60 | 15/15 | `GREATER_THAN_THRESHOLD` |
| `AgeOfOldestUnreplicatedRecord` | `TableName, DelegatedOperation` | Maximum | desired replication delay in ms | 300 | 3/3 | `GREATER_THAN_THRESHOLD` |
| `FailedToReplicateRecordCount` | `TableName, DelegatedOperation` | Sum | 0 | 60 | 1/1 | `GREATER_THAN_THRESHOLD` |
| `ThrottledPutRecordCount` | `TableName, DelegatedOperation` | Maximum | regular excessive throttling level | 60 | 10/10 | `GREATER_THAN_THRESHOLD` |

`ThrottledRequests` appears in the Lens list but not in the CloudWatch recommended alarms page; alarm
on it above the workload's accepted level.

---

## AWS Step Functions *(Lens list only — no published CloudWatch thresholds)*

Lens list: `ExecutionThrottled`, `ExecutionsFailed`, `ExecutionsTimedOut`, `ActivitiesTimedOut`,
`LambdaFunctionsTimedOut`.

| Metric | Dimensions | Suggested statistic | Threshold |
|---|---|---|---|
| `ExecutionsFailed` | `StateMachineArn` | Sum | greater than zero, tuned to tolerance |
| `ExecutionsTimedOut` | `StateMachineArn` | Sum | greater than zero |
| `ExecutionThrottled` | `StateMachineArn` | Sum | greater than zero |
| `LambdaFunctionsTimedOut` | `StateMachineArn` | Sum | greater than zero |
| `ActivitiesTimedOut` | `StateMachineArn` | Sum | greater than zero |

State the threshold as workload-specific in the finding, and recommend a starting point based on the
observed 7-day values rather than presenting a number as an AWS recommendation.

---

## Amazon EventBridge (rules) *(Lens list only — no published CloudWatch thresholds)*

Lens list: `FailedInvocations`, `ThrottledRules`.

| Metric | Dimensions | Suggested statistic | Threshold |
|---|---|---|---|
| `FailedInvocations` | `RuleName` | Sum | 0 — a failed invocation means the target was never reached |
| `ThrottledRules` | `RuleName` | Sum | 0 |
| `DeadLetterInvocations` | `RuleName` | Sum | 0 |

---

## Creating a missing alarm

Every alarm-gap finding should carry a ready-to-run command. Template:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "lambda-checkout-processor-errors" \
  --alarm-description "Lambda errors on checkout-processor" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=checkout-processor \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 3 \
  --datapoints-to-alarm 3 \
  --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:REGION:ACCOUNT:ops-alerts
```

For a percentile threshold use `--extended-statistic p90` in place of `--statistic`:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "lambda-checkout-processor-duration-p90" \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=checkout-processor \
  --extended-statistic p90 \
  --period 60 \
  --evaluation-periods 15 \
  --datapoints-to-alarm 15 \
  --threshold 24000 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:REGION:ACCOUNT:ops-alerts
```

The `Duration` threshold above assumes a 30-second function timeout and alarms at 80% of it, which
satisfies the documented requirement to "set the threshold lower than the configured function
timeout".

Always recommend an `--alarm-actions` target. An alarm with no action is a dashboard decoration, not
an alert.
