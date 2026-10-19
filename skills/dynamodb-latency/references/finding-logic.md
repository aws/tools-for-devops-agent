# Finding Logic

Three kinds of output:

1. **One primary outcome** — `LT-00` … `LT-05`, chosen by the selection order below, with a
   **confidence** of High, Medium, or Low.
2. **Also observed** — every other outcome condition that also qualified, and every signal
   that was present but not established as a cause. Nothing that was measured is dropped to
   make the primary outcome look cleaner.
3. **Zero or more contributing factors** — `CF-01` … `CF-09`. These explain, qualify, or hand
   off; they never replace the primary outcome.

Use the body templates verbatim, substituting only the bracketed placeholders. Every template
separates **Observed** (what the metrics show), **Not established** (what they do not prove),
and **Next** (the measurement or handoff that would settle it).

## Outcome names — canonical

Use exactly these names everywhere: report, summary, and conversation.

| ID | Name |
|---|---|
| `LT-00` | Indeterminate |
| `LT-01` | Service-side errors |
| `LT-02` | Throttle-induced |
| `LT-03` | Typical-latency elevation |
| `LT-04` | Tail elevation |
| `LT-05` | No DynamoDB-side elevation |

## Thresholds, and what they are

Every number below is **this skill's operating heuristic**, chosen to agree with what AWS
documents: single-digit millisecond `Average` for singleton operations, explicitly variable
latency for multi-item ones, occasional high-percentile spikes as normal, and a persistent rise
in `Average`/p50 as the actionable signal. DynamoDB publishes no latency SLA. Say "above this
skill's threshold", never "above the SLA", and never present a threshold breach as a root
cause on its own.

### Observation window and periods

| Window | Period | Baseline |
|---|---|---|
| ≤ 6 hours (default 3 h, incident) | 60 s | 7 days before the window, one CloudWatch-computed datapoint |
| > 6 hours (default 14 d, review) | 300 s | 7 days before the window, one CloudWatch-computed datapoint |

### Assessable periods — the `SampleCount` floor

Only **assessable** periods enter any elevation test: `SampleCount` ≥ 100 for p99, ≥ 10 for
p50. An operation with fewer than 10 assessable periods for a statistic, or with fewer than
half of its periods assessable, is **not assessable** for that statistic.

### The reference value each period is compared against

Chosen per operation, in this order:

| # | Reference | When | Confidence ceiling |
|---|---|---|---|
| 1 | **7-day baseline** p50 / p99 | baseline `SampleCount` ≥ 1,000 | High |
| 2 | **Absolute floor only** — no ratio test | singleton operations without a usable baseline | Medium |
| 3 | **First third of the window** — one CloudWatch datapoint with `Period` = a third of the window, rounded down to a multiple of 60 s; only the later two-thirds are tested | multi-item or transactional operations without a usable baseline, when the first third holds ≥ 30 assessable periods | Low |
| 4 | none | otherwise | the operation is **not assessable** |

Reference 3 is contaminated if the problem began before the window. Say so whenever you use it.

### Elevation tests, per assessable period

| Class | p50-elevated when | p99-elevated when |
|---|---|---|
| Singleton — `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` | p50 ≥ 2 × reference **and** p50 ≥ 10 ms. Without a reference: p50 ≥ 10 ms | p99 ≥ 3 × reference **and** p99 ≥ 50 ms. Without a reference: p99 ≥ 50 ms |
| Multi-item — `Query`, `Scan`, `BatchGetItem`, `BatchWriteItem` | p50 ≥ 2 × reference **and** p50 ≥ reference + 5 ms | p99 ≥ 3 × reference **and** p99 ≥ reference + 20 ms |
| Transactional — `TransactGetItems`, `TransactWriteItems` | as multi-item | as multi-item |

Multi-item and transactional operations **never** use an absolute threshold. Each operation is
compared only with its own reference, because no two operations share a meaningful baseline.

If the user states an SLO for an operation and statistic, also record the assessable periods
that breach it. An SLO breach is reported in its own right; it does not replace the tests
above. A p50 or `Average` objective is tested by `LT-03`; a p90, p99, or `Maximum` objective by
`LT-04`. An objective that names no operation applies to every active operation.

