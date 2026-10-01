# Report Format

One structure, used for every run. Substitute placeholders; do not reorder sections, and do not
drop a section because it would be short — a short "Not Assessed" section is information.

## Structure

```markdown
# DynamoDB Latency Analysis — `<table>`

**Region:** <region> · **Account:** <account> · **Window:** <start> → <end> (<duration>, <period>s periods)
**Capacity mode:** <PROVISIONED | PAY_PER_REQUEST> · **Table age:** <n> days
**Classification:** `<LT-xx>` <name>

<One paragraph: what the data shows, in plain language, and what it does not cover.>

## Latency Profile

| Operation | Requests | p50 | p90 | p99 | Max | Average | Coverage |
|---|---|---|---|---|---|---|---|
| `GetItem` | 1,841,233 | 3.6 ms | 7.2 ms | 68.4 ms | 412 ms | 4.1 ms | 100% |
| `Query` | 42,109 | 18.4 ms | 44.1 ms | 96.0 ms | 388 ms | 22.7 ms | 100% |
| `Scan` | — | — | — | — | — | — | not called in window |

Statistic source: `SuccessfulRequestLatency`, per `Operation` dimension. This metric measures
time internal to DynamoDB only — client-side activity and network trip times are excluded — and
counts successful requests only.

## Errors and Throttling

| Signal | Total | Non-zero periods | Status |
|---|---|---|---|
| `SystemErrors` | 0 | — | measured |
| `UserErrors` | 14 | 2 | measured |
| `ThrottledRequests` | 0 | — | measured |
| `ReadThrottleEvents` | 0 | — | measured |
| `WriteThrottleEvents` | 0 | — | measured |

## Classification

`<LT-xx>` — <name>. <The verbatim template body from finding-logic.md.>

## Contributing Factors

<Each CF rule that fired, verbatim from finding-logic.md, most significant first. If none
fired, write: "None identified from the collected metrics.">

## Not Assessed

| Question | Why |
|---|---|
| Item size distribution | Requires reading items; outside this skill |
| Which partition key is hot | Requires Contributor Insights traffic analysis; outside this skill |
| Which throttle ceiling was hit | Read from the cause-specific throttle metrics; outside this skill |
| Per-index latency | No index dimension exists on `SuccessfulRequestLatency` |
| End-to-end client latency | Not measured by any DynamoDB metric; needs SDK latency logging or tracing |

## Recommended Actions

<Ordered as in finding-logic.md and dynamodb-facts.md. Each item: the action, the reason, and
who must make the change.>

## Not Recommended

<Include this section whenever latency is the presenting problem. Both entries are common
advice that AWS documentation contradicts — see references/dynamodb-facts.md.>

## References

- Troubleshooting latency issues in Amazon DynamoDB — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html
- DynamoDB metrics and dimensions — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html
- Monitoring DynamoDB with CloudWatch — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Monitoring-metrics-with-Amazon-CloudWatch.html
- DynamoDB read consistency — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
- CloudWatch throttling metrics — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingThrottling-cloudwatch.html
- On-demand capacity mode — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html
- In-memory acceleration with DAX — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html
```

## The "Not Recommended" section

Render both entries verbatim when latency is the presenting problem. They exist because both
are widely recommended and both are contradicted by the documentation, so a report that omits
them leaves the user likely to apply them anyway.

> **Do not set a very low socket or request timeout** (the commonly repeated 50 ms). AWS
> documents that overly low timeouts cause client-induced availability issues, and gives a
> 50 ms socket timeout as the example that can produce connection errors during network latency
> spikes. Default SDK behaviours are optimised for most applications. If you need tail
> protection, prefer request hedging to a short timeout.
>
> **Do not switch to strongly consistent reads to reduce latency.** They require twice the
> throughput, may have higher latency, and are not supported on global secondary indexes.
> Eventually consistent reads can be served from an availability zone co-located with the
> requester, which is why they appear in AWS's latency-reduction guidance. Use strong
> consistency only when the requirement is reading a just-written item.

