# Check Catalog — Lambda Event Sources

Covers Amazon SQS, Amazon SNS, Amazon EventBridge, EventBridge Scheduler, DynamoDB Streams, and
Amazon Kinesis Data Streams as they attach to a Lambda function.

Pillar codes: **SEC** Security · **REL** Reliability · **PERF** Performance Efficiency ·
**COST** Cost Optimization · **OPS** Operational Excellence

---

## Amazon SQS

Key documented facts to reason from:

- "To allow your function time to process each batch of records, set the source queue's visibility
  timeout to at least **six times** the configuration timeout on your function."
  ([Creating and configuring an Amazon SQS event source mapping](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html))
- "Your function's timeout must be less than or equal to the queue's visibility timeout. Lambda
  validates this requirement when you create or update an event source mapping." So a queue whose
  visibility timeout is now *below* the function timeout means the queue was changed after the
  mapping was created — a real and dangerous drift condition.
- With a batch window, "We recommend setting your queue's visibility timeout to six times your
  function timeout, **plus** the value of `MaximumBatchingWindowInSeconds`."
- "We recommend setting the `maxReceiveCount` on your source queue's redrive policy to at least 5."
- Batch size over 10 requires `MaximumBatchingWindowInSeconds` of at least 1 second. FIFO queues cap
  batch size at 10; standard queues allow up to 10,000.
- "If you configure reserved concurrency on your function, set a minimum of five concurrent
  executions to reduce the chance of throttling errors."
- Maximum concurrency and Provisioned Mode are mutually exclusive.

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SQS-001 | REL | CRITICAL | Queue `VisibilityTimeout` **less than** the consuming function's `Timeout` | The queue was changed after the mapping was created. Messages become visible again while the function is still processing them, producing duplicate processing. Raise `VisibilityTimeout` immediately | Lambda SQS ESM configuration |
| SLS-SQS-002 | REL | HIGH | `VisibilityTimeout` < 6 × function `Timeout` (+ `MaximumBatchingWindowInSeconds` when a batch window is set) | Raise to the documented recommendation so Lambda has room to retry a throttled batch without the messages reappearing | Lambda SQS ESM configuration |
| SLS-SQS-003 | REL | HIGH | Source queue has no `RedrivePolicy` (no dead-letter queue) | A message that always fails is retried until it expires, silently. Create a DLQ and attach a redrive policy | Lens — Failure management; Lambda SQS error handling |
| SLS-SQS-004 | REL | MEDIUM | `RedrivePolicy.maxReceiveCount` < 5 | Raise to at least 5 so transient failures get a few retries before the message is sidelined | Lambda SQS ESM configuration |
| SLS-SQS-005 | REL | MEDIUM | `RedrivePolicy.maxReceiveCount` very high (> 100) on a queue whose consumer is failing | Poison-pill messages are being retried for a long time and holding concurrency. Lower it | Lambda SQS error handling |
| SLS-SQS-006 | REL | HIGH | Event source mapping has no `FunctionResponseTypes: ["ReportBatchItemFailures"]` | Without partial batch response, one failed message re-queues the entire batch, so already-processed messages are delivered again | Lambda SQS: "You can configure your event source mapping to use partial batch responses to return only the failed messages back to the queue"; Lens — Failure management |
| SLS-SQS-007 | REL | HIGH | DLQ `ApproximateNumberOfMessagesVisible` > 0 | Messages have failed permanently and are waiting. Investigate, fix, then redrive | SQS dead-letter queues |
| SLS-SQS-008 | REL | HIGH | `ApproximateAgeOfOldestMessage` above 50% over the maximum expected processing time | Consumers are not keeping up or a poison pill is stuck. Add consumer throughput, raise batch size, or check the DLQ configuration | CloudWatch recommended alarms — `ApproximateAgeOfOldestMessage`: "set the threshold to 50% higher than the maximum expected SQS message processing time" |
| SLS-SQS-009 | REL | MEDIUM | `ApproximateNumberOfMessagesNotVisible` sustained more than 50% above the expected in-flight count | Consumers are receiving but not deleting messages. For FIFO queues the in-flight cap is 20,000, and a backlog in one message group blocks later groups | CloudWatch recommended alarms — `ApproximateNumberOfMessagesNotVisible` |
| SLS-SQS-010 | REL | MEDIUM | `BatchSize` > 10 with `MaximumBatchingWindowInSeconds` of 0 | This configuration is invalid for standard queues — a batch size above 10 requires a batch window of at least 1 second | Lambda SQS ESM configuration |
| SLS-SQS-011 | REL | MEDIUM | Function has `ReservedConcurrentExecutions` < 5 while consuming an SQS queue | Below five concurrent executions the mapping is likely to hit throttling errors | Lambda SQS ESM configuration |
| SLS-SQS-012 | PERF | LOW | `BatchSize` of 1 on a high-volume standard queue with a very short function duration | Larger batches amortise invocation overhead and raise throughput | Lambda best practices: "Test with different batch and record sizes" |
| SLS-SQS-013 | SEC | MEDIUM | Queue has no `KmsMasterKeyId` (no server-side encryption with KMS) | Enable SSE-KMS, and grant the execution role `kms:Decrypt` | Lambda SQS permissions; SQS encryption |
| SLS-SQS-014 | REL | MEDIUM | Event source mapping `State` is `Disabled` or `Disabling` without an explanation | A disabled mapping means the queue is filling with no consumer | Lambda event source mappings |
| SLS-SQS-015 | REL | LOW | Both `ScalingConfig.MaximumConcurrency` and `ProvisionedPollerConfig` are set | These are mutually exclusive; with Provisioned Mode, concurrency is controlled by the maximum poller count | Lambda SQS ESM configuration |
| SLS-SQS-016 | OPS | MEDIUM | No CloudWatch alarm on `ApproximateAgeOfOldestMessage` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts |
| SLS-SQS-017 | OPS | MEDIUM | No alarm on DLQ depth (`ApproximateNumberOfMessagesVisible` on the DLQ) | A DLQ nobody watches is a silent data-loss queue | Lens — Failure management |