### Patterns

Per operation and statistic, from the elevated-period list:

| Pattern | Definition |
|---|---|
| `none` | no elevated periods |
| `isolated` | 1–2 elevated periods, and no run of 3 consecutive |
| `recurring` | ≥ 3 elevated periods, no run of 3 consecutive, and < 50% of assessable periods |
| `sustained` | a run of ≥ 3 consecutive elevated periods, **or** ≥ 50% of assessable periods |
| `not_assessable` | below the `SampleCount` floor, or no usable reference |

With 60-second periods, "3 consecutive" is three minutes; with 300-second periods it is fifteen.

### Coincidence

An event counter **coincides** with an operation's elevation when one of its non-zero periods
is the same period as, or immediately adjacent to, an elevated period of that operation.
Count coinciding periods; that count is the evidence the causal outcomes rest on.

## Severity definitions

| Severity | Meaning |
|---|---|
| **High** | Requests are failing or the elevated latency is sustained and service-side |
| **Medium** | Real and worth acting on, but bounded — a tail problem, a factor that needs a client-side change, or a cause with partial evidence |
| **Low** | Worth knowing, not urgent |
| **Info** | Context, or an explicit statement that something could not be evaluated |

## Confidence

Assign to the primary outcome. Start at the reference's confidence ceiling, then lower one step
for each that applies:

- coverage ratio of an affected operation below 0.9
- a causal outcome (`LT-01`, `LT-02`) resting on 1–2 coinciding periods, or on the
  no-elevation branch
- a relevant event counter is `NoData` rather than `recorded` / `none_recorded`
- any affected operation is `not_assessable` for the statistic the outcome rests on

Never below Low. State the reasons in the report, one line each.

## Selection order — evaluate every outcome, then choose

Evaluate **all** of `LT-01` … `LT-04` before choosing. The primary outcome is the first one in
this order that qualifies; every other one that qualified goes under **Also observed**.
`LT-00` overrides everything when it fires.

**`LT-05` is the catch-all, so every profile reaches exactly one primary outcome.** When
neither `LT-00` nor any of `LT-01` … `LT-04` qualifies, the outcome is `LT-05`, and every
sub-threshold observation — an isolated p50 period, a counter recorded but not causal, an
operation not assessable — goes under **Also observed** or the relevant `CF` rule.

### LT-00 [Info] · Indeterminate

Fires when **any** of these holds:

- every operation queried has `NoData` for `SuccessfulRequestLatency` — **unless** organic
  `SystemErrors` are recorded for an operation, in which case `LT-01` branch (c) applies: no
  successful latency because requests failed is a finding, not an absence of data, or
- every operation with data has `coverage_ratio < 0.5`, not explained by table age, or
- every operation with data is `not_assessable` for both p50 and p99, or
- `SystemErrors` **or** the throttle counters are `AccessDenied` or `ToolingFailure` for the
  operations that carry the traffic — because `LT-01` and `LT-02` cannot be evaluated, or
- no `LT-01` … `LT-04` condition qualifies — so `LT-05` is the only remaining candidate — but a
  relevant event counter is `NoData` (activity could not be confirmed) rather than
  `none_recorded`.

> **`LT-00` · Indeterminate — `[table]`**
>
> **Observed:** between `[start]` and `[end]`, `[what was missing: which metric, which status]`.
> `SuccessfulRequestLatency` covered `[coverage_minutes]` of `[window]` minutes
> (`[coverage_ratio]`). `[If table age explains it: The table was created [created], so a
> shorter series is expected.]`
>
> **Not established:** whether the latency is service-side, throttle-induced, or within
> normal variance — the signals that separate those were `[unavailable / absent / below the
> SampleCount floor]`.
>
> **Next:** `[the specific call, permission, or window that would settle it]`.

### LT-01 [High | Medium] · Service-side errors

Compute **organic** `SystemErrors` per operation and period as `SystemErrors` minus
`FaultInjectionServiceInducedErrors` for the same period (treat `none_recorded` FIS as 0).

Qualifies when, for at least one operation, organic `SystemErrors` are **persistent** —
non-zero in ≥ 3 periods, or totalling more than 0.1% of that operation's `SampleCount` — **and**
either:

- **(a) coincidence:** they coincide with that operation's p50- or p99-elevated periods in ≥ 1
  period, or
- **(b) retry branch:** no operation is elevated, but the user reports client-observed slowness,
  timeouts, or errors overlapping the error periods. Most AWS SDKs retry HTTP 500s
  automatically; a retried 500 adds client-perceived latency that `SuccessfulRequestLatency`
  does not show, or
- **(c) total failure:** organic `SystemErrors` are recorded for an operation that has **no**
  `SuccessfulRequestLatency` datapoints in the same periods — every request to it failed, so
  there is no successful latency to elevate. This qualifies on persistence alone.

`SystemErrors` that are recorded but not persistent, or do not coincide, **do not qualify** —
report them as `CF-05`. Errors that are entirely FIS-induced never qualify.

Severity **High** when organic errors are non-zero in ≥ 3 consecutive periods and either
coincide in ≥ 3 periods or meet branch (c); otherwise **Medium**.

> **`LT-01` · Service-side errors — `[operation]` on `[table]`**
>
> **Observed:** organic `SystemErrors` totalled `[n]` across `[m]` periods between `[first_ts]`
> and `[last_ts]`, against `[sample_count]` successful `[operation]` requests
> (`[rate]`%). `[FIS-induced errors in the same periods: [k] | none recorded.]`
> `[(a): They coincide with [c] elevated-latency periods: [timestamps]. | (b): No elevation in
> SuccessfulRequestLatency; the errors overlap the slowness you reported at [time]. | (c): No
> request to [operation] succeeded in those periods — every recorded request failed.]`
>
> HTTP 500 responses are server-side. Most AWS SDKs retry them automatically, so a request that
> eventually succeeds can still have taken longer from the client's point of view.
> `[If sustained: This is sustained, not occasional — [m] consecutive periods.]`
>
> **Not established:** that these errors are the whole explanation. `[List any other qualifying
> outcome or signal, or "No other signal was observed."]`
>
> **Next:** correlate the window with AWS Health (Service Health Dashboard and your Personal
> Health Dashboard), and log request IDs for the slow or failed requests. If the errors persist
> over a prolonged period, contact AWS Support with those request IDs.

### LT-02 [High | Medium] · Throttle-induced

Qualifies when a throttle counter — `ThrottledRequests` for an operation, table-level
`Read`/`WriteThrottleEvents`, or a GSI's `Read`/`WriteThrottleEvents` — is `recorded`, and
either:

- **(a) coincidence:** its non-zero periods coincide with the p50- or p99-elevated periods of a
  matching operation (reads with read operations, writes and GSI write throttling with write
  operations) in ≥ 1 period, or
- **(b) retry branch:** no operation is elevated, the counter is non-zero in ≥ 3 periods, and the
  user reports client-observed slowness overlapping those periods.

Severity **High** when coincidence covers ≥ 3 periods, or in branch (b) when the counter is
non-zero in ≥ 3 consecutive periods; otherwise **Medium**.

This rule exists because of a metric property that misleads reliably: throttled requests are
**not** in `SuccessfulRequestLatency`. The service-side curve can stay perfectly flat while the
client sees seconds of added time from SDK retries.

> **`LT-02` · Throttle-induced — `[table]`**
>
> **Observed:** `[counter and scope: ThrottledRequests for PutItem | WriteThrottleEvents on GSI
> orders-by-status | …]` totalled `[n]` in `[m]` periods,
> `[(a): coinciding with elevated [operation] latency at [timestamps] | (b): overlapping the
> slowness you reported, with SuccessfulRequestLatency flat at [x] ms]`.
>
> The AWS SDKs retry `ProvisionedThroughputExceededException` automatically, so throttled calls
> usually succeed eventually — and the retry wait is elapsed time your client experiences as
> latency. `SuccessfulRequestLatency` measures only *successful* requests, so it does not show
> that time. `ThrottledRequests` increments once per request however many events inside it were
> throttled, so `[n]` is a floor. `[If GSI: A GSI without enough write capacity throttles writes
> to the base table — the throttling here is at the index.]`
>
> **Not established:** which ceiling was hit — table or index capacity, a partition, an account
> limit, or an on-demand maximum. That diagnosis is outside this skill; see the handoff in
> `CF-04`.
>
> **Next:** hand off to throttling diagnosis with the details in `CF-04`. On the client side,
> check the SDK's existing retry configuration — the SDKs already retry throttling with
> backoff by default — and confirm the application is not adding its own fixed-interval retries
> on top.

