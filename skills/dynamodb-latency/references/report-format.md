# Report Format

One structure, used for every run. Substitute placeholders; do not reorder sections, and do not
drop a section because it would be short — a short "Not Assessed" section is information.

## Structure

```markdown
# DynamoDB Latency Analysis — `<table>`

**Region:** <region> · **Account:** <account> · **Window:** <start> → <end> (<duration>, <period>s periods)
**Baseline:** <baseline start> → <baseline end> (7 days, per operation) · **Capacity mode:** <PROVISIONED | PAY_PER_REQUEST> · **Table age:** <n> days
**Primary outcome:** `<LT-xx>` <canonical name> · **Confidence:** <High | Medium | Low>

<One paragraph: what the data shows, in plain language, what it does not establish, and what
it does not cover. Observations first, then the limits.>

## Latency Profile

| Operation | Requests | p50 | p99 | Max | Average | Baseline p50 / p99 | p50 pattern | p99 pattern | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| `GetItem` | 1,841,233 | 3.6 ms | 68.4 ms | 412 ms | 4.1 ms | 3.4 / 14.9 ms | none | isolated (2) | 100% |
| `Query` | 42,109 | 18.4 ms | 96.0 ms | 388 ms | 22.7 ms | 17.9 / 91.0 ms | none | none | 100% |
| `Scan` | — | — | — | — | — | — | — | — | not called in window |

Statistic source: `SuccessfulRequestLatency`, per `Operation` dimension. This metric measures
time internal to DynamoDB only — client-side activity and network trip times are excluded — and
counts successful requests only. Baselines are computed by CloudWatch over the 7 days before the
window. Periods with fewer than 100 requests (p99) or 10 requests (p50) are excluded.

## Errors and Throttling

| Signal | Scope | Total | Non-zero periods | Status |
|---|---|---|---|---|
| `SystemErrors` | `GetItem` | — | — | none recorded |
| `FaultInjectionServiceInducedErrors` | `GetItem` | — | — | none recorded |
| `ThrottledRequests` | `GetItem` | — | — | none recorded |
| `ReadThrottleEvents` | table | — | — | none recorded |
| `WriteThrottleEvents` | GSI `orders-by-status` | — | — | none recorded |

Status is one of: `recorded`, `none recorded` (no events published while the operation was
active), `not exercised` (the operation was not called — omit the row unless it was recorded),
`no data` (activity could not be confirmed — unknown), `unable to verify`.

## Primary Outcome

`<LT-xx>` — <canonical name>. Confidence <level>: <one line per reason>.

<The verbatim template body from finding-logic.md.>

## Also Observed

<Each other qualifying outcome and each present-but-not-causal signal, one line each, per
finding-logic.md. If none: "No other signal was observed.">

## Contributing Factors

<Each CF rule that fired, verbatim from finding-logic.md, most significant first. If none
fired, write: "None identified from the collected metrics.">

## Not Assessed

| Question | Why |
|---|---|
| Item size distribution | Requires reading items; outside this skill |
| Which partition key is hot | Requires Contributor Insights traffic analysis; outside this skill |
| Which throttle ceiling was hit | Read from the cause-specific throttle metrics; handed off (`CF-04`) |
| Per-index latency | No index dimension exists on `SuccessfulRequestLatency` |
| End-to-end client latency | Not measured by any DynamoDB metric; needs SDK latency logging or tracing |
| Client errors for this table | `UserErrors` is aggregated across the account and Region |

## Recommended Actions

<Ordered as in the table below. Each item: the action, the evidence that triggered it, its
precondition or trade-off, and who must make the change.>

## Not Recommended

<Include this section whenever latency is the presenting problem. Both entries are common
advice that AWS documentation contradicts — see references/dynamodb-facts.md.>

## References

- Troubleshooting latency issues in Amazon DynamoDB — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html
- DynamoDB metrics and dimensions — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html
- DynamoDB read consistency — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html
- CloudWatch throttling metrics — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingThrottling-cloudwatch.html
- GSI write throttling and back-pressure — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/gsi-throttling.html
- DAX and DynamoDB consistency models — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.consistency.html
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

## Recommended Actions — ordering and preconditions

Order by the documented sequence, filtered to what the evidence supports. **Never list an
action whose trigger did not fire, and always state its precondition.**

| Order | Action | Fires when | Precondition / trade-off to state |
|---|---|---|---|
| 1 | Measure the client: SDK latency metric logging, or end-to-end tracing of a slow request | `CF-01`, `CF-07`, or any outcome at Low confidence | — |
| 2 | Hand off throttling diagnosis with the `CF-04` evidence | `CF-04` | — |
| 3 | Review the SDK's retry configuration: backoff with jitter, attempt count, and whether the application adds its own retries on top | `LT-02`, or `LT-01` branch (b) | The SDKs already retry throttling and HTTP 500s by default — do not stack application retries on SDK retries; retry only operations safe to repeat; total retry time must fit the application's latency objective |
| 4 | Check connection reuse for the caller's SDK | `CF-01` with a first-call-after-idle or after-deploy symptom | SDK-specific — several current SDKs reuse connections by default (see `dynamodb-facts.md`); a keep-alive `GetItem` every 30 s consumes read capacity |
| 5 | Request hedging for tail protection | `LT-04` recurring, sustained, or SLO breach | Reads, or idempotent/conditional writes with timestamp ordering; costs extra requests |
| 6 | Review attempt and total-call timeouts — with the warning in Not Recommended | `LT-04` recurring or sustained, `CF-01` | Size them from the application's latency objective, not from DynamoDB's typical latency |
| 7 | Bound page size, narrow projections, avoid filter-heavy reads | `CF-03` | Client-side; safe to change |
| 8 | Reduce client-to-endpoint distance (Global Tables) | `CF-07` | Asynchronous replication; replicas serve eventually consistent reads |
| 9 | Caching — DAX, or ElastiCache cache-aside | **only** when the user describes a read-heavy workload of repeated reads that can tolerate eventually consistent results, alongside `LT-03` or `LT-04` on a read operation | State every DAX trade-off in `dynamodb-facts.md`; not for `Scan`-heavy, write-heavy, or strongly consistent reads |
| 10 | AWS Health check, request IDs from the affected periods, support case if persistent | `LT-01`, `LT-03`, or `LT-04` recurring, sustained, or SLO breach | — |

Each item states **who changes it**. Items 3–9 are changes in the caller's code or
configuration. This skill does not size capacity, pre-warm tables, or change indexes.

## Health rating

One rating per table, describing the **DynamoDB-internal request path only**:

| Rating | Criteria |
|---|---|
| **Not rated** | `LT-00` |
| **High concern** | any outcome or factor at High severity |
| **Medium concern** | any outcome or factor at Medium severity, or any run that continued past a permissions or tooling gap |
| **Low concern** | any outcome or factor at Low severity — e.g. `LT-04` isolated, or `LT-05` with `CF-05` at Low |
| **No DynamoDB-side concern** | `LT-05` with nothing above Info |

Apply the first row that matches, top to bottom. Rate from **severity**, not from the outcome
name — an `LT-01` at Medium is Medium concern. `CF-01` is excluded from the rating: it describes
time outside DynamoDB, which this rating does not cover.

### Caps

- A run that continued past an `AccessDenied` or `ToolingFailure` is capped at **Medium
  concern** — you cannot certify what you could not read.
- `LT-00` is never rated.
- If the user reports slowness and the rating is "No DynamoDB-side concern" or "Low concern",
  the report must say that the rating does not cover client-side or network time.

## Multi-table reports

One section per table, in the order the user listed them, each with its own outcome,
confidence, and rating. Then a short comparison table: table, outcome, confidence, rating,
headline number. No cross-table inference — two tables sharing a client and a symptom is a
hypothesis for the client, not a finding about either table.

## Pre-render validation

Check every line before output. Any failure means fix the report, not ship it with a caveat.

1. **Exactly one primary outcome, with a confidence and its reasons.** Every other qualifying
   condition is under Also Observed — none silently dropped.
2. **No counter is written as "0" or "measured zero".** `none_recorded` reads "none recorded";
   `NoData` reads "no data" and supports no conclusion.
3. **No threshold is described as an SLA or an AWS commitment.**
4. **No sentence concludes that the client, SDK, or network *is* the cause.** Search the draft
   for "is client-side", "is in the client", "client-side cause", "network is the cause". The
   allowed form is "not explained by DynamoDB-side metrics", followed by a measurement.
5. **No client-side mechanism is attached to a DynamoDB-side elevation.** Connection setup,
   cold start, and idle connections are never offered as the cause of an elevated
   `SuccessfulRequestLatency` percentile.
6. **Every causal outcome names its evidence of coincidence** — the overlapping timestamps, or
   the reported-slowness overlap for a retry branch.
7. **Every template keeps Observed and Not established separate.** No possible factor is stated
   as a finding.
8. **No multi-item or transactional operation is judged against an absolute threshold.**
9. **`SystemErrors` and `ThrottledRequests` come from per-`Operation` queries.** A table-only
   `SystemErrors` query is invalid — DynamoDB does not publish it there.
10. **`UserErrors`, if mentioned, is labelled account-wide.**
11. **`Not Recommended` is present** whenever latency is the presenting problem.
12. **Every rule ID cited corresponds to a rule that actually fired** on collected data.
13. **No hot key is named, no item is quoted, no index is blamed for latency.** A GSI may be
    named only as the scope of recorded throttle events.
14. **Every recommended action names its trigger, its precondition, and who changes it.**
15. **The window, baseline, region, and period are stated in the header**, and match what was
    actually queried.
16. **Any conversational summary around the report obeys the same checks.** A closing "in
    short" paragraph is where attribution drifts — "the time is lost between your app and
    DynamoDB" is a conclusion about the network the metrics did not establish. Restate the
    finding as "not inside DynamoDB processing time" and the next measurement.

## Tone

Report what the metrics show, then say plainly what they do not establish. The most valuable
sentence this skill produces is often "DynamoDB processing time was not elevated, so the time
your users are seeing is outside what this metric measures — here is how to measure it". Do not
bury it, do not turn it into a claim about the client, and do not dress a clean result up as a
clean bill of health.
