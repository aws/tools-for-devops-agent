# DynamoDB Facts — latency and the metrics behind it

Load-bearing mechanics for this skill. **Read this before explaining how any metric,
statistic, limit, or client behaviour works, and before recommending any fix.**

Every fact below is cited to AWS documentation, or marked as an observation where it is
inferred from how CloudWatch behaves rather than stated in a document. The "**Do not say**"
notes are claims that sound right, circulate widely, and are wrong — including two
remediations that are commonly recommended for latency and that the documentation explicitly
warns against.

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
> experiencing latency — or that it proves the client or network *is* the cause. A normal
> value supports exactly one statement: *no DynamoDB service-processing latency signal was
> observed.* Where the remaining time went is unmeasured until the client is measured.

**It measures *successful* requests.** Throttled and failed requests are not represented in
it, and `SampleCount` counts successful requests only.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that a flat latency curve rules out a capacity problem. Retries of throttled
> requests inflate what the *client* observes while leaving this metric unchanged.

**Because it excludes all client activity, nothing that happens in the client can raise it.**
Connection setup, TLS handshakes, SDK retries, client CPU or garbage-collection pauses, and
network distance are all outside it. An elevated p99 in this metric is therefore a
DynamoDB-side observation by construction.

> **Do not say:** that an elevated `SuccessfulRequestLatency` p99 is caused by a client cold
> start, connection setup, or an idle connection. Those costs are excluded from the metric.

**Valid statistics are `Minimum`, `Maximum`, `Sum`, `Average`, `Percentile`, and
`SampleCount`.** Percentiles are supported — p50, p90, p99 — and custom percentiles such as
p99.9 can be entered directly in the CloudWatch statistic field.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that DynamoDB does not support p99 for this metric, or that `Average` is the
> only usable statistic. That was older guidance; it is now wrong.

**A percentile is only as meaningful as the number of requests behind it.** With fewer than
100 requests in a period, p99 is effectively the slowest one or two requests in that period.
This is arithmetic, not a DynamoDB property — it is why this skill applies a minimum
`SampleCount` per period before reading a percentile.

**CloudWatch computes a percentile over whatever period you request,** including a single
period spanning several days. A one-datapoint query over a 7-day period returns the p50 or
p99 of every request in those 7 days. This skill uses that to get a baseline without
aggregating datapoints by hand. *(Observed against live CloudWatch with `Period: 604800`.)*

**Dimensions are `TableName`, `Operation`, and `StreamLabel`.** There is no index dimension,
so latency cannot be attributed to a specific GSI or LSI from this metric.

**Aggregation granularity is one minute** for `SuccessfulRequestLatency`, `SystemErrors`,
`UserErrors`, `ThrottledRequests`, `ConsumedRead`/`WriteCapacityUnits`, `ReturnedItemCount`,
`FaultInjectionServiceInducedErrors`, and the throttle-event metrics. Most other DynamoDB
metrics aggregate at five minutes.

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
> multi-item operation against its own baseline, not against an absolute number.

**Transactional operations do two underlying reads or writes per item** — one to prepare the
transaction and one to commit it — so `TransactGetItems` and `TransactWriteItems` do not share
a baseline with the corresponding singleton operations.
→ [Transactions: capacity management](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)

**Occasional spikes are normal, particularly in `Maximum` and the high percentiles**, and are
expected as a result of DynamoDB background operations that maintain availability and
durability, or transient infrastructure conditions. A **sharp, persistent** rise in `Average`
or p50 is the documented actionable signal, and warrants checking the Service Health Dashboard
and Personal Health Dashboard.

> **Do not say:** that a tail is harmless because the documentation calls occasional spikes
> normal. *Occasional* is the operative word. A tail elevation that recurs or persists, or that
> breaks the application's own latency objective, is worth acting on even when p50 is normal.

**Interpretation of the percentiles is documented:** p50 is typical latency; high p99 with
normal p50 indicates sporadic issues affecting a small portion of requests; consistently
elevated p50 suggests genuine performance degradation.

**Item size and query size affect latency** — a 1 KB item and a 400 KB item differ, as do 10
items and 100 items returned. This is a documented *possible* cause, not a diagnosis: an
elevated p50 alone does not show which factor is responsible.

**`TableSizeBytes` and `ItemCount` refresh roughly every six hours,** and give a table-wide mean
item size. A static mean cannot explain a *change* in latency, and cannot show the size of the
items a slow operation actually touched. Treat it as weak background context only.

**`ReturnedItemCount` counts the items returned by `Query`, `Scan`, or `ExecuteStatement`
(select)**, with `TableName` and `Operation` dimensions. It is the number *returned*, not the
number *evaluated* — a `Scan` with a filter that evaluates 100 items and returns 15 records 15.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that DynamoDB publishes a latency SLA, or quote a figure as one. It
> documents an expectation for singleton operations. Any threshold this skill applies is its
> own operating heuristic.

