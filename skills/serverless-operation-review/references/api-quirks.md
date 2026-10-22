# API Quirks and Error Handling Reference

How to handle the errors a review will hit, and the API responses whose obvious reading is wrong.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|-----------|
| `AccessDeniedException` / `AccessDenied` | the agent role lacks a read permission | skip that check, record it in Scope Covered, and list the missing action in the report |
| `NO_ELEVATED_ROLE_FOR_ACCOUNT` on an otherwise-permitted call | an agent-space policy restriction, not an IAM gap — observed on `lambda:GetFunctionEventInvokeConfig` | say so precisely in Scope Covered: the permission exists, the platform declined the call. Infer what you can from other evidence (`AsyncEventsDropped`, a destination's IAM policy) and label it as inferred |
| `ResourceNotFoundException` on `GetFunctionEventInvokeConfig` | no async config exists | not an error — async defaults apply (2 retries, 6-hour max age, no destination) |
| `ResourceNotFoundException` on `GetFunctionUrlConfig` | no function URL | not an error — record "no function URL" |
| `ResourceNotFoundException` on `GetPolicy` | no resource-based policy | not an error — record "no resource policy" |
| `ResourceNotFoundException` on `DescribeLogGroups` result being empty | function has never run | report INFO, skip log analysis for that function |
| `TooManyRequestsException` / `ThrottlingException` | the review is calling AWS APIs too fast | back off exponentially, reduce parallelism, and continue |
| `ValidationException` on `GetMetricData` | more than 500 metric queries in one call | split the request per resource |
| `DataUnavailableException` on Cost Explorer | Cost Explorer not enabled in the account | skip the cost section and say so |
| Empty metric result | the metric is not emitted for this configuration | not a finding — omit the row |

---

## Known API Quirks

Recorded so a review does not misread an API response. Several of these were confirmed against a live
account, and each one is a case where the obvious reading of a response is wrong.

Recorded so the review does not misread an API response:

- `lambda.GetFunctionEventInvokeConfig` throwing `ResourceNotFoundException` means **defaults are in
  effect**, not that something is broken. The defaults themselves — 2 retries, 6-hour maximum event
  age, no `OnFailure` destination — are what the reliability checks evaluate.
- `lambda.GetFunctionConcurrency` returning an empty response means the function is **unreserved**
  (it draws from the shared account pool), not that its concurrency is zero. Reserved concurrency of
  `0` is a very different thing: it throttles the function completely.
- `AWS/Lambda ClaimedAccountConcurrency` is **account-level and has no dimensions**. Do not try to
  fetch it per function.
- Percentiles need `ExtendedStatistic: p99`, not `Statistic`. Mixing them in one metric query is a
  validation error.
- Both the legacy `DeadLetterConfig.TargetArn` and the modern
  `EventInvokeConfig.DestinationConfig.OnFailure` satisfy the "async failures are captured" check.
  Prefer recommending `OnFailure` for new work, since it carries the full invocation record.
- `lambda.ListEventSourceMappings` and `lambda.ListFunctions` are paginated. An unpaginated read
  silently under-reports a large account.
- `lambda.ListEventSourceMappings` returns `MaximumRetryAttempts: -1` when the value is **unset**,
  meaning "retry until the record expires". Do not read `-1` as zero retries. `BisectBatchOnFunctionError`
  is absent entirely on SQS mappings — it is a stream-only control, so its absence there is not a
  finding.
- The REPORT log line carries a `Status` field on failure (`Status: timeout`, `Status: error`).
  Current managed runtimes may record a timeout **only** this way, with no `Task timed out` message,
  so scan for both. A `Duration` that equals the configured `Timeout` almost exactly is corroborating
  evidence.
- `Max Memory Used` can under-report on the very invocation that ran out of memory. When the language
  runtime's allocator refuses a large allocation up front — a Python `MemoryError`, for example — the
  pages are never touched. Treat log evidence as authoritative for memory failures.
- `FunctionResponseTypes: ["ReportBatchItemFailures"]` is the partial-batch-response flag. Its
  absence on a stream or SQS mapping means one bad record fails the whole batch. The API returns an
  empty list rather than null when it is unset.
- SQS `GetQueueAttributes` needs `AttributeNames=["All"]` to return `RedrivePolicy`; the default
  response omits it, which reads as "no DLQ" if you do not ask for it.
- `wafv2.GetWebACLForResource` works for REST API stages. HTTP APIs cannot associate a WAF web ACL at
  all, so absence there is a design note, not a misconfiguration.
- Lambda runtime end-of-support dates change. Treat
  `references/lambda-runtime-deprecations.md` as the source of truth and re-check it against the
  [runtime support policy](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) before
  reporting a date as fact.
