# Configuration Collection Reference

Step 3 of `SKILL.md` in detail: the exact API calls per resource family, and the fields each one
contributes to a check. Every field listed here feeds at least one row in the check catalogs.

Collect per resource, and skip a family that is not in scope.

---

Collect per resource. Every field listed here feeds at least one check in `references/`.

## 3.1 Lambda functions

```
lambda.GetFunctionConfiguration         # or reuse ListFunctions output
lambda.GetFunctionConcurrency           # reserved concurrency
lambda.GetFunctionEventInvokeConfig     # async retries, max age, OnFailure/OnSuccess destinations
lambda.ListProvisionedConcurrencyConfigs
lambda.ListAliases
lambda.ListVersionsByFunction           # only if version sprawl or alias routing is in question
lambda.GetFunctionUrlConfig             # per function; AuthType and CORS
lambda.GetPolicy                        # resource-based policy — principals
lambda.ListTags
```

Capture per function:

- `Runtime`, `PackageType`, `Architectures`, `MemorySize`, `Timeout`, `EphemeralStorage`
- `Handler`, `CodeSize`, `Layers`, `LoggingConfig` (`LogFormat`, `LogGroup`, `ApplicationLogLevel`)
- `Environment.Variables` **key names only**, plus `KMSKeyArn` presence
- `VpcConfig` (subnets, security groups), `DeadLetterConfig.TargetArn`
- `TracingConfig.Mode`, `SnapStart`, `CodeSigningConfigArn`, `Role`
- `ReservedConcurrentExecutions` (absent means unreserved), provisioned concurrency per alias
- `State`, `LastUpdateStatus`, `LastModified`
- Tags, specifically the operational set `Environment`, `Owner`, `Runbook`, `OnCall`

## 3.2 Event sources

For each event source mapping from Step 2 and each async trigger:

```
sqs.GetQueueAttributes             # AttributeNames=All → RedrivePolicy, VisibilityTimeout,
                                   #   ApproximateNumberOfMessages, KmsMasterKeyId
sns.ListSubscriptionsByTopic       # subscriptions pointing at the function
sns.GetSubscriptionAttributes      # RedrivePolicy (subscription DLQ), FilterPolicy
sns.GetTopicAttributes             # KmsMasterKeyId
events.ListRuleNamesByTarget       # EventBridge rules targeting the function
events.ListTargetsByRule           # DeadLetterConfig, RetryPolicy per target
scheduler.ListSchedules            # EventBridge Scheduler
scheduler.GetSchedule              # DeadLetterConfig, RetryPolicy, FlexibleTimeWindow
kinesis.DescribeStreamSummary      # RetentionPeriodHours, shard count, StreamModeDetails
dynamodb.DescribeTable             # StreamSpecification for stream sources
```

Capture per event source mapping: `BatchSize`, `MaximumBatchingWindowInSeconds`,
`MaximumRetryAttempts`, `MaximumRecordAgeInSeconds`, `BisectBatchOnFunctionError`,
`FunctionResponseTypes`, `ParallelizationFactor`, `FilterCriteria`, `DestinationConfig.OnFailure`,
`ScalingConfig.MaximumConcurrency`, `StartingPosition`, `State`.

The single most important cross-check in this step: **SQS queue `VisibilityTimeout` against the
consuming function's `Timeout`**. See `references/checks-event-sources.md` — this is a CRITICAL
finding when the queue timeout is lower.

## 3.3 API Gateway

```
apigateway.GetRestApis / GetStages / GetMethod   # REST: per stage and per method
apigateway.GetUsagePlans                        # throttling + quota per API key
apigateway.GetAuthorizers
apigateway.GetDomainNames                       # mutualTlsAuthentication
apigatewayv2.GetApis / GetStages / GetRoutes    # HTTP + WebSocket
apigatewayv2.GetAuthorizers
wafv2.GetWebACLForResource                      # REST stages only; HTTP APIs cannot use WAF
```

Capture: `endpointConfiguration.types`, stage `throttlingRateLimit`/`throttlingBurstLimit`,
`cachingEnabled` and `cacheDataEncrypted`, `accessLogSettings`, `methodSettings` logging level and
`dataTraceEnabled`, `tracingEnabled`, `defaultRouteSettings` (HTTP), `disableExecuteApiEndpoint`,
authorizer type per route/method, `apiKeyRequired`, WAF association, and `minimumCompressionSize`.

Detail in `references/checks-apigateway.md`.

## 3.4 Step Functions

```
states.DescribeStateMachine       # definition, roleArn, loggingConfiguration, tracingConfiguration
states.ListExecutions             # statusFilter=FAILED / TIMED_OUT, last 7 days, MaxResults small
```

Parse the ASL `definition` JSON for: `Retry` and `Catch` on every `Task` state, `TimeoutSeconds` (or
`TimeoutSecondsPath`) on task states and at the top level, `HeartbeatSeconds` on activity tasks,
`MaxConcurrency` on `Map` states, and `.waitForTaskToken` patterns without a timeout.

Detail in `references/checks-stepfunctions.md`.

## 3.5 DynamoDB

```
dynamodb.DescribeTable                        # capacity mode, GSIs, streams, SSE, TTL-adjacent
dynamodb.DescribeContinuousBackups            # PITR status
dynamodb.DescribeTimeToLive
dynamodb.ListTagsOfResource
application-autoscaling.DescribeScalableTargets   # PROVISIONED tables only
backup.ListRecoveryPointsByResource           # optional; AWS Backup coverage
```

Capture: `BillingModeSummary`, `ProvisionedThroughput`, `TableStatus`, `DeletionProtectionEnabled`,
`SSEDescription`, `StreamSpecification`, GSI list with per-index throughput, `GlobalTableVersion` /
replicas, `TableClassSummary`, PITR status, TTL status.

Detail in `references/checks-dynamodb.md`.
