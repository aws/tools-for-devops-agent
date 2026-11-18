# Report Template — Serverless Operational Review

Produce the artifact in exactly this section order. It matches the other operation-review skills in
this repository so reports are comparable across services.

Artifact naming:

- One to three named resources — one artifact per resource:
  `serverless-review-<resource-name>-<YYYY-MM-DD>.md`
- Anything wider (stack, tag, Region, account) — one consolidated artifact:
  `serverless-review-<scope-label>-<YYYY-MM-DD>.md`

Rules for the whole report:

- Every finding carries the observed value, not just the conclusion. "No DLQ configured" is a claim;
  "`DeadLetterConfig` absent and `EventInvokeConfig.DestinationConfig.OnFailure` absent" is evidence.
- Mark every derived cost figure **(estimated)**.
- Never print environment variable values, secrets, or anything credential-shaped. Key names only.
- If a check could not run, it belongs in Scope Covered, not silently omitted.

---

## Brevity variant

When the user asks for a brief review, collapse the report rather than abandoning it. Observed
behaviour, and the shape to aim for:

- Group findings **by severity** (CRITICAL / HIGH / MEDIUM / LOW-INFO) instead of by pillar, and
  replace the Priority Matrix with a one-row-per-resource quick reference table.
- Keep the per-finding shape intact: the observed value, the check id, why it matters, and the fix.
- **Never drop Scope Covered.** A brief review that hides what it skipped is worse than no review.
- Say explicitly what you did not do, so the reader knows the difference between "checked and clean"
  and "not checked".

The full section order below is the default. Only collapse it when brevity is requested.

---

## 1. Report Header

```
# Serverless Operational Review — <scope label>

Account: <account-id> | Region(s): <regions> | Date: <YYYY-MM-DD>
Scope: <n> Lambda functions | <n> APIs | <n> state machines | <n> tables
Review window: 7 days (<start> to <end> UTC)
```

## 2. Executive Summary

```
Health: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
```

| Severity | Count |
|---|---|
| CRITICAL | n |
| HIGH | n |
| MEDIUM | n |
| LOW | n |
| INFO | n |

Then the top three CRITICAL/HIGH items as one line each, naming the resource and the single action
that closes them.

Health verdict rule: any CRITICAL makes the verdict ❌; otherwise any HIGH makes it ⚠️; otherwise ✅.

## 3. Scope Covered

| Item | Detail |
|---|---|
| Regions reviewed | us-east-1, eu-west-1 |
| Regions skipped (no serverless resources) | ap-south-1, … |
| Resources reviewed | 25 of 63 Lambda functions (top 25 by 7-day invocations) |
| Resources not reviewed | 38 functions below the budget cap — list names or say how to widen scope |
| Checks skipped | Cost analysis — `ce:GetCostAndUsage` denied; IAM breadth — `iam:GetPolicyVersion` denied |
| Data gaps | 3 functions have no log group (never invoked) |

This section is mandatory. A review that hides its own blind spots is not reviewable.

## 4. Configuration Snapshot

Per Lambda function:

| Item | Value |
|---|---|
| Runtime / architecture | python3.13 / arm64 |
| Memory / timeout / ephemeral storage | 1024 MB / 30 s / 512 MB |
| Concurrency | reserved: none, provisioned: none |
| Event sources | SQS `orders` (batch 10, window 0 s) |
| Async config | retries 2, max age 21600 s, OnFailure: none |
| Networking | VPC-attached: no |
| Observability | tracing: Active, log format: JSON, retention: 30 days |
| Security | env vars: 4 keys, CMK: no; function URL: none; code signing: no |
| Execution role | `checkout-processor-role` — 2 managed, 1 inline policy |
| Tags | Environment=prod, Owner=payments, Runbook=missing, OnCall=missing |

Per API, state machine, and table use the equivalent shape — the fields collected in Step 3 of the
skill.

## 5. Findings by Pillar

One table per pillar, in this order: Security, Reliability, Performance Efficiency, Cost
Optimization, Operational Excellence. Sort each table by severity, CRITICAL first.

| # | Check | Finding | Severity | Resource | Current State | Recommendation |
|---|---|---|---|---|---|---|
| 1 | SLS-LMB-056 | Function URL allows unauthenticated access | CRITICAL | `public-webhook` | `AuthType: NONE` | Switch to `AWS_IAM`, or front with CloudFront + WAF if it must stay public |
| 2 | SLS-SQS-001 | Queue visibility timeout below function timeout | CRITICAL | `orders` → `order-processor` | visibility 30 s, function timeout 60 s | Raise visibility timeout to 360 s (6 × 60 s) |

Each row needs a remediation snippet either inline or in the Next Steps section — the reader should
never have to look up the fix.

## 6. CloudWatch Metrics (7-Day)

Per resource, using the metric ids from Step 4 of the skill:

| Metric | Stat | 7-Day Avg | 7-Day Max / Min | Status | Finding |
|---|---|---|---|---|---|
| Invocations | Sum | 41,300/day | 96,100 | — | baseline |
| Errors | Sum | 412/day | 1,847 | ⚠️ | 1.0% error rate |
| Throttles | Sum | 0 | 0 | ✅ | no throttling |
| Duration | p99 | 27,400 ms | 29,900 ms | ❌ | 99.7% of the 30 s timeout |
| ConcurrentExecutions | Max | 84 | 190 | ✅ | 19% of account quota |
| IteratorAge | Max | — | — | — | not a stream source |

Omit rows for metrics the configuration does not emit. Do not report an absent metric as a finding.

