# DynamoDB Facts — latency and the metrics behind it

Load-bearing mechanics for this skill. **Read this before explaining how any metric,
statistic, limit, or client behaviour works, and before recommending any fix.**

Every fact below is cited to AWS documentation. The "**Do not say**" notes are claims that
sound right, circulate widely, and are wrong — including two remediations that are commonly
recommended for latency and that the documentation explicitly warns against.

The rule this file exists to serve: a correct finding with a fabricated mechanism is still a
harmful answer. If you need a mechanism fact that is not here and not in another reference,
say you are not certain and name the check that would settle it.

---

## What `SuccessfulRequestLatency` measures

**It measures latency internal to the DynamoDB service only. Client-side activity and
network trip times are not included.** To see end-to-end time from the caller, enable latency
metric logging in the AWS SDK.
→ [Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

> **Do not say:** that a normal `SuccessfulRequestLatency` proves the application is not
> experiencing latency, or that an elevated one proves the network is fine. The metric is
> silent about everything outside the service.

**It measures *successful* requests.** Throttled and failed requests are not represented in
it, and `SampleCount` counts successful requests only.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that a flat latency curve rules out a capacity problem. Retries of throttled
> requests inflate what the *client* observes while leaving this metric unchanged.

**Valid statistics are `Minimum`, `Maximum`, `Sum`, `Average`, `Percentile`, and
`SampleCount`.** Percentiles are supported — p50, p90, p99 — and custom percentiles such as
p99.9 can be entered directly in the CloudWatch statistic field.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that DynamoDB does not support p99 for this metric, or that `Average` is the
> only usable statistic. That was older guidance; it is now wrong, and repeating it leads
> teams to build alarms that cannot distinguish a tail problem from a systemic one.

**Dimensions are `TableName`, `Operation`, and `StreamLabel`.** There is no index dimension,
so latency cannot be attributed to a specific GSI or LSI from this metric.

**Aggregation granularity is one minute** for `SuccessfulRequestLatency`, `SystemErrors`,
`UserErrors`, `ThrottledRequests`, `ConsumedRead`/`WriteCapacityUnits` and the throttle-event
metrics. Most other DynamoDB metrics aggregate at five minutes.

## What normal looks like

**For most singleton operations** — those that fully specify the primary key — **DynamoDB
delivers single-digit millisecond `Average SuccessfulRequestLatency`**, excluding transport
overhead for the caller.
→ [Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

**For multi-item operations, latency varies** with the size of the result set, the complexity
of the data structures returned, and any condition or filter expressions applied. Repeated
multi-item operations over the same data with the same parameters give a highly consistent
`Average`.

> **Do not say:** that a `Query` or `Scan` is "slow" against a single-item benchmark. Judge a
> multi-item operation against its own trailing baseline, not against an absolute number.

**Occasional spikes are normal, particularly in `Maximum` and the high percentiles**, and are
expected as a result of DynamoDB background operations that maintain availability and
durability, or transient infrastructure conditions. A **sharp, persistent** rise in `Average`
or p50 is the actionable signal, and warrants checking the Service Health Dashboard and
Personal Health Dashboard.

**Interpretation of the percentiles is documented:** p50 is typical latency; high p99 with
normal p50 indicates sporadic issues affecting a small portion of requests; consistently
elevated p50 suggests genuine performance degradation.

**Item size and query size affect latency** — a 1 KB item and a 400 KB item differ, as do 10
items and 100 items returned.

> **Do not say:** that DynamoDB publishes a latency SLA, or quote a figure as one. It
> documents an expectation for singleton operations. Any threshold this skill applies is its
> own operating heuristic.

## Errors, throttles, and how they reach the client

**`SystemErrors` counts requests that returned HTTP 500.** Occasional 500s are expected in a
distributed system and the affected request can be retried; if they persist over a prolonged
period, contact AWS Support. Log request IDs for slow or failed requests before opening a case.
→ [Monitoring with CloudWatch](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Monitoring-metrics-with-Amazon-CloudWatch.html)

**`UserErrors` counts HTTP 400 responses** — client-side faults such as
`ResourceNotFoundException`, `ValidationException`, and `TransactionConflict`. It **excludes**
`ProvisionedThroughputExceededException` (counted in `ThrottledRequests`) and
`ConditionalCheckFailedException` (counted in `ConditionalCheckFailedRequests`). Valid
statistics: `Sum`, `SampleCount`.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

**`ThrottledRequests` increments once per request**, no matter how many events inside that
request were throttled — a single `UpdateItem` against a table with several GSIs is one
increment even if the base write and multiple index writes all throttled. It can therefore
mask the true extent of throttling; compare it with `ReadThrottleEvents`,
`WriteThrottleEvents`, and the cause-specific metrics.
→ [CloudWatch throttling metrics](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingThrottling-cloudwatch.html)

**The AWS SDKs automatically retry `ProvisionedThroughputExceededException`**, so a throttled
workload often succeeds eventually — at the cost of elapsed time the client sees as latency.
`ProvisionedThroughputExceededException` is an HTTP 400.
→ [ProvisionedThroughputExceededException](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_ExecuteTransaction.html)

> **Do not say:** that throttling shows up as elevated `SuccessfulRequestLatency`. It shows up
> as throttle events plus client-observed slowness. The two live in different metrics.

## Capacity behaviour that presents as latency

**On-demand:** a new on-demand table sustains up to **4,000 writes and 12,000 reads per
second**. On-demand instantly accommodates **up to double the previous peak**; exceeding
double the previous peak **within 30 minutes** can throttle. Pre-warming by raising warm
throughput prepares the table's internal partitioning — it does not provision capacity in
advance — and is the documented way to prepare for a known surge.
→ [On-demand capacity mode](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)

**Provisioned burst capacity:** DynamoDB retains up to **5 minutes (300 seconds)** of unused
read and write capacity. It is best-effort, is not guaranteed, may be consumed by background
tasks, and **cannot relieve partition-level throttling**.
→ [Handling spiky loads](https://repost.aws/knowledge-center/dynamodb-spiky-workloads-short-intervals)

**Every physical partition is capped at 1,000 WCU/s and 3,000 RCU/s** (or a linear
combination), so a table with ample aggregate capacity can still throttle when traffic
concentrates. Establishing *which* ceiling was hit is the throttling skill's job, not this
one's — this skill establishes only that throttling coincides with the latency.

## Read consistency

**Eventually consistent is the default.** A response might not reflect a recently completed
write; repeating the read after a short time should return the newer item. Eventually
consistent reads are supported on tables, LSIs, and GSIs, and cost half of strongly
consistent reads.
→ [DynamoDB read consistency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)

**Strongly consistent reads may have *higher* latency, require twice the throughput, and are
not supported on global secondary indexes.**
→ [GetItem does not return the latest data](https://repost.aws/knowledge-center/dynamodb-putitem-getitem-latest-data)

**Eventually consistent reads can be served from an availability zone co-located with the
requester, which decreases latency** — this is why the documentation lists them *as* a latency
reduction strategy.
→ [Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

> **Do not recommend strongly consistent reads to fix latency.** This is one of the two
> inverted remediations. Strong consistency is a correctness choice: it costs twice the
> throughput, may raise latency, and cannot be used on a GSI. Recommend it only when the
> requirement is reading a just-written item, and say plainly that it trades latency and cost
> for that guarantee.

## Documented ways to reduce latency

In the order the documentation presents them.
→ [Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

1. **Reuse connections.** Requests go over an authenticated HTTPS session; establishing one
   takes multiple round trips, so the first request is slower than those that reuse the
   connection. A documented keep-alive is sending a `GetItem` every 30 seconds when no other
   request is made.
2. **Use eventually consistent reads** where the application does not require strong
   consistency — lower cost, and can be served from a co-located availability zone.
3. **Implement request hedging** for very low p99 requirements: if the first request has not
   answered quickly enough, send a second equivalent request and take the first response.
   Easier for reads; for writes use timestamp-based ordering so a hedged request is treated as
   occurring at the first attempt's time, preventing out-of-order updates.
4. **Adjust request timeout and retry behaviour** — but see the warning below.
5. **Reduce the distance between client and endpoint**, using Global Tables to place a replica
   closer to users.
6. **Use caching.** DAX is a managed in-memory cache for DynamoDB delivering up to a **10×**
   improvement, from milliseconds to microseconds, at millions of requests per second.
   ElastiCache is the alternative for a cache-aside pattern.

> **Do not recommend a very low socket timeout.** This is the second inverted remediation.
> The documentation warns that overly low timeouts cause client-induced availability issues,
> gives **a 50 ms socket timeout** as the example that can produce connection errors during
> network latency spikes, and says to **prefer hedging to short timeouts**. Default SDK
> behaviours are optimised for most applications. A fail-fast strategy is legitimate, but
> "set the timeout to 50 ms" is not the documented advice — it is the documented anti-example.

## When you are not certain

Say so, and name what would settle it. Preferred forms:

- "I can't confirm that from what I've collected — `<metric or statistic>` would show it."
- "That's outside what `SuccessfulRequestLatency` measures; SDK latency logging on the client
  would show it."
- "That behaviour I'd want to verify against the DynamoDB documentation before relying on it."

All three beat a confident mechanism that turns out to be wrong. The most common harmful
answer in this family is not a wrong conclusion — it is a right conclusion wrapped in an
invented explanation.
