# Finding Logic

Every threshold, severity rule, and body template for the four dimensions. Use the
templates **verbatim**, substituting only `<placeholders>`. Do not reword, merge, or
summarize findings.

**Cite the exact rule ID that fired.** Write `TTL-04`, not "TTL-01 style" or "a TTL
finding". The IDs distinguish materially different diagnoses — TTL-01 is *TTL deleted
nothing*, TTL-04 is *the timestamps are malformed* — and they are how a reader
verifies your reasoning against this file. If you are unsure which rule applies,
re-read its trigger rather than hedging the label.

Each rule is tagged **[A]** (Phase A, no sampling needed) or **[B]** (requires a
completed sample). Skip **[B]** rules when `sampling.status != "completed"` and list
them in the report's "Not assessed" section with the reason.

## Severity definitions

| Severity | Meaning |
|---|---|
| **High** | Causing failures now, or will cause failures without intervention (hard limit approach, silent data retention failure, sustained waste) |
| **Medium** | Degrading cost or performance; no failure yet |
| **Low** | Suboptimal; worth knowing during the next design review |
| **Info** | Observation with no action required |

### Confidence downgrade rule

For any **[B]** finding, if `items_sampled < 100` **or** `pct_of_table < 0.01`,
downgrade the severity by one level (High→Medium, Medium→Low) and append:

> Severity downgraded one level: the sample of `<N>` items is `<pct>`% of the table,
> too small to support the full severity.

Never downgrade below Info. Never upgrade a **[B]** finding above the level its rule
assigns, however striking the sample looks.

---

## Dimension 1 — Item Size

### IS-01 [B] · Item approaching the 400 KB limit · **High**

Trigger: any sampled item size ≥ **350 KB** (87.5 % of the 400 KB hard limit).

> **`<count>` sampled item(s) are within 12.5 % of the 400 KB item size limit** —
> the largest is `<max_size>`. A write that pushes an item past 400 KB fails with
> `ValidationException` **and is rejected in full** — nothing is partially written, and an
> item over 400 KB cannot exist in the table. The failure surfaces in the application, not in
> a DynamoDB metric. See `references/dynamodb-facts.md` before describing this mechanism. Items this large also cost `<rcu>` RCU per eventually-consistent
> read, so every read of them is `<multiple>`× the cost of a 4 KB item.
> Attributes contributing most to size: `<top_3_attribute_names>`.
>
> Remediation: move the largest attributes to Amazon S3 and store the object key in
> the item, or split the item vertically across sort-key rows. Add an
> application-side guard that rejects or offloads items above a threshold you
> choose, so the 400 KB ceiling is never reached in production.
> Confidence: `<confidence>`.

If the table has LSIs, append:

> This table has local secondary indexes, so the 400 KB limit applies to the item
> **plus** its projected entries in every LSI combined — the effective headroom for
> the base item is lower than 400 KB.

### IS-02 [B] · Large mean or p99 item size · **Medium**

Trigger: sampled `p99 ≥ 100 KB`, or `mean ≥ 64 KB`.

> **Item sizes are large: p99 `<p99>`, mean `<mean>`, max `<max>`.** DynamoDB bills
> reads in 4 KB units and writes in 1 KB units, so a `<mean>` mean item size makes
> every read cost at least `<read_units>` RCU and every write at least
> `<write_units>` WCU. `Query` and `Scan` throughput is bounded by bytes, not item
> count, so pagination will return fewer items per page than the application may
> expect. Attributes contributing most to size: `<top_3_attribute_names>`.
>
> Remediation: project only the attributes each access pattern needs, offload large
> blobs to S3, and consider compressing large text attributes before writing.
> Confidence: `<confidence>`.

### IS-03 [B] · Item size skew · **Medium**

Trigger: `max / median ≥ 20` **and** `max ≥ 16 KB`.