---

## Amazon SNS

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SNS-001 | REL | HIGH | Subscription to a Lambda function has no `RedrivePolicy` (no subscription DLQ) | SNS delivery failures to Lambda are lost after the retry policy is exhausted. Attach a subscription DLQ | Lens — Failure management |
| SLS-SNS-002 | REL | HIGH | `NumberOfNotificationsRedrivenToDlq` > 0 | Messages are landing in the DLQ. Investigate the failure and redrive | CloudWatch recommended alarms — threshold 0: "in a healthy system of any subscriber type, messages should not be moved to the dead-letter queue" |
| SLS-SNS-003 | REL | CRITICAL | `NumberOfNotificationsFailedToRedriveToDlq` > 0 | Messages failed processing **and** failed to reach the DLQ — that is data loss. Check the DLQ exists and SNS has permission to write to it | CloudWatch recommended alarms — threshold 0 |
| SLS-SNS-004 | REL | HIGH | `NumberOfNotificationsFailed` > 0 | For SQS, Lambda, or Firehose subscriptions the expected value is zero. Enable delivery status logging to find the failing subscriber | CloudWatch recommended alarms: "The number of notifications failed should be 0 for topics that have only SQS, Lambda or Firehose subscriptions" |
| SLS-SNS-005 | REL | MEDIUM | `NumberOfNotificationsFilteredOut-InvalidAttributes` > 0 | A publisher is sending invalid message attributes, or a subscriber filter policy is wrong | CloudWatch recommended alarms — threshold 0: "Invalid attributes are almost always a mistake by the publisher" |
| SLS-SNS-006 | SEC | MEDIUM | Topic has no `KmsMasterKeyId` | Enable SSE-KMS on the topic | SNS encryption |
| SLS-SNS-007 | OPS | MEDIUM | No alarm on `NumberOfNotificationsFailed` or `NumberOfNotificationsFilteredOut-InvalidAttributes` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts |
| SLS-SNS-008 | COST | LOW | Subscription has no `FilterPolicy` while the function discards most events in code | Filter at the subscription so you stop paying for invocations that do nothing | SNS message filtering |

