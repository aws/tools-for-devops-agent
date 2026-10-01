# Finding Logic

Two kinds of output:

1. **One primary classification** — `LT-00` … `LT-05`, chosen by the decision order below.
   Exactly one. Never two, never none.
2. **Zero or more contributing factors** — `CF-01` … `CF-09`. These explain or qualify the
   primary classification; they never replace it.

Use the body templates verbatim, substituting only the bracketed placeholders.

## Thresholds, and what they are

Every number below is **this skill's operating heuristic**, chosen so that it agrees with what
AWS documents: single-digit millisecond `Average` for singleton operations, and explicitly
variable latency for multi-item ones. DynamoDB publishes no latency SLA. Say "above this
skill's threshold", never "above the SLA", and never present a threshold breach as a root
cause on its own.

| Operation class | Sustained threshold (`Average` / p50) | Tail threshold (p99) |
|---|---|---|
| Singleton — `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` | 10 ms | 50 ms |
| Multi-item — `Query`, `Scan`, `Batch*`, `Transact*` | **no absolute threshold** — use the relative test | **no absolute threshold** — use the relative test |

**Relative test for multi-item operations.** Compare the operation's p50 in the most recent
third of the window against its p50 in the earliest third. Flag only at **≥ 2×** with both
thirds holding ≥ 30 datapoints. If the window is too short to split, or either third is too
sparse, the operation is **not assessable** — say so rather than applying a singleton
threshold to a `Scan`.

**"Sustained" means ≥ 3 consecutive periods, or ≥ 50% of periods in the window.**
**"Isolated" means fewer than 3 consecutive periods.** Documented normal variance lives in
the isolated case; do not report it as degradation.

## Severity definitions

| Severity | Meaning |
|---|---|
| **High** | Requests are failing or the elevated latency is sustained and service-side |
| **Medium** | Real and worth acting on, but bounded — a tail problem, or a factor that needs a client-side change |
| **Low** | Worth knowing, not urgent |
| **Info** | Context, or an explicit statement that something could not be evaluated |

## Decision order — apply in this sequence, first match wins

### LT-00 [Info] · Indeterminate — the data cannot support a classification

Fires when **any** of these holds:

- `latency_by_operation` has `NoData` for every operation queried, or
- `coverage_ratio < 0.5` for every operation with data, and the shortfall is not explained by
  table age, or
- `SystemErrors` **or** the throttle metrics are `AccessDenied` or `ToolingFailure` — because
  `LT-01` and `LT-02` sit above `LT-03`/`LT-04` in this order, and skipping them would
  mis-rank the answer, or
- every operation is within threshold — so the only remaining candidate is `LT-05` — **but**
  `SystemErrors` or a throttle metric returned `NoData`. A nominal verdict requires those to
  have been *measured* at zero. An absent metric cannot rule out the two causes that outrank
  it.

This rule is first deliberately. A classification derived from a window with no data is not a
finding, it is a guess wearing a rule ID.

> **`LT-00` · Latency could not be classified for `[table]`**
>
> Between `[start]` and `[end]`, `[what was missing: which metric, which status]`.
>
> `SuccessfulRequestLatency` coverage was `[coverage_minutes]` minutes of the `[window]`-minute
> window requested (`[coverage_ratio]`). `[If table age explains it: The table was created
> [created], so a shorter series is expected.]`
>
> I have not classified the latency profile, because the signals that distinguish a
> service-side condition from a throttle-induced one from normal variance were
> `[unavailable / absent]`. What would settle it: `[the specific call or window]`.

### LT-01 [High | Medium] · Service-side condition

Fires when `SystemErrors.total > 0` **measured** (status `ok`, not `NoData`).

Severity **High** when non-zero in ≥ 3 consecutive periods or `SystemErrors` exceeds 0.1% of
summed `SampleCount`; otherwise **Medium** — occasional HTTP 500s are documented as expected in
a distributed system.

> **`LT-01` · Service-side errors present — `[table]`**
>
> `SystemErrors` totalled `[n]` across `[m]` periods between `[first_ts]` and `[last_ts]`,
> against `[sample_count]` successful requests. HTTP 500 responses are server-side; the
> affected requests can be retried, and occasional ones are expected in a distributed system.
> `[If sustained: This is sustained, not occasional — [m] consecutive periods.]`
>
> Latency alongside them: `[operation]` `Average` `[x]` ms, p99 `[y]` ms.
>
> Next: correlate the window with AWS Health (Service Health Dashboard and your Personal
> Health Dashboard), and log request IDs for the slow or failed requests before opening a
> support case. If the errors persist over a prolonged period, contact AWS Support with those
> request IDs.