> **Item sizes are highly uneven — the largest sampled item (`<max>`) is
> `<ratio>`× the median (`<median>`).** Uneven item sizes make capacity planning
> unreliable: provisioning or on-demand scaling derived from an average request cost
> will under-provision whenever traffic hits the large items, producing throttling
> that looks random. Histogram: `<histogram>`.
>
> Remediation: identify the access patterns that touch the large items and size
> capacity for those, or normalize the schema so item size is more uniform.
> Confidence: `<confidence>`.

### IS-04 [B] · Attribute bloat · **Low**

Trigger: a single attribute name accounts for ≥ **40 %** of total sampled bytes, or
mean attribute count per item ≥ **50**.

> **Attribute `<attribute_name>` accounts for `<pct>`% of sampled item bytes**
> (mean `<attr_mean>` per item across `<items_with>` of `<n>` sampled items).
> `<other_observation>` Because an attribute's **name** counts toward item size as
> well as its value, wide items with long attribute names carry measurable overhead
> on every read and write.
>
> Remediation: move this attribute to S3 if it is a blob, or to a separate item if
> it is only needed by some access patterns. Shorten long attribute names on
> high-volume items. Confidence: `<confidence>`.

### IS-05 [A] · Mean item size from table metadata · **Info**

Always emit when `size.status == "OK"` and `item_count > 0`. This is the zero-cost
item-size signal and must appear even when sampling is declined.

> **Mean item size is approximately `<mean_item_size>`** (`<table_size>` across
> `<item_count>` items). `ItemCount` and `TableSizeBytes` are refreshed by DynamoDB
> roughly every six hours, so this is an approximation and cannot show the size
> *distribution* — a table with a healthy mean can still hold items near the 400 KB
> limit. `<sampling_note>`

Where `<sampling_note>` is, when sampling did not complete: "Item size distribution
and 400 KB proximity were not assessed because `<sampling_reason>`."

---

## Dimension 2 — Hot Keys

Contributor Insights is authoritative. Sampling can only speak to item-count
concentration.

### HK-01 [A] · Contributor Insights not enabled · **Medium**

Trigger: `hot_keys.status == "NotConfigured"`, or every target's `ci_status != "ENABLED"`.

> **CloudWatch Contributor Insights is not enabled for `<targets>`, so hot keys
> cannot be determined.** Contributor Insights is the only mechanism that reports
> which partition keys receive the most traffic and which are throttled; without it,
> a hot partition can only be inferred, never identified. In
> **throttled-keys-only** mode it incurs no charge unless throttling actually
> occurs, which makes it inexpensive to leave enabled on production tables.
>
> Remediation: enable Contributor Insights in throttled-keys-only mode on the base
> table **and on each GSI separately** — GSIs require their own enablement. Re-run
> this inspection after a throttling window to identify the contributing keys.
> LSIs need no separate enablement; their activity appears under the base table's
> keys because they share the base table's partitions.

### HK-02 [A] · Hot key confirmed with throttling · **High**

Trigger: top contributor's value ≥ **3×** the second contributor's, **and** throttling
is observed — satisfied by **either** of:

| Evidence | Strength |
|---|---|
| `throttling.key_range.*_sum_14d > 0` | **Strong** — the key-range metric proves a single partition exceeded its ceiling |
| `throttling.key_range` is `NoData`/`NotAvailable` **and** `ReadThrottleEvents`/`WriteThrottleEvents`/`ThrottledRequests > 0` | **Corroborating** — throttling is real but the partition-level attribution comes from Contributor Insights alone |

Do not require the key-range metric. Across ~1,275 real hot-partition support cases,
throttling was the presenting symptom in **93.6%** but the key-range metric was cited
in only **12.2%**, while Contributor Insights was cited in **63.5%**. Gating this rule
on key-range alone would suppress the majority of genuine hot partitions.

State which evidence you had. With only the corroborating path, say the partition-level
attribution rests on Contributor Insights and add: *"enable an alarm on
`WriteKeyRangeThroughputThrottleEvents >= 1` to get direct partition-level confirmation
on the next occurrence."*