---

## Amazon EventBridge (rules and buses)

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-EVB-001 | REL | HIGH | Rule target has no `DeadLetterConfig` | Events that cannot be delivered after the retry policy are discarded silently. Attach a DLQ to the target | Lens — Failure management |
| SLS-EVB-002 | REL | HIGH | `FailedInvocations` > 0 | EventBridge could not invoke the target at all. Check target permissions and existence | Lens — Metrics and alerts (alert on `FailedInvocations`) |
| SLS-EVB-003 | REL | HIGH | `ThrottledRules` > 0 | Rule invocations are being throttled — check the target's own limits and the account's invocation quota | Lens — Metrics and alerts (alert on `ThrottledRules`) |
| SLS-EVB-004 | REL | MEDIUM | Target left on the default `RetryPolicy` (maximum event age 24 hours, up to 185 attempts) for a time-sensitive event | Set `MaximumEventAgeInSeconds` to the window in which the event is still useful, so stale events go to the DLQ instead of being retried for a day | EventBridge retry policy |
| SLS-EVB-005 | REL | MEDIUM | `DeadLetterInvocations` > 0 | Events are reaching the DLQ. Investigate and replay | EventBridge DLQ |
| SLS-EVB-006 | OPS | MEDIUM | No alarm on `FailedInvocations` or `ThrottledRules` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts |
| SLS-EVB-007 | COST | LOW | Rule pattern is broad and the target function filters in code | Narrow the event pattern so undelivered events are never billed as invocations | EventBridge event patterns |
| SLS-EVB-008 | REL | LOW | Custom bus with no archive or replay configured for a workload that needs recovery of missed events | Archives allow replay after an outage or a bug fix | EventBridge archive and replay |

---

## EventBridge Scheduler

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SCH-001 | REL | HIGH | Schedule has no `DeadLetterConfig` | A dropped invocation disappears with no record | CloudWatch recommended alarms — `InvocationDroppedCount`: "Consider investigating by configuring a DLQ for the schedule" |
| SLS-SCH-002 | REL | CRITICAL | `InvocationDroppedCount` > 0 | Scheduled invocations are being dropped outright | CloudWatch recommended alarms — threshold 0 |
| SLS-SCH-003 | REL | CRITICAL | `InvocationsFailedToBeSentToDeadLetterCount` > 0 | The invocation failed and could not be preserved in the DLQ. Fix the DLQ configuration | CloudWatch recommended alarms — threshold 0 |
| SLS-SCH-004 | REL | HIGH | `TargetErrorThrottledCount` > 0 sustained | The target service is throttling. Configure a flexible time window to spread the load, or raise the target's limits | CloudWatch recommended alarms — threshold 0 |
| SLS-SCH-005 | REL | HIGH | `InvocationThrottleCount` > 0 sustained | Scheduler itself is throttling invocations. Spread the schedule with a flexible time window or raise the quota | CloudWatch recommended alarms — threshold 0 |
| SLS-SCH-006 | REL | LOW | Many schedules share the same exact minute with `FlexibleTimeWindow: OFF` | A thundering herd against the same target. Enable a flexible time window | EventBridge Scheduler flexible time windows |

---

## DynamoDB Streams and Kinesis Data Streams

Documented facts to reason from:

- Stream sources "retry the entire batch of items. Repeated errors block processing of the affected
  shard until the error is resolved or the items expire."
  ([Lens — Failure management](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/failure-management.html))