Include the account-level concurrency line once per Region:

| Metric | Stat | Value | Quota | Utilization | Status |
|---|---|---|---|---|---|
| ClaimedAccountConcurrency | Max | 412 | 1000 | 41% | ✅ |

## 7. Log Pattern Analysis

Per function:

| Pattern | Occurrences | First seen | Last seen | Severity | Finding |
|---|---|---|---|---|---|
| `Task timed out` | 1,204 | 2026-09-04 | 2026-09-10 | HIGH | timeouts are the dominant failure mode |
| `Runtime.OutOfMemory` | 0 | — | — | — | no OOM |
| `AccessDenied` | 17 | 2026-09-08 | 2026-09-08 | MEDIUM | execution role gap on a single downstream call |

Plus the memory and cold-start summary derived from REPORT lines:

| Item | Value |
|---|---|
| Configured memory | 1024 MB |
| Peak Max Memory Used | 412 MB (40%) |
| Cold starts | 3.1% of invocations |
| p99 Init Duration | 620 ms |
| Log retention | never expire |
| Log group stored bytes | 41.2 GB |

State the sample size used for the REPORT extraction so the figures can be judged.

## 8. Alarm Coverage

| Resource | Metric | Alarm exists | Recommended setting | Severity |
|---|---|---|---|---|
| `checkout-processor` | Errors | ❌ | Sum, > 0, period 60, 3/3 | MEDIUM |
| `checkout-processor` | Throttles | ✅ `checkout-throttles` | — | — |
| `checkout-processor` | Duration | ❌ | p90, < timeout (24,000 ms for a 30 s timeout), period 60, 15/15 | MEDIUM |
| account | ClaimedAccountConcurrency | ❌ | Maximum, 900 (90% of 1,000), period 60, 10/10 | MEDIUM |

Recommended settings come from `cloudwatch-alarm-reference.md`. Where no AWS threshold is published,
say so and propose a starting point derived from the observed 7-day values.

## 9. Cost Summary

| Item | Value |
|---|---|
| Lambda spend, latest full month | $1,240.18 |
| CloudWatch Logs spend, latest full month | $890.44 |
| This function's estimated share | $310.05 **(estimated)** |
| 3-month trend | +18% month over month |

| # | Opportunity | Estimated monthly saving | Confidence | Action |
|---|---|---|---|---|
| 1 | Set 30-day retention on 12 never-expire log groups | $220 **(estimated)** | high | `aws logs put-retention-policy …` |
| 2 | Move 8 x86 functions to arm64 | $95 **(estimated)** | medium — depends on native dependencies | rebuild and shift an alias |
| 3 | Right-size memory on `report-generator` (peak 38% of 3008 MB) | $60 **(estimated)** | medium — validate with Power Tuning first | Lambda Power Tuning, then update memory |

State the split method for any per-resource cost figure, and never present an estimate as a bill.

## 10. Priority Matrix

| # | Finding | Severity | Pillar | Effort | Impact |
|---|---|---|---|---|---|
| 1 | Unauthenticated function URL on `public-webhook` | CRITICAL | Security | Low | High |
| 2 | Queue visibility timeout below function timeout | CRITICAL | Reliability | Low | High |
| 3 | Duration p99 at 99.7% of timeout | HIGH | Performance | Medium | High |

Effort and impact are Low / Medium / High. Sort by severity, then by effort ascending, so the cheap
critical fixes are at the top.

## 11. Next Steps

**Immediate (CRITICAL — 24 to 48 hours)**

1. `public-webhook` — set `AuthType: AWS_IAM` on the function URL, or place CloudFront + WAF in front:
   ```bash
   aws lambda update-function-url-config --function-name public-webhook --auth-type AWS_IAM
   ```
2. `orders` queue — raise the visibility timeout to 6× the function timeout:
   ```bash
   aws sqs set-queue-attributes --queue-url <url> --attributes VisibilityTimeout=360
   ```

**Short-term (HIGH — 1 week)**

**Medium-term (MEDIUM — 30 days)**

**Long-term (LOW — as convenient)**

Each item names the resource, the command or IaC change, and the finding id it closes.

## 12. Appendix — Reference Links

- [Serverless Applications Lens](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/welcome.html)
- [Lens — Failure management](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/failure-management.html)
- [Lens — Metrics and alerts](https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/opex-metrics-and-alerts.html)
- [Lambda best practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Lambda runtime support policy](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
- [CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html)
- [AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning)
- [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)

---

## Severity Definitions

Include this table in every report.

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | Fix within 24–48 hours |
| HIGH | Significant gap that could lead to incidents | Fix within 1 week |
| MEDIUM | Notable improvement opportunity | Plan within 30 days |
| LOW | Minor optimization or hardening | Address when convenient |
| INFO | Observation, no action required | N/A |

---

## Consolidated (multi-resource) variant

For a Region- or account-wide review, keep sections 1–3 global, then add a per-resource roll-up
before the detailed sections:

| Resource | Type | CRITICAL | HIGH | MEDIUM | LOW | Verdict |
|---|---|---|---|---|---|---|
| `checkout-processor` | Lambda | 1 | 2 | 4 | 1 | ❌ |
| `checkout-api` | API (HTTP) | 0 | 1 | 3 | 0 | ⚠️ |
| `orders` | DynamoDB | 0 | 0 | 2 | 1 | ✅ |

Then repeat sections 4 through 8 per resource, and keep sections 9 through 12 global so the reader
gets one prioritised action list rather than one per resource.