> **Partition key `<key_digest>` is a confirmed hot partition.** Contributor
> Insights ranks it at `<top_value>` versus `<second_value>` for the next key
> (`<ratio>`× higher), and the table recorded `<key_range_events>`
> key-range throughput throttle events over `<window>`. A key-range throttle event
> is the direct signal that a single partition's hard ceiling — **1,000 WCU/s and
> 3,000 RCU/s** — was exceeded, independent of how much capacity the table has in
> aggregate. Aggregate consumed capacity over the same window was
> `<consumed_summary>`.
>
> Remediation, in the order real cases are resolved:
> 1. **Handle the throttles the client already sees** — retry with exponential backoff
>    plus full jitter, and resubmit `UnprocessedItems` from `BatchWriteItem`. This is
>    the single most common resolution and it stops data loss today, before any
>    re-modelling.
> 2. **Give the table headroom** — raise provisioned capacity (which also adds backend
>    partitions) or move to on-demand. This buys time; it does not fix a key whose
>    traffic exceeds one partition's ceiling.
> 3. **Raise the key's cardinality** — write sharding: append a calculated suffix to the
>    partition key so traffic spans partitions, and scatter-gather on read. This is the
>    durable fix, and the only one that removes the ceiling.
> 4. **For a read-heavy hot key**, add DAX or an application cache in front of the table.
>
> Steps 1 and 2 are mitigations and step 3 is the cure — say so, so the operator does
> not stop at step 2 and meet the same ceiling at the next traffic peak.

### HK-03 [A] · Traffic concentration without throttling · **Medium**

Trigger: top contributor's value ≥ **3×** the second's, and no key-range throttle
events in the window.

> **Partition key `<key_digest>` receives disproportionate traffic
> (`<top_value>` versus `<second_value>` for the next key, `<ratio>`× higher) but is
> not yet throttling.** Every physical partition is capped at 1,000 WCU/s and
> 3,000 RCU/s, so a concentration this uneven means the table's practical throughput
> ceiling is set by this one key rather than by its provisioned or on-demand
> capacity. A traffic increase on this key will throttle even though the table
> appears to have headroom.
>
> Remediation: raise the key's cardinality before the next traffic peak — write
> sharding, or a partition key that includes a naturally high-cardinality component.
> Alarm on `WriteKeyRangeThroughputThrottleEvents` and
> `ReadKeyRangeThroughputThrottleEvents` at `>= 1` so the transition to throttling
> is detected immediately.

### HK-04 [A] · Throttling with no identified contributor · **High**

Trigger: `throttling.key_range.*_sum_14d > 0` **and** `hot_keys` has no
contributors (either `NotConfigured`, or enabled but empty).

> **The table recorded `<key_range_events>` key-range throughput throttle events
> over `<window>`, but the contributing key could not be identified.**
> `<reason>` Key-range throttling proves a single partition exceeded its 1,000 WCU/s
> or 3,000 RCU/s ceiling; without Contributor Insights data the specific key remains
> unknown, so remediation cannot be targeted.
>
> Remediation: enable Contributor Insights in throttled-keys-only mode on the table
> and each GSI, then re-run after the next throttling window. Meanwhile the
> cause-specific throttle metrics already available will localize the throttle to
> the partition, table, account, or on-demand-max level even without the key.

### HK-05 [B] · Item-count concentration in the sample · **Low**

Trigger: the most frequent sampled partition key holds ≥ **20 %** of sampled items,
and `table_size_bytes > 10 GB`.

> **Partition key `<key_digest>` holds `<pct>`% of the `<n>` sampled items.** This
> measures how items are *stored*, not how traffic is *distributed* — a `Scan`
> returns items in partition-layout order, so this is a storage-skew observation and
> is not evidence of a hot partition. It matters because a partition key holding a
> large share of a `<table_size>` table concentrates both storage and any traffic
> that targets those items.
>
> Remediation: confirm or rule out a traffic problem with Contributor Insights
> before acting. If this key is also hot in Contributor Insights, treat HK-02 or
> HK-03 as the actionable finding. Confidence: `<confidence>`.