- The Lens names four controls for stream resilience: **Maximum Retry Attempts**, **Maximum Record
  Age**, **Destination on Failure**, and **Bisect Batch on Function Error**.
- Lambda best practices recommends alarming on stream `IteratorAge`, with an example threshold of
  30,000 ms.
- CloudWatch notes that if iterator age passes 50% of the stream retention period there is a risk of
  data loss through record expiry.

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-STR-001 | REL | CRITICAL | Mapping has none of `MaximumRetryAttempts`, `MaximumRecordAgeInSeconds`, `BisectBatchOnFunctionError`, or `DestinationConfig.OnFailure` | A single poison-pill record blocks the shard until the records expire. Configure the error-handling controls and an `OnFailure` destination | Lens — Failure management |
| SLS-STR-002 | REL | HIGH | No `DestinationConfig.OnFailure` on the mapping | Discarded batches leave no record of what was lost. Send failed batch metadata to an SQS queue or SNS topic | Lens — Failure management: "effectively remove poison-pill messages from the batch by sending its metadata to an Amazon SQS dead-letter queue" |
| SLS-STR-003 | REL | HIGH | `BisectBatchOnFunctionError` is false | Without bisection, one bad record fails the whole batch on every retry. Enabling it isolates the offending record | Lens — Failure management |
| SLS-STR-004 | REL | HIGH | No `FunctionResponseTypes: ["ReportBatchItemFailures"]` | Enable partial batch response so only failed records are retried | Lambda best practices: "Enable partial batch response for stream processing" |
| SLS-STR-005 | REL | MEDIUM | `MaximumRetryAttempts` is unset (retry until expiry) | Bound the retries so the shard cannot stall for the full retention period | Lens — Failure management |
| SLS-STR-006 | REL | MEDIUM | `MaximumRecordAgeInSeconds` is unset | Bound record age so stale records are discarded to the destination instead of blocking the shard | Lens — Failure management |
| SLS-STR-007 | REL | CRITICAL | `IteratorAge` exceeds 50% of the stream retention period | Records are at risk of expiring unprocessed — that is data loss. As an immediate mitigation raise the retention period while the consumer is fixed | CloudWatch recommended alarms — `GetRecords.IteratorAgeMilliseconds`: "If an iterator's age passes 50% of the retention period… there is a risk for data loss" |
| SLS-STR-008 | REL | HIGH | `IteratorAge` sustained above 30,000 ms (or a workload-specific target) | The consumer is falling behind. Add shards, raise `ParallelizationFactor`, or make the handler faster | Lambda best practices: "configure a CloudWatch alarm with a maximum setting to 30000 (30 seconds)" |
| SLS-STR-009 | PERF | MEDIUM | Kinesis `ReadProvisionedThroughputExceeded` > 0 | Consumers are throttled. Add shards, or register consumers with enhanced fan-out so they do not share the `GetRecords` limit | CloudWatch recommended alarms; Lambda best practices |
| SLS-STR-010 | PERF | MEDIUM | Kinesis `WriteProvisionedThroughputExceeded` > 0 | Producers are throttled. Add shards and check the partition key distribution for a hot shard | CloudWatch recommended alarms; Lambda best practices: "make sure you have picked a good partition key" |
| SLS-STR-011 | PERF | LOW | `ParallelizationFactor` is 1 on a lagging stream where record order per partition key allows concurrency | Raising the parallelization factor processes more batches per shard concurrently | Lambda stream scaling |
| SLS-STR-012 | REL | MEDIUM | DynamoDB Streams source with `StreamViewType` that does not carry what the consumer needs (for example `KEYS_ONLY` where the handler expects images) | Align the view type with the handler's requirement | DynamoDB Streams |
| SLS-STR-013 | OPS | MEDIUM | No alarm on `IteratorAge` (Lambda) or `GetRecords.IteratorAgeMilliseconds` (Kinesis) | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts; Lambda best practices |
| SLS-STR-014 | OPS | MEDIUM | No alarm on `PutRecord.Success` / `GetRecords.Success` for a Kinesis source | The Lens names both for stream workloads | Lens — Metrics and alerts |
| SLS-STR-015 | PERF | LOW | Kinesis stream in provisioned mode with consistently low utilisation, or on-demand with steady predictable throughput | Match the capacity mode to the traffic shape | Kinesis capacity modes |
| SLS-STR-016 | REL | LOW | Handler performs non-atomic batch operations (`PutRecords`, `BatchWriteItem`) — cannot be verified from configuration | These return success when at least one record succeeded. The handler must inspect the response and deal with partial failures programmatically | Lens — Failure management: "Always inspect the response when using such operations" |