### LT-02 [High | Medium] · Throttle-induced

Fires when a throttle metric is non-zero **and** its non-zero periods intersect the
`elevated_periods` of at least one operation — or, when no operation is elevated, when
throttles are non-zero at all and the user reports client-observed slowness.

Severity **High** when the intersection covers ≥ 3 periods — or, in the no-elevation branch,
when the throttle metric is non-zero in ≥ 3 periods; otherwise **Medium**.

This rule exists because of a metric property that misleads reliably: throttled requests are
**not** in `SuccessfulRequestLatency`. The service-side curve can stay perfectly flat while the
client sees seconds of added time from SDK retries.

> **`LT-02` · Latency is throttle-induced — `[table]`**
>
> `[ThrottledRequests | ReadThrottleEvents | WriteThrottleEvents]` totalled `[n]` in
> `[m]` periods, overlapping the elevated-latency periods at `[list of timestamps]`.
>
> What this means: the AWS SDKs retry `ProvisionedThroughputExceededException`
> automatically, so throttled calls usually succeed eventually — and the retry wait is
> elapsed time your client experiences as latency. Because
> `SuccessfulRequestLatency` measures only *successful* requests, the service-side curve
> `[stayed flat at [x] ms | rose to [x] ms]` while the client-observed latency did not.
>
> Note that `ThrottledRequests` increments once per request regardless of how many events
> inside it were throttled, so `[n]` is a floor, not the full extent.
>
> Next: the fix is capacity or key distribution, not the request path. Establishing which
> ceiling was hit — table provisioned capacity, a single partition's 1,000 WCU/s or
> 3,000 RCU/s, an account limit, or an on-demand maximum — is read from the cause-specific
> throttle metrics and is outside this skill. On the client side, confirm retries use
> exponential backoff with jitter rather than a fixed interval.

### LT-03 [High | Medium] · Systemic degradation

Fires when, for at least one operation, `Average` **or** p50 is above the sustained threshold
(singleton) or passes the relative test (multi-item).

Severity **High** when the operation is singleton and p50 ≥ 3× the threshold; otherwise
**Medium**.

> **`LT-03` · Sustained latency elevation — `[operation]` on `[table]`**
>
> p50 `[x]` ms and `Average` `[y]` ms over `[m]` of `[total]` periods, against this skill's
> threshold of `[threshold]` ms for `[operation class]` operations.
> `[Multi-item form: p50 rose from [a] ms in the first third of the window to [b] ms in the
> last third — [ratio]×.]`
>
> A persistent rise in `Average` or p50 — as distinct from a tail spike — is the documented
> signal of genuine degradation rather than normal variance.
>
> Contributing factors assessed: `[list the CF rule IDs that fired, or "none identified"]`.
>
> Next: `[the remediation implied by the factors that fired, in the documented order]`. Also
> check the Service Health Dashboard and Personal Health Dashboard for the window.

### LT-04 [Medium | Low] · Isolated tail spike

Fires when p99 or `Maximum` exceeds the tail threshold while `Average` and p50 stay within the
sustained threshold.

Severity **Medium** when the elevated periods are ≥ 3 and non-consecutive but recurring;
**Low** when fewer than 3.

> **`LT-04` · Tail latency spikes, typical latency normal — `[operation]` on `[table]`**
>
> p99 reached `[y]` ms in `[m]` of `[total]` periods (`[timestamps]`) while p50 held at
> `[x]` ms and `Average` at `[z]` ms.
>
> High p99 with normal p50 indicates sporadic slowness affecting a small share of requests,
> not degradation of the workload. AWS documents that occasional spikes — particularly in
> `Maximum` and the high percentiles — are expected, arising from DynamoDB background
> operations that maintain availability and durability, or transient infrastructure
> conditions.
>
> `[If the user reports a slow first call: The "first call slow, later calls fast" pattern is
> a client-side connection cost, not something this metric can show — see CF-01.]`
>
> Next: this is only worth engineering effort if the tail matters to your SLO. If it does, the
> documented lever is request hedging — issue a second equivalent request when the first has
> not answered in time, and take the first response. For writes, use timestamp-based ordering
> so the hedged request is treated as occurring at the first attempt's time. Do **not**
> respond by lowering socket timeouts; see `references/dynamodb-facts.md`.

### LT-05 [Info] · Nominal

Fires when every operation with data is within threshold, and `SystemErrors` **and** the
throttle metrics were **measured** at zero — status `ok`, not `NoData`.

If any of those three was `NoData`, this rule must not fire: `LT-00` applies instead.