---

## Dimension 3 — TTL Effectiveness

### HK-06 [A] · Contributor Insights enabled but returned no data · **Low**

Trigger: `hot_keys.status == "NoData"` — status `ENABLED` and rules present, but zero
contributors after retrying the window at 24 hours.

> **Contributor Insights is enabled for `<targets>` but returned no contributors over
> the last `<window>`, so hot keys are not determinable from this run.** An enabled
> rule with no contributors is an empty window, not a verdict: Contributor Insights
> takes time to populate after being enabled, and in **throttled-keys-only** mode the
> throttled-key rules emit nothing at all unless throttling occurred — which, if the
> table is healthy, is the expected and desirable result.
>
> Remediation: if Contributor Insights was enabled recently, re-run this inspection
> after the table has served a representative traffic period. If it has been enabled
> for some time and the mode is throttled-keys-only, the empty result is consistent
> with a table that is not throttling — corroborate with the throttle metrics in this
> report rather than concluding anything from the empty rule.

This rule exists to close a specific hole: without it, an enabled-but-empty
Contributor Insights produces no hot-key finding at all, and the dimension renders as
though it had been assessed and found healthy. Mark the hot-key dimension ❓, never ✅.

### TTL-01 [A] · TTL enabled but deleting nothing · **High**

Trigger: `ttl.state == "ENABLED"` **and** `ttl.deleted_item_count.status == "OK"`
**and** `sum_14d == 0`.

> **TTL is enabled on attribute `<ttl_attribute>` but has deleted zero items in the
> last 14 days** (`TimeToLiveDeletedItemCount` sum = 0). TTL is enabled and running,
> so a zero deletion count means no item currently carries a valid, expired,
> Number-typed timestamp in that attribute. The table is paying to store data that
> the retention policy intends to remove, and the storage will grow without bound.
> `<growth_note>`
>
> Remediation: verify the attribute name in the TTL configuration matches the
> attribute the application actually writes, and that it is stored as a **Number**
> in **Unix epoch seconds**. A single mismatch — a different name, a string type, or
> milliseconds instead of seconds — makes TTL silently no-op with no error and no
> metric. `<sampling_pointer>`

`<growth_note>`: when `size_trend_bytes_per_day` is known and positive, "Table size
is growing at approximately `<rate>` per day." Otherwise, "Table size trend was not
measured in this run; `TableSizeBytes` is a point-in-time value."

`<sampling_pointer>`: when a sample completed, "The per-item findings below identify
which of these applies." Otherwise, "Re-run with data-plane sampling approved to
determine which of these applies."

### TTL-02 [A] · TTL deletion metric never published · **Medium**

Trigger: `ttl.state == "ENABLED"` **and** `ttl.deleted_item_count.status == "NoData"`.

> **TTL is enabled on attribute `<ttl_attribute>`, but `TimeToLiveDeletedItemCount`
> published no data points over the last 14 days.** This is weaker evidence than a
> measured zero: the metric is emitted only when TTL processes deletions, so no data
> points is consistent with TTL never having deleted anything, and also with the
> metric not being available for this table. It cannot be read as confirmation that
> TTL is working.
>
> Remediation: confirm the TTL attribute name, type (**Number**), and units
> (**epoch seconds**) against what the application writes. Alarm on
> `TimeToLiveDeletedItemCount` with `Sum` over 24 h so a silent TTL failure is
> detected rather than discovered through a storage bill.

### TTL-03 [B] · TTL attribute missing from items · **High**

Trigger: `missing` fraction of sampled items > **5 %**.