## Recommended Actions — ordering

Order by the documented sequence, filtered to what the classification supports. Never list an
action whose triggering factor did not fire.

| Order | Action | Fires when |
|---|---|---|
| 1 | Reuse connections; keep-alive `GetItem` every 30 s when idle | `CF-01`, or any tail-spike classification |
| 2 | Retries with exponential backoff and jitter | `LT-02`, `CF-05` |
| 3 | Request hedging for tail protection | `LT-04` where the tail matters to an SLO |
| 4 | Review timeout and retry configuration — with the warning above | `LT-04`, `CF-01` |
| 5 | Reduce client-to-endpoint distance (Global Tables) | `CF-07` |
| 6 | Caching — DAX, or ElastiCache cache-aside | read-heavy repeat access, `LT-03` with `CF-03` |
| 7 | Bound page size, narrow projections, avoid filter-heavy reads | `CF-03` |
| 8 | Pre-warm via warm throughput | `CF-04` |
| 9 | Capacity or key-distribution work, handed off | `LT-02`, `CF-04`, `CF-05` |

Each item states **who changes it**. Items 1–7 are changes in the caller's code or
configuration; 8 and 9 are table-side and outside this skill's remit to size.

## Health rating

One rating per table, from the classification and the factors:

| Rating | Criteria |
|---|---|
| **Healthy** | `LT-05`, with `SystemErrors` and throttles measured at zero |
| **Low concern** | `LT-04` with fewer than 3 elevated periods, or `LT-05` with `CF` factors that are client-side only |
| **Medium concern** | `LT-03` at Medium, `LT-04` recurring, `LT-02` at Medium, or any run that continued past a permissions or tooling gap |
| **High concern** | `LT-01`, or `LT-03`/`LT-02` at High |
| **Not rated** | `LT-00` |

### Caps

- A run that continued past an `AccessDenied` or `ToolingFailure` is capped at **Medium
  concern** — you cannot certify what you could not read.
- `LT-00` is never rated. Do not substitute "Healthy" for "could not measure".
- A rating describes the **DynamoDB-internal** request path. If the user reports slowness and
  the rating is Healthy, the report must say that the rating does not cover client-side or
  network time.

## Multi-table reports

One section per table, in the order the user listed them, each with its own classification and
rating. Then a short comparison table: table, classification, rating, headline number. No
cross-table inference — two tables sharing a client and a symptom is a hypothesis for the
client, not a finding about either table.

## Pre-render validation

Check every line before output. Any failure means fix the report, not ship it with a caveat.

1. **Exactly one `LT-` classification appears.** Not zero, not two.
2. **No `NoData` metric is reported as `0`.** Search the draft for every `0` in the errors and
   throttling table and confirm each came from a measured zero.
3. **No threshold is described as an SLA or an AWS commitment.** Every threshold mention says
   "this skill's threshold".
4. **If the classification is `LT-05` or any nominal-leaning outcome**, the report states what
   `SuccessfulRequestLatency` excludes. A bare "nominal" is the single most misleading output
   this skill can produce.
5. **No multi-item operation is judged against a singleton threshold.** `Query`, `Scan`,
   `Batch*` and `Transact*` are assessed relatively or marked not assessable.
6. **`Not Recommended` is present** whenever latency is the presenting problem.
7. **Every rule ID cited corresponds to a rule that actually fired** on collected data.
8. **No hot key is named, no item is quoted, no index is blamed for latency.**
9. **Every recommended action names who changes it**, and no action appears whose triggering
   factor did not fire.
10. **The window, region, and period are stated in the header**, and the window matches what
    was actually queried.

## Tone

Report what the metrics show, then say plainly what they cannot show. The most valuable
sentence this skill produces is often "the DynamoDB-internal portion is normal, so the time
your users are seeing is somewhere this metric does not reach" — do not bury it, and do not
dress up a nominal result as a clean bill of health.