> **`LT-05` · DynamoDB-internal latency is nominal — `[table]`**
>
> | Operation | `SampleCount` | p50 | p99 | `Average` |
> |---|---|---|---|---|
> | `[op]` | `[n]` | `[x]` ms | `[y]` ms | `[z]` ms |
>
> `SystemErrors` measured 0 and throttle events measured 0 across the window.
>
> **This does not mean the application is not slow.** `SuccessfulRequestLatency` measures
> time internal to the DynamoDB service only — client-side activity and network trip times are
> excluded — and it counts only successful requests. If your users are seeing latency, it is
> in the client, the SDK, or the network path, and the next measurement belongs there: enable
> latency metric logging in the AWS SDK, or use distributed tracing on the calling service,
> then compare end-to-end time against these service-side numbers.

## Contributing factors

Report each one that fires, under the primary classification. Several may fire together.

### CF-01 [Medium] · Client-side residual — connection cost is the leading hypothesis

Fires when the service-side profile is nominal or only tail-elevated **and** the user reports
slowness, a slow first call, slowness after idle, or timeouts.

> **`CF-01` · The unexplained time is client-side**
>
> Service-side latency for `[operation]` is `[x]` ms p50 / `[y]` ms p99, which is
> `[within this skill's threshold]`. The gap between that and what you are observing is not
> measurable from this metric.
>
> The documented first cause of a slow first request is connection establishment: DynamoDB
> requests run over an authenticated HTTPS session, and initiating one takes multiple round
> trips, so the first request is slower than those reusing the connection. The documented
> remedy is a keep-alive — send a `GetItem` every 30 seconds when the application is
> otherwise idle — plus SDK connection-pool reuse across calls.
>
> I am presenting this as the leading hypothesis, not a measured finding: confirming it needs
> client-side timing. Enable SDK latency metric logging, or trace one slow request end to end,
> and compare the total against the `[x]` ms service-side figure above.

### CF-02 [Low | Medium] · Item size as a latency factor

Fires when mean item size ≥ 50 KB and status is `ok`. Severity **Medium** at ≥ 100 KB.

Does **not** fire when `mean_item_size_bytes.status` is `stale` — say it could not be evaluated
instead.

> **`CF-02` · Mean item size is a plausible contributor**
>
> `TableSizeBytes / ItemCount` gives a mean of `[n]` KB per item, from table metadata that
> refreshes roughly every six hours, so treat it as approximate.
>
> Item size affects latency — AWS documents that a 1 KB item and a 400 KB item differ — and
> larger items also reduce items per page, so a paginated read does more round trips for the
> same result set.
>
> This is a distribution question and I have only the mean: a small number of very large items
> can drive a tail while the mean looks unremarkable. Measuring the distribution requires
> reading items, which this skill does not do.

### CF-03 [Medium] · Multi-item operation dominates the latency

Fires when the elevated operation is `Query`, `Scan`, `Batch*`, or `Transact*`.

> **`CF-03` · The elevated operation is multi-item — `[operation]`**
>
> `[operation]` p50 `[x]` ms against `[singleton op]` p50 `[y]` ms in the same window.
>
> Multi-item latency varies with the size of the result set, the complexity of the structures
> returned, and any condition or filter expressions applied — so an absolute comparison with a
> single-item operation says nothing. What the numbers here support is that the time scales
> with how much work each call does.
>
> Request-shape levers, which are client-side and safe to change: bound the page with `Limit`,
> narrow `ProjectionExpression` to the attributes actually used, and avoid filter expressions
> that read many items to return few — a filter is applied *after* the read, so the discarded
> items were already paid for in both latency and capacity.
>
> Whether the access pattern needs a different key schema or a new index is a data-model
> question, and outside this skill.

### CF-04 [Medium] · On-demand ramp risk

Fires when `BillingMode` is `PAY_PER_REQUEST` **and** `LT-02` fired **and** either the table is
younger than 7 days or consumed capacity in the window more than doubled within any 30-minute
span.

> **`CF-04` · On-demand ramp is a plausible source of the throttling**
>
> The table is on-demand `[and was created [created], [age] days ago | and consumed capacity
> rose from [a] to [b] within [n] minutes]`.
>
> On-demand tables instantly accommodate up to **double the previous peak**; exceeding double
> the previous peak within 30 minutes can throttle. A new on-demand table starts able to
> sustain about 4,000 writes and 12,000 reads per second.
>
> The documented preparation is pre-warming — raising the table's warm throughput ahead of a
> known surge. Pre-warming prepares the table's internal partitioning rather than provisioning
> capacity in advance. Sizing that change is a capacity decision and outside this skill.

### CF-05 [Medium] · Provisioned capacity at its ceiling