> **`<pct>`% of sampled items (`<count>` of `<n>`) have no `<ttl_attribute>`
> attribute.** DynamoDB never expires an item that lacks the configured TTL
> attribute; those items are retained permanently regardless of the table's TTL
> setting, and no error or metric reports this. Extrapolated across
> `<item_count>` items, roughly `<extrapolated>` items are outside the retention
> policy.
>
> Remediation: set the TTL attribute on every write path that creates items in this
> table, including backfills, migrations, and any writer that predates TTL being
> enabled. Backfill the attribute on existing items that should expire.
> Confidence: `<confidence>`.

### TTL-04 [B] · TTL attribute malformed · **High**

Trigger: any `malformed_type`, `malformed_value`, or `malformed_scale` observed.

> **`<pct>`% of sampled items (`<count>` of `<n>`) carry a `<ttl_attribute>` value
> that TTL cannot act on:** `<breakdown>`. DynamoDB requires a **Number** attribute
> in **Unix epoch seconds**; it silently ignores attributes of any other type, and a
> millisecond-scale value resolves to a date thousands of years in the future, so
> the item never expires. Neither case raises an error or increments a metric.
>
> Remediation: correct the writer to emit epoch **seconds** as a Number, then
> backfill the affected items. A millisecond value divided by 1,000 recovers the
> intended timestamp. Confidence: `<confidence>`.

`<breakdown>` enumerates only the classes actually observed, e.g. "`<n1>` stored as
a String (type `S`), `<n2>` at millisecond scale".

### TTL-05 [B] · Expired-item backlog · **Medium**

Trigger: fraction of sampled items expired **more than 7 days ago** > **10 %**.

> **`<pct>`% of sampled items (`<count>` of `<n>`) expired more than 7 days ago and
> are still present.** DynamoDB deletes expired items typically within a few days of
> expiry, so a backlog beyond seven days exceeds the documented window. Until they
> are deleted these items occupy storage, count toward `ItemCount`, and are returned
> by `Query` and `Scan` unless the application filters them out. Recency breakdown:
> `<recency_breakdown>`.
>
> **TTL deletion is asynchronous and its throughput is bounded by backend capacity DynamoDB
> allocates — it does not consume your provisioned capacity, does not appear in
> `ConsumedWriteCapacityUnits`, and cannot be accelerated by the customer.** A backlog is
> therefore expected behaviour up to a point, not a defect to fix. Do not quote a specific
> deletion SLA: current documentation says *within a few days*, not 48 hours. See
> `references/dynamodb-facts.md`.
>
> Remediation:
> 1. **Stop serving expired data now.** Add a `FilterExpression` on the TTL attribute in
>    every read path so the application never returns logically deleted items,
>    regardless of when DynamoDB gets to them. This is the fix that matters; it is under
>    your control and it removes the correctness problem immediately.
> 2. **If storage reclamation is the concern** and the backlog is sustained across
>    inspections, open a support case. A persistent backlog well beyond the documented
>    window is an AWS-side capacity matter.
> 3. **Do not** delete expired items yourself with a scan-and-delete job unless you
>    genuinely need the space back sooner — it consumes write capacity that TTL
>    deletion would have provided free.
>
> Confidence: `<confidence>`.

### TTL-06 [A] · TTL not configured · **Info**

Trigger: `ttl.state == "DISABLED"`.

> **TTL is not enabled on this table.** This is a design choice, not a defect — TTL
> only helps where data has a natural expiry. `<size_context>`
>
> Consider enabling it if this table stores sessions, events, logs, caches, or any
> record with a bounded useful life. TTL deletions do not consume write capacity in
> the region where the expiry occurs, which makes it materially cheaper than
> application-driven deletes. Note that in Global Tables the replicated delete does
> consume capacity in each replica region.

`<size_context>`: when `table_size_bytes > 100 GB`, "At `<table_size>` this table is
large enough that an expiry policy would have a measurable cost impact." Otherwise
omit.

---

## Dimension 4 — Index Utilization

### IX-01 [A] · Unused GSI · **High**

Trigger: GSI `consumed_read_sum_30d == 0` — a **measured zero**, not `null` (which
means the metric published no data and proves nothing) — **and**
`consumed_write_sum_30d > 0` **and** `metric_coverage_days >= 30`.

