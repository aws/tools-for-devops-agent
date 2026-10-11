# Lambda Best-Practices Checklist

Each item maps to a review dimension. The **Signal** column is the exact API
field or metric that decides the finding. Severity is a starting point — raise
one level for production-tagged functions on a critical path.

## 1. Configuration & Runtime

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Runtime supported | `Runtime` is deprecated (e.g. nodejs14.x, python3.7, go1.x, dotnetcore*) | Deprecated runtime stops receiving patches/updates; migrate to a supported runtime | HIGH |
| Runtime nearing EOL | Runtime deprecation date < 90 days out | Plan runtime upgrade before end of support | MEDIUM |
| Timeout appropriate | `Timeout == 900` (max) for a synchronous/API path | Overlong timeout hides hangs and inflates cost on failure; set to p99 duration + margin | MEDIUM |
| Timeout not too tight | `Duration` p95 > 80% of `Timeout` | Requests risk timing out; raise timeout or optimize | HIGH |
| Ephemeral storage sized | `/tmp` (`EphemeralStorage`) default 512 MB but workload writes more | Sized-down `/tmp` causing failures; increase up to 10240 MB | MEDIUM |
| Code package lean | Deployment package near 250 MB unzipped limit | Large package slows cold start/deploys; trim deps or use layers/container image | LOW |
| Layer count reasonable | > 5 layers | Layer sprawl complicates cold start and ops; consolidate | LOW |

## 2. Reliability

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Async DLQ / on-failure destination | Async-invoked function with no `DeadLetterConfig` and no on-failure destination | Failed async events silently dropped after retries; add a DLQ or destination | HIGH |
| Event source error handling | SQS/Kinesis/DDB mapping without DLQ / `BisectBatchOnFunctionError` / max-retry | Poison messages block the shard/queue; configure failure handling | HIGH |
| Sensible batch size | Event source `BatchSize` very large with tight timeout | Batch cannot finish before timeout; reduce batch or raise timeout | MEDIUM |
| Idempotency for at-least-once | Kinesis/SQS/DDB source (at-least-once delivery) | Duplicate processing risk; ensure handler is idempotent | MEDIUM |
| Error rate healthy | `Errors / Invocations` > 1% sustained | Elevated error rate; investigate via logs (see runbooks) | HIGH |
| DLQ not filling | `DeadLetterErrors` > 0 or DLQ depth growing | Failures accumulating unprocessed; triage | HIGH |

## 3. Performance

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Cold-start rate low | High `InitDuration` frequency relative to invocations on a latency-sensitive path | Cold starts hurting tail latency; consider provisioned concurrency or SnapStart | MEDIUM |
| Init duration reasonable | `InitDuration` p95 high (heavy init / large deps) | Slow init; lazy-load, trim deps, move work out of handler init | MEDIUM |
| Memory right-sized (under) | `Duration` high and flat while memory low; CPU-bound | Under-memoried (CPU scales with memory); increase memory to cut duration | MEDIUM |
| Memory right-sized (over) | `Duration` flat above a memory level; low `MaxMemoryUsed` | Over-provisioned memory; lower to the knee of the curve | MEDIUM |
| SnapStart / provisioned concurrency | Latency-sensitive Java/.NET or spiky traffic with cold-start pain | Evaluate SnapStart (Java/others) or provisioned concurrency | LOW |
| VPC cold-start awareness | VPC-attached function on a latency path | Note VPC ENI/cold-start considerations; ensure adequate subnet IPs | LOW |

## 4. Concurrency & Throttling

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| No sustained throttling | `Throttles` > 0 sustained | Requests rejected; raise account/reserved concurrency or add reserved concurrency | HIGH |
| Account concurrency headroom | `ConcurrentExecutions` near account limit | Approaching regional limit; request a quota increase | HIGH |
| Reserved concurrency not starving others | One function reserves most of the account pool | Other functions may throttle; rebalance reservations | MEDIUM |
| Provisioned concurrency utilized | `ProvisionedConcurrencyUtilization` very low | Paying for idle warm capacity; reduce or remove | MEDIUM |
| Provisioned concurrency sufficient | `ProvisionedConcurrencySpilloverInvocations` > 0 | Spilling to on-demand (cold starts); raise provisioned level | MEDIUM |

## 5. Security

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Execution role least privilege | Role policy contains `"*"` action or resource | Over-privileged function role; scope to least privilege | HIGH |
| No plaintext secrets | Env vars look like keys/passwords/tokens in plaintext | Secrets in config; move to Secrets Manager / SSM Parameter Store | HIGH |
| Env vars encrypted with CMK | No `KMSKeyArn` on sensitive env vars (AWS-managed key only) | Use a customer-managed KMS key for sensitive env vars | LOW |
| Function URL auth | `FunctionUrlConfig.AuthType == "NONE"` not intentional | Publicly invokable function URL; require `AWS_IAM` or front with auth | CRITICAL |
| Resource policy scoped | `GetPolicy` grants invoke to `*` principal without condition | Overly broad invoke permission; scope principal/source | HIGH |
| VPC / SG scoped | Security group overly permissive egress/ingress | Tighten Lambda ENI security group | LOW |

## 6. Cost

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Memory not over-provisioned | Over-memoried per dimension 3 | Paying for unused memory-seconds; right-size | MEDIUM |
| Idle provisioned concurrency | Low utilization (dimension 4) | Warm capacity billed while idle; reduce | MEDIUM |
| arm64 candidacy | `Architectures == ["x86_64"]` with no native-binary constraint | Graviton (arm64) is ~20% cheaper; evaluate migration | LOW |
| Retry storm | High `Errors` driving retries and re-invocations | Failures multiply cost; fix root cause | MEDIUM |
| Log retention set | Log group retention = "Never expire" | Unbounded CloudWatch Logs cost; set a retention period | LOW |

## 7. Observability

| Check | Signal | Finding if violated | Severity |
|---|---|---|---|
| Tracing enabled | `TracingConfig.Mode == "PassThrough"` on a latency-sensitive function | No active X-Ray tracing; enable `Active` | LOW |
| Log retention configured | No retention on `/aws/lambda/<name>` | Logs never expire (cost) or missing policy; set retention | LOW |
| Alarms present | No alarm on `Errors` / `Throttles` / `Duration` | No proactive alerting; add alarms (see thresholds ref) | MEDIUM |
| Structured logging | Free-text logs, no correlation IDs | Harder incident triage; adopt structured/JSON logging | LOW |
