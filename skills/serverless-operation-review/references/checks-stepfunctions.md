# Check Catalog — AWS Step Functions

Covers state machines, their logging and tracing configuration, and the Amazon States Language (ASL)
definition returned by `states:DescribeStateMachine`.

Pillar codes: **SEC** Security · **REL** Reliability · **PERF** Performance Efficiency ·
**COST** Cost Optimization · **OPS** Operational Excellence

Type differences that change what counts as a finding:

| Aspect | Standard | Express |
|---|---|---|
| Execution history | Recorded and queryable for 90 days | Sent to CloudWatch Logs only |
| Execution semantics | Exactly-once | At-least-once |
| Maximum duration | 1 year | 5 minutes |
| Billing | Per state transition | Per request plus duration and memory |
| `ListExecutions` visibility | Yes | Only through CloudWatch Logs |

The Serverless Applications Lens is explicit about choosing between them: "For short-running
synchronous and asynchronous high-volume workloads, use Step Functions - Sync Express. If you need to
automate long-running workflows and want to have additional durability and audit go with Step
Functions Standard."

---

## Reliability — error handling in the definition

The Lens recommends using Step Functions specifically to remove hand-rolled retry logic: "Whenever
possible, use Step Functions to minimize the amount of custom try/catch, back-off, and retry logic
within your Serverless applications." A state machine with no `Retry` or `Catch` gives up that
benefit.

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SFN-001 | REL | HIGH | A `Task` state that calls an external service has no `Retry` array | Transient failures fail the whole execution. Add a `Retry` with `IntervalSeconds`, `MaxAttempts`, and `BackoffRate`, and include `States.TaskFailed`, `States.Timeout`, and the service's throttling error | Lens — Failure management; Step Functions error handling |
| SLS-SFN-002 | REL | HIGH | No `Catch` anywhere in the definition and no terminal `Fail` handling path | An unhandled error ends the execution with no compensating action and no record beyond the execution history. Add `Catch` blocks routing to a failure path — the Lens shows a state machine with a DLQ step | Lens — Failure management (Figure 20: "Step Functions state machine with DLQ step") |
| SLS-SFN-003 | REL | CRITICAL | A `Task` state has neither `TimeoutSeconds` nor `TimeoutSecondsPath`, and the integration pattern is `.waitForTaskToken` | A task token that is never returned holds the execution open indefinitely — for a Standard workflow, up to a year. Always set a timeout on callback tasks | Step Functions task timeouts and callback pattern |
| SLS-SFN-004 | REL | HIGH | A `Task` state has no `TimeoutSeconds` on a non-callback integration | Without a task timeout the state waits on the service default, which can be far longer than the business need | Step Functions task timeouts |
| SLS-SFN-005 | REL | MEDIUM | State machine definition has no top-level `TimeoutSeconds` | Bound the whole execution so a stalled workflow cannot run indefinitely | Step Functions state machine timeouts |
| SLS-SFN-006 | REL | MEDIUM | An `Activity` task has no `HeartbeatSeconds` | Without heartbeats a dead worker is only detected at the task timeout | Step Functions activities |
| SLS-SFN-007 | REL | HIGH | `ExecutionsFailed` > 0 over the window | Read the failure cause from the execution history (Standard) or CloudWatch Logs (Express) and fix the underlying error rather than only widening retries | Lens — Metrics and alerts (alert on `ExecutionsFailed`) |
| SLS-SFN-008 | REL | HIGH | `ExecutionsTimedOut` > 0 | Executions are hitting a timeout. Determine whether the timeout is too tight or a downstream is hanging | Lens — Metrics and alerts (alert on `ExecutionsTimedOut`) |
| SLS-SFN-009 | REL | HIGH | `ExecutionThrottled` > 0 | State transitions or `StartExecution` calls are being throttled. Check the `StateTransition` and `StartExecution` quotas, and add backoff at the caller | Lens — Metrics and alerts (alert on `ExecutionThrottled`) |
| SLS-SFN-010 | REL | MEDIUM | `LambdaFunctionsTimedOut` > 0 | A Lambda task is timing out inside the workflow. Correlate with that function's `Duration` p99 against its `Timeout` | Lens — Metrics and alerts (alert on `LambdaFunctionsTimedOut`) |
| SLS-SFN-011 | REL | MEDIUM | `ActivitiesTimedOut` > 0 | Activity workers are not completing or not heartbeating | Lens — Metrics and alerts (alert on `ActivitiesTimedOut`) |
| SLS-SFN-012 | REL | MEDIUM | `Retry` on a Lambda task does not include the Lambda transient errors (`Lambda.ServiceException`, `Lambda.AWSLambdaException`, `Lambda.SdkClientException`, `Lambda.TooManyRequestsException`) | These are the retryable Lambda invocation errors; omitting them turns a transient throttle into a failed execution | Step Functions error handling for Lambda |
| SLS-SFN-013 | REL | MEDIUM | A transaction-shaped workflow (multiple writes across services) with no compensating path | The Lens recommends the Saga pattern implemented as a state machine so failed transactions roll back | Lens — Failure management (Figure 21: "Step Functions state machine Saga pattern") |
| SLS-SFN-014 | REL | LOW | `Map` state with no `MaxConcurrency` | Unbounded fan-out can overwhelm the downstream and exhaust Lambda concurrency. Set `MaxConcurrency` deliberately | Step Functions Map state |
| SLS-SFN-015 | REL | LOW | Express workflow used where the workload needs exactly-once semantics or an auditable history | Express is at-least-once with no queryable execution history. Use Standard, or make every task idempotent | Lens — Failure management; Step Functions workflow types |