> **Check `metric_coverage_days` before firing this rule, every time.** It is
> computed per `data-collection.md` as `min(datapoints returned, table age in days)`
> — **not** the width of the window you queried. Asking for a 30-day window on a
> table created this morning still yields `metric_coverage_days = 0`.
>
> This rule recommends **deleting a customer's index**. Firing it on a few hours of
> data is a false High-severity finding that could destroy an index a batch job needs
> next week. If `metric_coverage_days < 30`, the correct rule is **IX-02** — no
> exceptions, no "but the read count is clearly zero". A zero over four hours is not
> evidence of thirty days of disuse.
>
> **Calibration from real cases:** a genuinely unused index is the *rarest* index
> problem in support data — roughly 3% of index-related cases, against 28% for item
> collection limits and 22% for over-broad projections. So treat a zero read count as
> a prompt to *ask the owner*, not as a conclusion. Always phrase the recommendation as
> "confirm with the owning application, then delete" — never "delete this index".

> **GSI `<index_name>` served zero reads in 30 days while consuming
> `<write_units>` write units.** An unread index is pure cost: every write to the
> base table that touches its key attributes is replicated into it, and it holds
> `<index_size>` of storage (`<amplification>`× the base table). It also adds a
> throttling surface — if this index throttles, it applies backpressure that blocks
> writes to the base table it is not serving.
>
> Remediation: confirm with the owning application that no query path uses this
> index, then delete it. Deleting a GSI does not affect the base table or its other
> indexes. If it exists for a rare batch or disaster-recovery query, document that
> so the next review does not re-raise this finding.

### IX-02 [A] · GSI with no read activity, insufficient metric history · **Low**

Trigger: `consumed_read_sum_30d == 0` **and** `metric_coverage_days < 30`.

> **GSI `<index_name>` served zero reads across the `<coverage>` days of metric
> history available.** The 30-day window used to identify unused indexes is not yet
> covered, so this is not sufficient evidence that the index is unused — a monthly
> batch job would not appear. It currently consumes `<write_units>` write units and
> `<index_size>` of storage.
>
> Remediation: re-check after 30 days of metrics accumulate. If the index was
> created for an access pattern that has not shipped yet, no action is needed.

### IX-03 [A] · GSI with no read activity and no write activity · **Medium**

Trigger: `consumed_read_sum_30d == 0` **and** `consumed_write_sum_30d == 0` — both
measured zeros, not `null` — **and** `index_size_bytes > 0`.

> **GSI `<index_name>` shows neither read nor write activity over 30 days, yet holds
> `<index_size>` of storage.** No writes reaching the index means the base table
> itself is not receiving writes that match the index's key schema — either the
> table is dormant or the index keys on attributes the current writers do not set.
> Either way it is storage cost with no observed purpose.
>
> Remediation: determine whether the base table is still in active use. If it is,
> check whether the index's key attributes are still written by the application.

### IX-04 [A] · Over-broad GSI projection · **Medium**

Trigger: `projection_type == "ALL"` **and** `amplification_ratio > 0.8`.

**If `amplification_ratio` is `null`** (because `IndexSizeBytes` or `TableSizeBytes`
is 0 from stale metadata), do **not** silently skip this rule — a full projection on
a large table is exactly what it exists to catch. Emit it at **Low** instead, with
the ratio replaced by: "Storage amplification could not be computed because
`IndexSizeBytes`/`TableSizeBytes` still read 0; DynamoDB refreshes them about every
six hours. Re-run once they populate to quantify the overhead." Never let a
non-computable ratio read as a passing check.

