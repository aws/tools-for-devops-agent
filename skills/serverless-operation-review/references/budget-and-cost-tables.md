# Budget caps, alarm metrics and cost opportunities

## Review caps (Step 1)

| Scope given | Default cap | Selection rule when the cap binds |
|---|---|---|
| Named resources | none | review all named resources |
| Stack or tag boundary | 50 resources per family | highest 7-day `Invocations` first |
| Named Regions | 25 functions, 10 APIs, 10 state machines, 25 tables per Region | highest 7-day `Invocations` (functions), `Count` (APIs), `ExecutionsStarted` (state machines), `ConsumedReadCapacityUnits` (tables) |
| All Regions | 10 functions, 5 APIs, 5 state machines, 10 tables per Region | as above |

## Alarm metrics the Lens expects (Step 6)

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

## Cost opportunities (Step 8)

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