## Operational excellence

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SFN-030 | OPS | HIGH | `loggingConfiguration.level` is `OFF` | For Standard workflows this removes the CloudWatch Logs record; for Express workflows it removes the **only** record of what happened, since Express does not retain execution history. Set `ERROR` at minimum, `ALL` for Express | Step Functions logging; Lens — Centralized and structured logging |
| SLS-SFN-031 | OPS | MEDIUM | `loggingConfiguration.includeExecutionData` is `false` where debugging requires the payload | Enable it deliberately, and only where the payload contains no sensitive data | Step Functions logging |
| SLS-SFN-032 | SEC | MEDIUM | `includeExecutionData` is `true` on a workflow handling personal or credential data | Execution input and output are written to CloudWatch Logs. Disable it, or redact upstream | Step Functions logging |
| SLS-SFN-033 | OPS | MEDIUM | `tracingConfiguration.enabled` is `false` | Enable X-Ray so end-to-end latency across the workflow and its integrations is attributable | Lens — Distributed tracing |
| SLS-SFN-034 | OPS | MEDIUM | No alarm on `ExecutionsFailed` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts |
| SLS-SFN-035 | OPS | MEDIUM | No alarm on `ExecutionsTimedOut` | as above | Lens — Metrics and alerts |
| SLS-SFN-036 | OPS | MEDIUM | No alarm on `ExecutionThrottled` | as above | Lens — Metrics and alerts |
| SLS-SFN-037 | OPS | MEDIUM | No alarm on `LambdaFunctionsTimedOut` or `ActivitiesTimedOut` where the workflow uses those integrations | as above | Lens — Metrics and alerts |
| SLS-SFN-038 | OPS | LOW | Log group for the state machine has no retention policy | Set retention; `ALL`-level logging on a high-volume Express workflow is a significant ingestion cost | CloudWatch Logs retention |
| SLS-SFN-039 | OPS | LOW | Missing operational tags — `Environment`, `Owner`, `Runbook`, `OnCall` | Tag for ownership routing and cost allocation | Well-Architected OPS |
| SLS-SFN-040 | OPS | LOW | State machine definition is edited in the console rather than deployed from IaC (no `CloudFormation`/`SAM`/CDK stack ownership evident) | Console-edited workflows drift and cannot be reviewed. Move to IaC | Well-Architected OPS |