> **GSI `<index_name>` projects ALL attributes and occupies `<index_size>`,
> `<amplification>`× the base table's `<table_size>`.** A full projection duplicates
> every attribute into the index, so both storage and write cost are roughly doubled
> for items the index covers. That is the right trade only when queries against the
> index genuinely need most attributes.
>
> Remediation: identify the attributes the index's queries actually read and switch
> to `INCLUDE` with just those, or `KEYS_ONLY` if the query can fetch the full item
> from the base table afterwards. Projection cannot be changed in place — create a
> replacement index with the narrower projection, migrate the query, then delete the
> original.

### IX-05 [A] · GSI missing independent autoscaling · **Medium**

Trigger: `billing_mode == "PROVISIONED"` **and** (`autoscaling.read == false` or
`autoscaling.write == false`).

> **GSI `<index_name>` lacks autoscaling on `<dimensions>`.** GSIs have their own
> provisioned capacity — which may be set higher than the base table's — and scale
> independently of it — enabling
> autoscaling on the table does not extend to its indexes. An index left at fixed
> capacity throttles when traffic grows, and a throttled GSI applies backpressure
> that blocks writes to the base table.
>
> Remediation: register an Application Auto Scaling target for this index on both
> `dynamodb:index:ReadCapacityUnits` and `dynamodb:index:WriteCapacityUnits`, or
> move the table to on-demand capacity mode where per-index scaling is automatic.

### IX-06 [A] · GSI throttling · **High**

Trigger: `read_throttle_sum_14d > 0` or `write_throttle_sum_14d > 0`.

> **GSI `<index_name>` is throttling** (`<read_events>` read, `<write_events>` write
> throttle events over `<window>`). A throttled GSI does not fail in isolation: it applies
> backpressure to the base table, so base-table writes are rejected even when the base table
> has capacity to spare. Note the mechanism — GSI propagation is **asynchronous**, and it is
> the index's own exhausted write capacity that ultimately fails the base-table write, not
> synchronous propagation. See `references/dynamodb-facts.md`. This is the usual explanation for
> "the table throttles but consumed capacity is low".
>
> Remediation: raise this index's capacity or enable autoscaling on it, and check
> whether its key schema concentrates traffic on one partition. Note that a GSI
> needs Contributor Insights enabled separately from the base table to identify its
> own hot keys.

### IX-07 [A] · LSI with full projection · **Low**

Trigger: LSI `projection_type == "ALL"`.

> **LSI `<index_name>` projects ALL attributes.** Every item in an LSI shares the
> base table's partition and counts toward the same item collection, which is capped
> at **10 GB** for tables that have LSIs. A full projection grows that collection at
> roughly the rate of the base data, so it consumes the 10 GB budget fastest. Once a
> collection reaches the limit, further writes to that partition key fail with
> `ItemCollectionSizeLimitExceededException` — and an LSI's projection cannot be
> changed, nor can the LSI be dropped, after the table is created.
>
> Remediation: narrow the projection by replacing the LSI with a GSI, which has no
> item-collection limit and supports projection changes via replacement.

### IX-08 [A/B] · Item collection approaching the 10 GB limit · **High**

Trigger: table has ≥ 1 LSI **and** the estimated item collection size ≥ **8 GB**.

> **This is the highest-value index check.** Item collection limits account for ~28% of
> index-related support cases — nearly ten times the rate of genuinely unused indexes.
> When a table has LSIs, estimate the collection size even if nothing else looks wrong,
> and prioritise this finding above projection and utilization findings in the report.
> The failure it predicts is abrupt and key-specific: writes to one partition key start
> failing while every other key keeps working, which reads to the application as
> intermittent and is hard to attribute without this check.

> **An item collection on this table is estimated at `<estimate>`, against the
> 10 GB limit that applies to tables with local secondary indexes.** The estimate
> covers partition key `<key_digest>`, derived from `<method>`. All items sharing a
> partition key across the base table and every LSI count toward this single limit.
> When it is reached, every further write to that partition key fails with
> `ItemCollectionSizeLimitExceededException`, while other partition keys keep
> working — so the failure looks intermittent and key-specific.
>
> This figure is an **estimate**. The exact size is only available from
> `ReturnItemCollectionMetrics=SIZE` on a write, which is outside this skill's
> read-only scope.
>
> Remediation: reduce what the LSIs project, move the access pattern to a GSI (no
> item-collection limit), or re-model so this partition key holds fewer or smaller
> items.

