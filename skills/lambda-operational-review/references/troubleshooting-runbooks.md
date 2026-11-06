# Lambda Troubleshooting Runbooks

Decision-tree runbooks for incident-mode investigations. Use these when the user
reports a symptom ("investigate errors in X", "why is X throttling / timing
out"). All steps are read-only: read metrics and logs, never invoke the function.

Log source: the function's log group `/aws/lambda/<function-name>`. Query with
`logs.FilterLogEvents` for a keyword scan, or `logs.StartQuery` (CloudWatch Logs
Insights) for aggregation. Always scope to the incident time window.

## Runbook A: Elevated Errors

1. Confirm from metrics: `Errors` and error rate over the window; find the onset
   time and whether it correlates with a `LastModified` (deploy) time.
2. Classify the failure from logs:

| Log signature | Likely cause | Remediation |
|---|---|---|
| `Task timed out after N seconds` | Timeout — slow downstream or under-memoried | See Runbook C |
| `errorType` / unhandled exception + stack trace | Code/logic error | Fix code; check if tied to a recent deploy |
| `Runtime.ImportModuleError` / `Unable to import module` | Missing dependency / bad package | Fix deployment package or layer |
| `AccessDenied` / `not authorized to perform` | Execution role missing a permission | Scope-add the specific action to the role |
| `ThrottlingException` / `Rate exceeded` (downstream) | Downstream service throttling | Add retry/backoff; raise downstream limits |
| `ConnectionError` / `ETIMEDOUT` / `ENOTFOUND` | Network/VPC/DNS or downstream down | See Runbook D (VPC) or check downstream health |
| `OutOfMemory` / `Runtime exited ... signal: killed` | Memory exhaustion | Increase memory (dimension: performance) |
| `Process exited before completing request` | Crash / native fault | Inspect init and native deps |

3. Check whether errors land in a DLQ / on-failure destination
   (`DeadLetterErrors`, `DestinationDeliveryFailures`). If none is configured,
   flag the missing DLQ as a HIGH reliability finding.

## Runbook B: Throttling

1. From metrics: confirm `Throttles` > 0 and the throttle rate.
2. Determine the ceiling:
   - `GetFunctionConcurrency` — does the function have reserved concurrency that
     is too low for its traffic?
   - `GetAccountSettings` — is account `ConcurrentExecutions` near
     `AccountLimit.ConcurrentExecutions`?
   - Is another function's reserved concurrency starving the unreserved pool
     (`UnreservedConcurrentExecutions` low)?
3. Remediation options (recommend, do not apply):
   - Raise the function's reserved concurrency (if the account pool allows).
   - Request an account concurrency quota increase.
   - Rebalance reserved concurrency across functions.
   - For spiky sync traffic, add provisioned concurrency to reduce burst cold
     starts (does not raise the throttle ceiling but smooths latency).

## Runbook C: Timeouts

1. From metrics: `Duration` p95/Maximum vs configured `Timeout`; count of
   `Task timed out` log lines.
2. Diagnose the slow segment from logs (downstream call latency, retries, cold
   init). Correlate with `InitDuration` if timeouts cluster on cold starts.
3. Remediation options:
   - Optimize the slow downstream call or add a client timeout shorter than the
     Lambda timeout so it fails fast with a useful error.
   - Increase memory (more CPU) if the work is compute-bound.
   - Raise the Lambda timeout only if the workload legitimately needs longer and
     the invoking path (e.g. API Gateway 29s limit) allows it.

## Runbook D: VPC / Networking Errors

1. Confirm the function has a `VpcConfig`.
2. Common causes: no route to the internet / target (missing NAT for public
   endpoints), security group blocking egress, subnet IP exhaustion for ENIs,
   DNS resolution failure.
3. Read-only checks: subnet free IP count, security group egress rules, whether
   the target is reachable via a VPC endpoint. Recommend the fix; if DNS
   resolution is the suspected root cause, hand off to the
   `aws-vpc-dns-investigation` skill.

## Runbook E: Cold-Start Latency

1. From metrics: `InitDuration` frequency and p95 relative to `Invocations`.
2. Causes: heavy initialization, large dependencies/package, VPC ENI setup,
   Java/.NET runtime init.
3. Remediation options: provisioned concurrency for predictable latency,
   SnapStart (supported runtimes), trim dependencies, move heavy work out of the
   handler init path, prefer arm64 for cost while tuning.

## Runbook F: Stream Consumer Lag (Kinesis / DynamoDB Streams)

1. From metrics: `IteratorAge` rising indicates the consumer is behind.
2. Causes: slow per-record processing, too-small parallelization, poison records
   blocking a shard.
3. Remediation options: increase `ParallelizationFactor`, reduce per-record work
   or raise memory, configure `BisectBatchOnFunctionError` and a failure
   destination so poison records don't block the shard, tune `BatchSize`.