## Errors, throttles, and how they reach the client

**DynamoDB's error and throttle counters publish datapoints only when an event occurs.**
AWS's CloudWatch documentation gives DynamoDB `ThrottledRequests` as its example of a metric
that "generates data points only when an error occurs", and alarms in the `AWS/DynamoDB`
namespace default to ignoring missing data.
→ [How CloudWatch alarms treat missing data](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html)
*(Observed: on actively used tables with no errors or throttling, `ListMetrics` returns no
`SystemErrors`, `ThrottledRequests`, or throttle-event series at all — the same behaviour.)*

An empty series for one of these counters is therefore the normal shape of *no events*. It is
evidence of zero events **only** when the query succeeded, used the dimensions DynamoDB
publishes the metric on, and the same operation's `SuccessfulRequestLatency` has datapoints in
the same window — proof that the operation was active and metrics were flowing.
`references/data-collection.md` calls that status `none_recorded`.

> **Do not say:** "SystemErrors measured 0." Say "no SystemErrors recorded" — and only after the
> three conditions above hold.

**`SystemErrors` counts requests that returned HTTP 500,** and **DynamoDB publishes it only on
the `TableName` + `Operation` dimension pair, never on `TableName` alone.** A query or alarm
that specifies only `TableName` never matches data.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

**When DynamoDB returns a 500, most AWS SDKs retry automatically.** If a retry succeeds, the
application never sees the error but may notice increased client-perceived latency; if every
retry fails, the error reaches application code. Occasional 500s are expected in a distributed
system; if they persist over a prolonged period, contact AWS Support with the request IDs of
the affected requests.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html),
[Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

> **Do not say:** that a non-zero `SystemErrors` count caused the latency. It shows service-side
> errors occurred. Causation needs the errors to coincide in time with the latency rise, on the
> same operation, and to persist.

**`FaultInjectionServiceInducedErrors` counts HTTP 500s injected by an AWS Fault Injection
Service experiment, and every one of them is also counted in `SystemErrors`.** Compare the two
for the same period to separate experiment-induced errors from organic ones. Dimensions:
`TableName`, `Operation`.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

**`UserErrors` is not a table metric.** It is the aggregate of HTTP 400 responses for the
**current Region and account** — client-side faults such as `ResourceNotFoundException`,
`ValidationException`, and `TransactionConflict` — and it excludes
`ProvisionedThroughputExceededException` (counted in `ThrottledRequests`) and
`ConditionalCheckFailedException` (counted in `ConditionalCheckFailedRequests`).
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

> **Do not say:** that a table had a given number of user errors. `UserErrors` cannot be
> attributed to a table.

**`ThrottledRequests` increments once per request**, no matter how many events inside that
request were throttled, and is published on `TableName` + `Operation`. In a batch request it
increments only if *every* item in the batch was throttled. Compare it with
`ReadThrottleEvents` and `WriteThrottleEvents`.
→ [CloudWatch throttling metrics](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingThrottling-cloudwatch.html),
[DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

**`ReadThrottleEvents` and `WriteThrottleEvents` on the `TableName` dimension exclude global
secondary indexes.** Index throttling is published only on `TableName` +
`GlobalSecondaryIndexName`.
→ [DynamoDB metrics and dimensions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html)

**A GSI without enough write capacity throttles writes to the base table** ("GSI
back-pressure"), so base-table write latency and throttling can originate at an index.
→ [GSI write throttling and back-pressure](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/gsi-throttling.html)

**The AWS SDKs automatically retry `ProvisionedThroughputExceededException`**, so a throttled
workload often succeeds eventually — at the cost of elapsed time the client sees as latency.
`ProvisionedThroughputExceededException` is an HTTP 400.

> **Do not say:** that throttling shows up as elevated `SuccessfulRequestLatency`. It shows up
> as throttle events plus client-observed slowness. The two live in different metrics.

**Which ceiling was hit** — table or index provisioned capacity, a single partition's
1,000 WCU/s or 3,000 RCU/s, an account limit, or an on-demand maximum — is read from the
cause-specific throttle metrics and the throttling exception's reason. This skill establishes
only that throttling coincides with the latency, and hands the rest off.
→ [Diagnosing throttling](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/throttling-diagnosing-workflow.html)

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

> **Do not recommend strongly consistent reads to reduce latency.** This is one of the two
> inverted remediations. Strong consistency is a freshness choice: it costs twice the
> throughput, may raise latency, and cannot be used on a GSI. Recommend it only when the
> requirement is reading a just-written item, and say plainly that it trades latency and cost
> for that guarantee.

## Documented ways to reduce latency

In the order the documentation presents them. Each is a change in the caller, and each has a
precondition — state it rather than recommending the lever unconditionally.
→ [Troubleshooting latency issues](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TroubleshootingLatency.html)

1. **Reuse connections.** Requests go over an authenticated HTTPS session; establishing one
   takes multiple round trips, so the first request is slower than those that reuse the
   connection. A documented keep-alive is sending a `GetItem` every 30 seconds when no other
   request is made — note that each keep-alive read consumes read capacity.
   **Whether this is needed depends on the SDK.** Check the caller's SDK and version first:
   - AWS SDK for JavaScript v3 reuses TCP connections by default.
     → [Reuse connections in Node.js (v3)](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/node-reusing-connections.html)
   - AWS SDK for JavaScript v2 (end of support) required opting in.
     → [Reusing connections in Node.js (v2)](https://docs.aws.amazon.com/sdk-for-javascript/v2/developer-guide/node-reusing-connections.html)
   - AWS SDK for Java 2.x keeps a connection pool per service client; the documented practice
     is to share one client instance rather than creating clients per request.
     → [Java 2.x best practices](https://docs.aws.amazon.com/sdk-for-java/v2/developer-guide/best-practices.html)
   - botocore (boto3) keeps a connection pool per client, `max_pool_connections` defaulting to
     10 — a pool smaller than the caller's concurrency forces new connections.
     → [botocore Config](https://docs.aws.amazon.com/botocore/latest/reference/config.html)

   For any other SDK, say you have not verified its default and point to its documentation.
2. **Use eventually consistent reads** where the application does not require strong
   consistency — lower cost, and can be served from a co-located availability zone.
3. **Implement request hedging** for very low p99 requirements: if the first request has not
   answered quickly enough, send a second equivalent request and take the first response.
   Easier for reads. For writes, use timestamp-based ordering so a hedged request is treated as
   occurring at the first attempt's time, preventing out-of-order updates. **Hedge or blindly
   retry only operations that are safe to repeat** — reads, idempotent writes, or conditional
   writes designed for it.
4. **Adjust request timeout and retry behaviour** — but see the warning below. A timeout is a
   budget decision: the attempt timeout and the total-call timeout (including retries) must fit
   inside the application's own latency objective. In the AWS SDK for Java 2.x these are
   `apiCallAttemptTimeout` and `apiCallTimeout`.
   → [Java 2.x best practices](https://docs.aws.amazon.com/sdk-for-java/v2/developer-guide/best-practices.html)
   `TransactWriteItems` is idempotent when it carries a client token; a client token is valid
   for 10 minutes after the request that used it finishes.
   → [Transactions: idempotency](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)
5. **Reduce the distance between client and endpoint**, using Global Tables to place a replica
   closer to users. Replication is asynchronous.
6. **Use caching** — only for read-heavy workloads that can tolerate eventually consistent
   results. DAX is a managed in-memory cache for DynamoDB documented at up to a **10×**
   improvement, milliseconds to microseconds. ElastiCache is the alternative for a cache-aside
   pattern.

> **Do not recommend a very low socket timeout.** This is the second inverted remediation.
> The documentation warns that overly low timeouts cause client-induced availability issues,
> gives **a 50 ms socket timeout** as the example that can produce connection errors during
> network latency spikes, and says to **prefer hedging to short timeouts**. Default SDK
> behaviours are optimised for most applications. A fail-fast strategy is legitimate, but
> "set the timeout to 50 ms" is not the documented advice — it is the documented anti-example.

## DAX trade-offs — state them whenever DAX is mentioned

→ [DAX and DynamoDB consistency models](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.consistency.html)

- **DAX serves eventually consistent reads.** Replication between DAX nodes is eventually
  consistent, so two clients can read different values for the same key for a short time.
  Applications using DAX must tolerate eventually consistent data.
- **Strongly consistent reads and `TransactGetItems` pass through DAX to DynamoDB and are not
  cached** — DAX gives them no latency benefit.
- **The query cache is not invalidated by item writes.** `Query` and `Scan` result sets are
  cached separately from items and stay as cached until their TTL expires, even after the
  underlying items change.
- **DAX caches negative results** — a lookup for a missing item can keep returning empty until
  the cache entry expires or the item is written through DAX.
- DAX is a separate cluster the caller must provision, size, and operate, and it requires a DAX
  client in the application.

> **Do not recommend DAX for a `Scan`-heavy or write-heavy latency problem, or for reads that
> must be strongly consistent.** It does not help those, and the query-cache behaviour can
> return stale result sets.

## When you are not certain

Say so, and name what would settle it. Preferred forms:

- "I can't confirm that from what I've collected — `<metric or statistic>` would show it."
- "That's outside what `SuccessfulRequestLatency` measures; SDK latency logging on the client
  would show it."
- "That behaviour I'd want to verify against the DynamoDB documentation before relying on it."

All three beat a confident mechanism that turns out to be wrong. The most common harmful
answer in this family is not a wrong conclusion — it is a right conclusion wrapped in an
invented explanation.