### IX-09 [A] · No secondary indexes · **Info**

Trigger: no GSIs and no LSIs.

> **This table has no secondary indexes,** so there is no index-utilization or
> projection cost to assess. Access is via the primary key only.

---

## "Unable to verify" template

For any check whose status was `AccessDenied` or `ToolingFailure`:

> **`<dimension>` could not be assessed** — `<check_name>` returned
> `<status>`. `<required_permission_or_retry_guidance>` No conclusion about
> `<dimension>` should be drawn from this report.

Never infer a state from a failed check, and never let a failed check produce a
"healthy" verdict for its dimension.

## Cross-reference consistency

Before rendering, verify the findings do not contradict each other:

| Check | Rule |
|---|---|
| HK-02 / HK-03 vs HK-04 | Mutually exclusive — HK-04 only when no contributor was identified |
| HK-01 vs HK-02 / HK-03 / HK-05 | If Contributor Insights is `NotConfigured`, HK-02 and HK-03 cannot fire |
| HK-01 vs HK-06 | Mutually exclusive — HK-01 is `NotConfigured` (never enabled), HK-06 is `NoData` (enabled, empty window) |
| HK-06 vs HK-02 / HK-03 | Mutually exclusive — no contributors means neither can fire |
| HK-01 / HK-04 / HK-06 vs the dimensions table | Any of these three forces the hot-key dimension to ❓, never ✅ |
| TTL-01 vs TTL-02 | Mutually exclusive — measured zero versus `NoData` |
| TTL-01 vs TTL-03 / TTL-04 | If TTL-01 fired and a sample completed, TTL-03 or TTL-04 should normally explain it. If neither fired, say so explicitly: the zero deletion count is unexplained by the sample. |
| TTL-06 vs all other TTL rules | If TTL is `DISABLED`, only TTL-06 applies |
| IX-01 vs IX-02 vs IX-03 | Mutually exclusive per index |
| IS-01 vs IS-05 | Both may fire; IS-05 must not be phrased so as to imply the distribution is healthy when IS-01 fired |
| Any [B] rule vs `sampling.status` | No `[B]` finding may appear unless `sampling.status == "completed"` or `"aborted"` with usable data |
| Any rule whose threshold divides by `TableSizeBytes` or `ItemCount` | If either is 0 or `null` from stale metadata, the rule must degrade to a stated-uncertainty finding (see IX-04) rather than silently not firing. A threshold that cannot be evaluated is not a passing threshold. |
### IX-10 [A] · Write amplification from indexes · **Medium**

Trigger: summed GSI `consumed_write_sum_30d` across all indexes ≥ **1.5×** the base
table's `consumed_write_sum_30d`.

Emit this whenever the ratio is met, even if no individual index looks wrong. It
answers a question customers arrive with directly — *"why is my write cost higher than
the writes I'm doing?"* — which the per-index rules above do not answer on their own.

> **Indexes are consuming `<ratio>`× the base table's write capacity**
> (`<gsi_total>` write units across `<n>` index(es) versus `<base>` on the table over
> `<window>`). Every write to the base table that touches an index's key or projected
> attributes is replicated into that index and billed again. With `<n>` index(es) on
> this table, a single logical write costs up to `<n+1>` physical writes, which is why
> the consumed capacity exceeds what the application appears to be writing.
> Per-index write consumption: `<per_index_breakdown>`.
>
> Remediation: narrow projections to the attributes each index's queries actually read
> (`KEYS_ONLY` or `INCLUDE` instead of `ALL`), and remove indexes no query path uses.
> Where an index only needs to cover a subset of items, a **sparse index** — keying on
> an attribute that most items omit — avoids replicating writes for items the index does
> not need to serve.