### LT-03 [High | Medium] · Typical-latency elevation

Qualifies when, for at least one operation, the p50 pattern is `recurring` or `sustained`, or a
p50 / `Average` SLO the user stated is breached in ≥ 3 assessable periods.

Severity **High** when the pattern is `sustained`, the operation is singleton, and its p50 in
the elevated periods is ≥ 3× the reference (or ≥ 30 ms without a reference); otherwise
**Medium**.

> **`LT-03` · Typical-latency elevation — `[operation]` on `[table]`**
>
> **Observed:** `[operation]` p50 was elevated in `[m]` of `[assessable]` assessable periods
> (`[recurring | sustained]`; `[longest run: [r] consecutive]`) — `[x]` ms against a reference
> of `[ref]` ms (`[ratio]`×; reference: `[7-day baseline | absolute floor 10 ms | first third of
> the window]`). `Average` over the elevated periods: `[y]` ms. `[If an SLO was given: p50
> exceeded your [slo] ms objective in [k] periods.]`
>
> `[sustained: A persistent rise in Average or p50 — as distinct from a tail spike — is the
> signal AWS documents as genuine degradation of DynamoDB processing time, rather than normal
> variance.]` `[recurring: Typical latency rose repeatedly but not persistently — more than
> normal variance, less than the persistent rise AWS documents as degradation.]`
>
> **Not established:** *why* processing time rose. Documented possible factors include larger
> items, larger result sets, and condition or filter expressions; these metrics do not show
> which applies. `[Any contributing factor that fired, with its own evidence.]`
>
> **Next:** check the Service Health Dashboard and Personal Health Dashboard for the window.
> `[The measurement implied by the factors that fired.]` If nothing explains it and it
> persists, open a support case with request IDs from the elevated periods.

### LT-04 [Medium | Low] · Tail elevation

Qualifies when, for at least one operation, the p99 pattern is `isolated`, `recurring`, or
`sustained`, or a p90 / p99 / `Maximum` SLO the user stated is breached, while that operation's
p50 pattern is neither `recurring` nor `sustained`.

Severity:

| Condition | Severity |
|---|---|
| p99 pattern `recurring` or `sustained` | **Medium** |
| user SLO breached in ≥ 3 assessable periods | **Medium**, whatever the pattern |
| anything else that qualifies — p99 `isolated`, or an SLO breached in 1–2 periods | **Low** |

> **`LT-04` · Tail elevation — `[operation]` on `[table]`**
>
> **Observed:** p99 reached `[y]` ms in `[m]` of `[assessable]` assessable periods
> (`[pattern]`; `[timestamps or longest run]`), against a reference of `[ref]` ms
> `[(reference: …)]`, while p50 held at `[x]` ms. `[Each elevated period had ≥ 100 requests.]`
> `[If an SLO was given: p99 exceeded your [slo] ms objective in [k] periods.]`
>
> This is DynamoDB-side time: client activity and network time are excluded from this metric,
> so nothing on the client — connection setup included — can produce it.
> `[isolated: AWS documents occasional high-percentile spikes as expected, from background
> operations that maintain availability and durability, or transient infrastructure conditions.
> Two isolated periods fit that description.]`
> `[recurring or sustained: This is more than the occasional spike AWS describes as normal — it
> recurs, so it is worth acting on if this operation's tail matters to your application.]`
>
> **Not established:** the cause of the tail. These metrics cannot see which requests were
> slow or why.
>
> **Next:** `[isolated, no SLO breach: no action unless it breaks an objective.]`
> `[recurring, sustained, or SLO breach: log request IDs for slow requests from these periods —
> they are what a support case needs if this persists; and if the tail must be bounded in the
> application, the documented lever is request hedging — see Recommended Actions for its
> preconditions.]` Do **not** respond by lowering socket timeouts; see
> `references/dynamodb-facts.md`.