## Security

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SFN-050 | SEC | CRITICAL | Execution role grants `AdministratorAccess` or `"Action": "*"` on `"Resource": "*"` | Scope to the specific integrations the workflow invokes | IAM best practices |
| SLS-SFN-051 | SEC | HIGH | Execution role grants `lambda:InvokeFunction` on `Resource: "*"` | Scope to the specific function ARNs the workflow calls | Step Functions IAM |
| SLS-SFN-052 | SEC | MEDIUM | State machine has no `encryptionConfiguration` using a customer-managed KMS key, for a workflow handling regulated data | Customer-managed key encryption gives key-policy control and an audit trail over execution data | Step Functions data encryption |
| SLS-SFN-053 | SEC | LOW | Definition embeds credentials, tokens, or endpoint secrets as literal values | Read secrets from Secrets Manager or SSM in a task instead. **Report only that a literal appears and in which state — never the value** | Step Functions best practices |

## Performance and cost

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-SFN-070 | COST | MEDIUM | Standard workflow with high `ExecutionsStarted` and short `ExecutionTime` (well under 5 minutes) | Standard bills per state transition, so a short high-volume workflow is usually cheaper on Express. Confirm the workload tolerates at-least-once semantics first | Lens — Failure management: "For short-running synchronous and asynchronous high-volume workloads, use Step Functions - Sync Express"; Step Functions pricing |
| SLS-SFN-071 | COST | LOW | Polling loop implemented with a `Wait` state of a few seconds inside a Standard workflow | Each cycle costs state transitions. Widen the wait interval, or replace polling with a callback (`.waitForTaskToken`) | Step Functions pricing |
| SLS-SFN-072 | PERF | LOW | Sequential `Task` states with no data dependency between them | Use `Parallel` or `Map` to shorten wall-clock duration | Step Functions Parallel state |
| SLS-SFN-073 | PERF | LOW | Workflow passes large payloads between states (approaching the 256 KB state payload quota) | Pass a pointer to S3 instead of the payload itself | Step Functions quotas |
| SLS-SFN-074 | PERF | LOW | `ExecutionTime` p99 close to the workflow's `TimeoutSeconds` | Little headroom before executions start timing out | Step Functions metrics |

---

## Remediation snippets

### Add retry and catch to a Lambda task

```json
{
  "ProcessOrder": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke",
    "Parameters": { "FunctionName": "order-processor", "Payload.$": "$" },
    "TimeoutSeconds": 30,
    "Retry": [
      {
        "ErrorEquals": [
          "Lambda.ServiceException",
          "Lambda.AWSLambdaException",
          "Lambda.SdkClientException",
          "Lambda.TooManyRequestsException"
        ],
        "IntervalSeconds": 1,
        "MaxAttempts": 3,
        "BackoffRate": 2
      },
      {
        "ErrorEquals": ["States.Timeout"],
        "IntervalSeconds": 5,
        "MaxAttempts": 2,
        "BackoffRate": 2
      }
    ],
    "Catch": [
      {
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "SendToFailureQueue"
      }
    ],
    "Next": "Success"
  },
  "SendToFailureQueue": {
    "Type": "Task",
    "Resource": "arn:aws:states:::sqs:sendMessage",
    "Parameters": {
      "QueueUrl": "https://sqs.REGION.amazonaws.com/ACCOUNT/workflow-failures",
      "MessageBody.$": "$"
    },
    "Next": "Fail"
  }
}
```

### Bound a callback task

```json
{
  "WaitForApproval": {
    "Type": "Task",
    "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
    "TimeoutSeconds": 86400,
    "HeartbeatSeconds": 3600,
    "Parameters": {
      "FunctionName": "request-approval",
      "Payload": { "taskToken.$": "$$.Task.Token" }
    },
    "Next": "Continue"
  }
}
```

### Enable logging and tracing

```bash
aws stepfunctions update-state-machine \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:order-saga \
  --tracing-configuration enabled=true \
  --logging-configuration '{
    "level": "ERROR",
    "includeExecutionData": false,
    "destinations": [{
      "cloudWatchLogsLogGroup": {
        "logGroupArn": "arn:aws:logs:REGION:ACCOUNT:log-group:/aws/vendedlogs/states/order-saga:*"
      }
    }]
  }'
```

SAM equivalent:

```yaml
Resources:
  OrderSaga:
    Type: AWS::Serverless::StateMachine
    Properties:
      Type: STANDARD
      Tracing:
        Enabled: true
      Logging:
        Level: ERROR
        IncludeExecutionData: false
        Destinations:
          - CloudWatchLogsLogGroup:
              LogGroupArn: !GetAtt SagaLogGroup.Arn
```