---

## Cross-cutting event source checks

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-ESM-001 | REL | HIGH | A function has an event source mapping whose `State` is `Disabled`, and the source is still receiving traffic | The source is accumulating a backlog with no consumer | Lambda event source mappings |
| SLS-ESM-002 | REL | MEDIUM | `LastProcessingResult` on the mapping reports a persistent error (for example `PROBLEM: Function call failed`) | Read the mapping's last processing result before assuming the function itself is healthy | Lambda event source mappings |
| SLS-ESM-003 | REL | LOW | Filter criteria are absent on a high-volume source where the handler immediately discards most events | Move the filter into the event source mapping so Lambda is not invoked for events it will drop | Lambda event filtering |
| SLS-ESM-004 | OPS | LOW | `MaximumBatchingWindowInSeconds` is 0 on a low-traffic queue or stream | A batching window reduces invocation count on sparse traffic. Note that with a batch window on a low-traffic SQS queue Lambda may wait up to 20 seconds before invoking | Lambda batching behaviour |

---

## Remediation snippets

### Correct an SQS visibility timeout

```bash
# Recommended: 6 x function timeout, plus the batch window when one is configured.
# Example: 30 s function timeout, 0 s batch window -> 180 s
aws sqs set-queue-attributes \
  --queue-url https://sqs.REGION.amazonaws.com/ACCOUNT/orders \
  --attributes VisibilityTimeout=180
```

### Attach a dead-letter queue with a sensible receive count

```yaml
Resources:
  OrdersQueue:
    Type: AWS::SQS::Queue
    Properties:
      VisibilityTimeout: 180
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt OrdersDLQ.Arn
        maxReceiveCount: 5
  OrdersDLQ:
    Type: AWS::SQS::Queue
    Properties:
      MessageRetentionPeriod: 1209600   # 14 days, the maximum
```

### Enable partial batch response

```bash
aws lambda update-event-source-mapping \
  --uuid a1b2c3d4-5678-90ab-cdef-EXAMPLE11111 \
  --function-response-types ReportBatchItemFailures
```

The handler must also return the failed message identifiers:

```json
{ "batchItemFailures": [ { "itemIdentifier": "059f36b4-87a3-44ab-83d2-661975830a7d" } ] }
```

### Harden a stream event source mapping

```bash
aws lambda update-event-source-mapping \
  --uuid a1b2c3d4-5678-90ab-cdef-EXAMPLE11111 \
  --maximum-retry-attempts 5 \
  --maximum-record-age-in-seconds 3600 \
  --bisect-batch-on-function-error \
  --function-response-types ReportBatchItemFailures \
  --destination-config '{"OnFailure":{"Destination":"arn:aws:sqs:REGION:ACCOUNT:stream-failures"}}'
```

### Add a DLQ to an EventBridge rule target

```yaml
Targets:
  - Id: ProcessOrder
    Arn: !GetAtt OrderProcessor.Arn
    DeadLetterConfig:
      Arn: !GetAtt EventBridgeDLQ.Arn
    RetryPolicy:
      MaximumRetryAttempts: 10
      MaximumEventAgeInSeconds: 3600
```