Fires when `BillingMode` is `PROVISIONED`, `LT-02` fired, and consumed capacity in the
throttled periods is ≥ 80% of provisioned.

> **`CF-05` · Consumed capacity is at the provisioned ceiling**
>
> In the throttled periods, consumed `[read|write]` capacity averaged `[x]` against
> `[y]` provisioned (`[pct]`%).
>
> Burst capacity retains up to five minutes of unused capacity, but it is best-effort, is not
> guaranteed, may be consumed by DynamoDB background tasks, and cannot relieve partition-level
> throttling — so it does not close a sustained gap.
>
> Sizing capacity is outside this skill. What belongs here: until the capacity gap closes, the
> latency your client sees is retry time, and the client-side mitigation is exponential backoff
> with jitter.

### CF-06 [Info] · Read-after-write reported — this is consistency, not latency

Fires when the user reports reads that miss a just-written item, or "stale reads".

> **`CF-06` · What you are describing is read consistency, not latency**
>
> Eventually consistent reads are the default, and a response might not reflect a recently
> completed write; repeating the read after a short time should return the newer item. This is
> not a latency defect and it will not appear in `SuccessfulRequestLatency`.
>
> If the application must read a just-written item, set `ConsistentRead: true` — and price it
> honestly: strongly consistent reads require twice the throughput, may have **higher**
> latency, and are **not supported on global secondary indexes**. Eventually consistent reads
> can be served from an availability zone co-located with the requester, which is why AWS lists
> them as a latency *reduction* strategy.
>
> So this is a correctness/latency trade, not a fix. Choose it per read path, not globally.

### CF-07 [Low] · Client-to-endpoint distance

Fires only when the user states where the client runs and it is a different region from the
table, or when `Replicas[]` is empty and the user describes globally distributed users.

> **`CF-07` · Client and table are in different regions**
>
> You described the client running in `[client region]` while the table is in
> `[table region]`. Cross-region network time is not in `SuccessfulRequestLatency` at all, so
> none of the service-side numbers above account for it.
>
> The documented lever is reducing the distance: Global Tables replicate to Regions you choose,
> placing a copy closer to users. Note the trade-off — replication is asynchronous, and a
> replica serves eventually consistent reads.

### CF-08 [Info] · Metric coverage shorter than the window

Fires when any operation's `coverage_ratio < 0.9` while `LT-00` did not fire.

> **`CF-08` · Partial metric coverage — `[operation]`**
>
> Datapoints span `[coverage_minutes]` minutes of the `[window]`-minute window
> (`[coverage_ratio]`). `[Reason if known: the table was created [created] | the operation was
> not called for part of the window.]`
>
> The findings above rest on the covered span only. A comparison across the full window would
> need `[what]`.

### CF-09 [Info] · Asked but not measurable

Fires whenever the user asks for something these metrics cannot answer. Use it rather than
answering anyway.

> **`CF-09` · `[what was asked]` is not measurable from what this skill collects**
>
> `[The specific reason.]` Examples that come up in this analysis:
> per-index latency — `SuccessfulRequestLatency` has `TableName`, `Operation`, and
> `StreamLabel` dimensions and no index dimension, so latency cannot be attributed to a GSI or
> LSI; the share of reads using strong consistency — no metric distinguishes consistent from
> eventually consistent reads; and which partition key is hot — that needs Contributor Insights
> traffic analysis, which is outside this skill.
>
> What would answer it: `[the specific measurement]`.

## "Unable to verify" template

For any check that returned `AccessDenied` or `ToolingFailure`:

> **Unable to verify · `[check]`**
>
> `[api]` returned `[error class]`, so `[what it would have established]` is unknown. This is
> not evidence of a healthy or unhealthy state — it is a missing measurement. `[The action
> needed.]`

Never substitute an inference for this template, and never let an unverified check render as
a passing one.

## Cross-reference consistency

Before rendering, check these pairs. Each has produced a self-contradicting report in review:

| If … | then … |
|---|---|
| `LT-05` fired | no `CF` rule may describe DynamoDB-side degradation, and the report must state what the metric excludes |
| `LT-02` fired | the report must not attribute the latency to the request path, and must name the `elevated_periods` ∩ `nonzero_periods` overlap |
| `LT-04` fired | the report must not use the word "degradation" for the tail, and must not recommend lowering timeouts |
| `CF-01` fired | the report must not state cold start as a measured finding |
| `CF-06` fired | the report must not present strongly consistent reads as a latency improvement |
| Any metric is `NoData` | the corresponding conclusion is absent from the report, not asserted as zero |
| Mean item size is `stale` | `CF-02` did not fire, and mean item size is reported as not determinable |