### LT-05 [Info] · No DynamoDB-side elevation

The catch-all: fires when `LT-00` did not fire and none of `LT-01` … `LT-04` qualified.

That covers profiles with sub-threshold observations — an `isolated` p50 period, an error or
throttle counter `recorded` but not causal, an operation that was not assessable. Each of those
appears under **Also observed** or its `CF` rule; none is dropped, and none changes the outcome.

> **`LT-05` · No DynamoDB-side latency elevation — `[table]`**
>
> | Operation | `SampleCount` | p50 | p99 | `Average` | Reference p50 / p99 |
> |---|---|---|---|---|---|
> | `[op]` | `[n]` | `[x]` ms | `[y]` ms | `[z]` ms | `[a]` / `[b]` ms |
>
> **Observed:** no assessable operation showed a recurring or sustained p50 elevation or any
> p99 elevation against its reference. `[No SystemErrors and no throttle events were recorded
> for active operations in the window. | Error or throttle events were recorded but did not meet
> the bar for a cause — see Also observed.]` `[If any operation was not assessable: [op] had too
> few requests to assess — see CF-08.]`
>
> **Not established:** where your users' latency is going. `SuccessfulRequestLatency` measures
> time inside DynamoDB only — client activity and network time are excluded — and counts only
> successful requests. A normal value here rules out DynamoDB processing time; it does not
> identify the client, the SDK, or the network as the cause. That needs a measurement taken on
> the client side.
>
> **Next:** `[If the user reports slowness: see CF-01.]`

## Also observed

Render under the primary outcome, one line each, most significant first:

- every other `LT-01` … `LT-04` condition that qualified, with its own evidence — e.g.
  "Also qualifies as `LT-02` Throttle-induced: `WriteThrottleEvents` coincide in 4 periods"
- `CF-05` when `SystemErrors` were recorded but did not qualify for `LT-01`
- throttle counters recorded but not qualifying for `LT-02` (their evidence is in `CF-04`)
- p99 elevation on an operation whose p50 drove `LT-03`
- an `isolated` p50 elevation (1–2 periods) that did not qualify for `LT-03`
- any SLO breach not already in the primary outcome
- any operation not assessable (detail in `CF-08`)

If nothing else was observed, write "No other signal was observed."

## Contributing factors

Report each one that fires, under the primary outcome. Several may fire together.

### CF-01 [Medium] · Not explained by DynamoDB-side metrics

Fires when the user reports slowness, timeouts, a slow first call, or slowness after idle,
**and** the primary outcome is `LT-05`, or `LT-04` with an `isolated` pattern — i.e. the
DynamoDB-side signals do not account for what the user describes.

> **`CF-01` · What you are seeing is not explained by DynamoDB-side metrics**
>
> **Observed:** `[operation]` service-side latency was `[x]` ms p50 / `[y]` ms p99, with no
> recurring or sustained elevation. `[No throttling or service errors were recorded. | Throttle
> or error events were recorded but do not coincide with what you describe — see Also
> observed.]` You reported `[symptom]` `[at time]`.
>
> **Not established:** the cause. The time you are seeing is outside what
> `SuccessfulRequestLatency` measures, so it is not visible here. Candidate places it can be,
> none of which these metrics can confirm or rule out:
> - SDK retries of failed attempts, and the client's timeout and retry configuration
> - connection setup — `[If first-call-after-idle was reported: a slow first request followed
>   by fast ones is consistent with connection setup cost; whether that applies depends on the
>   SDK's connection-reuse default, which you can check in references/dynamodb-facts.md.]`
> - the network path — DNS resolution, VPC endpoint or NAT routing, cross-Region distance
> - the client process itself — CPU, thread or connection-pool exhaustion, garbage collection
>
> **Next:** measure the client. Enable latency metric logging in the AWS SDK, or trace one
> slow request end to end in your application telemetry, and compare its total against the
> `[x]` ms service-side figure. If DNS or VPC endpoint behaviour is suspected, hand off to the
> `aws-vpc-dns-investigation` skill.

### CF-02 [Info] · Mean item size — background context

Fires only alongside `LT-03`, when `mean_item_size_bytes.status` is `ok` and the mean is
≥ 50 KB. Never carries a severity above Info.

Does **not** fire when the status is `stale` — say mean item size could not be determined.

> **`CF-02` · Mean item size — context only**
>
> **Observed:** `TableSizeBytes / ItemCount` gives a table-wide mean of `[n]` KB per item, from
> metadata that refreshes roughly every six hours.
>
> **Not established:** that item size explains the elevation. Item size is a documented
> latency factor, but this is a static, table-wide mean: it cannot explain a *change* in
> latency, and it says nothing about the items the slow requests touched.

### CF-03 [Info | Low] · Multi-item operation — result-set evidence

Fires when an operation that qualified for `LT-03` or `LT-04` is `Query`, `Scan`, `Batch*`, or
`Transact*`.

When `ReturnedItemCount` was collected (`Query`, `Scan`), compare average items returned per
request in the elevated periods with the baseline value. **Low** when it rose ≥ 1.5×;
otherwise **Info**.

> **`CF-03` · The elevated operation is multi-item — `[operation]`**
>
> **Observed:** `[ReturnedItemCount: items returned per request averaged [b] in the elevated
> periods against [a] in the baseline ([ratio]×) | did not change materially ([a] → [b]) | was
> not collected for this operation.]`
>
> Multi-item latency varies with the size of the result set, the complexity of the structures
> returned, and any condition or filter expressions applied.
>
> **Not established:** `[If it rose: that the larger result sets caused the elevation — they
> coincide with it, which makes them the leading candidate. | If unchanged: result-set growth
> does not explain this; the returned count is flat. Note that ReturnedItemCount counts items
> returned, not items evaluated, so a filter that discards more items would not show here.]`
>
> Request-shape levers — client-side, and specific to the operation:
> - `Query` / `Scan`: bound the page with `Limit`, narrow `ProjectionExpression` to the
>   attributes actually used, and avoid filter expressions that read many items to return few —
>   a filter is applied *after* the read, so discarded items were already paid for in both
>   latency and capacity.
> - `BatchGetItem`: narrow `ProjectionExpression`; fewer keys per call returns less per call.
> - `BatchWriteItem`, `TransactWriteItems`, `TransactGetItems`: the levers are fewer items per
>   call and smaller items. For transactions, AWS recommends not grouping operations that do not
>   need to be atomic — simpler transactions are more likely to succeed — and each transactional
>   item costs two underlying reads or writes.
>
> Whether the access pattern needs a different key schema or index is a data-model question,
> and outside this skill.

### CF-04 [Info] · Throttling handoff

Fires whenever any throttle counter is `recorded` — whether or not `LT-02` is the primary
outcome. It carries the evidence; it does **not** diagnose the ceiling or size capacity.

> **`CF-04` · Throttling detected — handoff for diagnosis**
>
> | Field | Value |
> |---|---|
> | Table | `[table]` (`[billing mode]`, created `[created]`) |
> | Throttled scope | `[base table | GSI [name]]` |
> | Operation(s) | `[operations with ThrottledRequests recorded]` |
> | Counters | `[ThrottledRequests n · ReadThrottleEvents n · WriteThrottleEvents n]` |
> | Non-zero periods | `[first_ts] → [last_ts]`, `[m]` periods |
> | Coincides with latency | `[yes, [c] periods | no]` |
> | Capacity in those periods | `[peak consumed [x] units/s vs provisioned [y] units/s ([pct]%) — or on-demand: peak consumed [x] units/s]` |
>
> Convert consumed capacity to a rate before comparing: CloudWatch `Sum` for a period divided by
> the period length in seconds gives units per second, which is what provisioned capacity is
> expressed in.
>
> Which ceiling was hit — table or index capacity, a single partition, an account limit, or an
> on-demand maximum — is read from the cause-specific throttle metrics and the throttling
> exception's reason, and is outside this skill. Use your Agent Space's throttling or quota
> diagnostic if it has one, with the details above.

### CF-05 [Info | Low] · Service errors recorded, not established as cause

Fires when `SystemErrors` were `recorded` for any operation but `LT-01` did not qualify — not
persistent, not coinciding with elevation, or entirely FIS-induced. **Low** when organic errors
are non-zero in ≥ 2 periods; otherwise **Info**.

> **`CF-05` · `SystemErrors` recorded — not established as the cause**
>
> **Observed:** `[n]` `SystemErrors` on `[operation]` in `[m]` periods (`[timestamps]`).
> `[Of these, [k] were FIS-induced (FaultInjectionServiceInducedErrors) — an experiment was
> running. | None were FIS-induced.]`
>
> **Not established:** that they caused the latency — `[they do not coincide with any elevated
> period | they are not persistent | they are all experiment-induced]`. Occasional HTTP 500s are
> expected in a distributed system and are retried by the SDKs.
>
> **Next:** `[If organic: keep the request IDs of any failed requests; if errors recur or
> persist, they are worth a support case.]`

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
> So this is a freshness/latency trade, not a fix. Choose it per read path, not globally.

### CF-07 [Low] · Client-to-endpoint distance

Fires only when the user states where the client runs and it is a different Region from the
table, or when `Replicas[]` is empty and the user describes globally distributed users.

> **`CF-07` · Client and table are in different Regions**
>
> **Observed:** you described the client running in `[client region]`; the table is in
> `[table region]`.
>
> **Not established:** how much time that adds — cross-Region network time is not in
> `SuccessfulRequestLatency` at all. Client-side timing would show it.
>
> The documented lever is reducing the distance: Global Tables replicate to Regions you choose,
> placing a copy closer to users. Replication is asynchronous, and a replica serves eventually
> consistent reads.

### CF-08 [Info] · Partial coverage or low volume

Fires when any operation's `coverage_ratio < 0.9`, or any operation has low-volume periods
excluded by the `SampleCount` floor, while `LT-00` did not fire.

> **`CF-08` · Partial coverage — `[operation]`**
>
> **Observed:** `[datapoints span [coverage_minutes] of [window] minutes ([coverage_ratio]) |
> [k] of [total] periods had too few requests to read p99 (fewer than 100) / p50 (fewer than
> 10) and were excluded]`. `[Reason if known: the table was created [created] | the operation
> was not called for part of the window.]`
>
> The findings above rest on the covered, assessable periods only.

### CF-09 [Info] · Asked but not measurable

Fires whenever the user asks for something these metrics cannot answer. Use it rather than
answering anyway.

> **`CF-09` · `[what was asked]` is not measurable from what this skill collects**
>
> `[The specific reason.]` Examples that come up in this analysis:
> per-index latency — `SuccessfulRequestLatency` has `TableName`, `Operation`, and
> `StreamLabel` dimensions and no index dimension; the share of reads using strong consistency
> — no metric distinguishes consistent from eventually consistent reads; which partition key is
> hot — that needs Contributor Insights traffic analysis, which is outside this skill; and
> per-table client errors — `UserErrors` is aggregated across the account and Region.
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
| `LT-05` fired | no text states or implies the client, SDK, or network *is* the cause — only that DynamoDB processing time was not elevated |
| `CF-01` fired | the report names a client-side measurement as the next step, and presents every candidate as unconfirmed |
| `LT-04` fired | no client-side mechanism (cold start, connection setup, idle connection) is offered as the cause of the tail, no timeout reduction is recommended, and `isolated` is not called degradation |
| `LT-01` fired | the coinciding periods or the reported-slowness overlap are named; FIS errors are excluded from the count |
| `SystemErrors` recorded and `LT-01` did not fire | `CF-05` appears; the errors are not described as the cause |
| `LT-02` fired | the report does not attribute the latency to the request path, names the coinciding periods or the overlap, and includes `CF-04` |
| Any throttle counter recorded | `CF-04` appears, even when `LT-02` is not primary |
| More than one `LT` condition qualified | all but the primary appear under **Also observed** |
| A counter is `NoData` | no conclusion that depends on it is asserted, and it is not written as "0" or "none recorded" |
| A counter is `none_recorded` | it is written as "no … recorded", never "measured 0" |
| `CF-06` fired | strongly consistent reads are not presented as a latency improvement |
| Mean item size is `stale` | `CF-02` did not fire, and mean item size is reported as not determinable |
| `UserErrors` appears anywhere | it is labelled account-wide, not attributed to the table |
