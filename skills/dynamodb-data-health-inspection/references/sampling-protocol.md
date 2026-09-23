# Sampling Protocol (Phase B)

Bounded, consent-gated, value-redacting data-plane sampling. This is the only part
of the skill that reads customer items, and it is the only part that costs read
capacity on a live table. Every rule here is a ceiling, not a default to negotiate
upward.

## When Phase B runs

Only when **all** of these hold:

- Phase A completed and `dynamodb:Scan` was not `AccessDenied`
- `ItemCount > 0`
- The user's question needs per-item evidence — item size distribution, attribute
  shape, or per-item TTL timestamps
- The operator explicitly approved the sampling plan in this run, for this table

If any fails, skip Phase B, set `sampling: skipped` or `sampling: declined` with
the reason, and report Phase A findings.

## Refuse to sample when the table is already in trouble

If Phase A observed `ThrottledRequests > 0`, `ReadThrottleEvents > 0`, or
`*KeyRangeThroughputThrottleEvents > 0` **in the last hour**, do not present the
normal consent gate. Sampling adds read pressure to a table that is already
shedding requests. Present this instead and default to declining:

> ⛔ **`<table>` is actively throttling** (`<metric>` = `<value>` in the last hour).
> Sampling would add read load to a table that is already shedding requests.
>
> 1. **Do not sample (recommended).** Deliver control-plane findings now; sample
>    later once throttling has cleared.
> 2. Sample anyway with a reduced budget of 250 items. Only choose this if the
>    read capacity headroom is known to be sufficient.

## The consent gate

Compute the plan first, then present it, then **wait**. Never sample and then ask.
Consent is per table and per run — it does not carry over between tables in a
multi-table request, and never carries over between runs.

### You must aggregate in context — so bound the payload, not just the item count

**This is the constraint that shapes everything below.** You have no code execution.
Every per-item statistic is computed by reading the returned items in your own
context. A page of 250 items at ~4 KB each is ~1 MB of JSON, and summarizing a
payload that large produces unreliable arithmetic — in validation it yielded
sub-batch counts that disagreed by 3×.

So Phase B runs as **two passes with different shapes**, because the two questions
have different payload costs:

| Pass | Projection | Items | Payload | Answers |
|---|---|---|---|---|
| **1 — TTL & keys** | `#pk, #sk, #ttl` only | up to 1,000 | small — a few hundred bytes/item | TTL-03/04/05, HK-05 |
| **2 — item size** | none (full items needed) | **100–200 total** | bounded by the small `n` | IS-01/02/03/04 |

Run **pass 1 first**. It is cheap to reason over and answers the TTL questions that
most often explain the user's complaint. Run pass 2 only if item size is actually in
question, and keep `n` small enough that you can total the sizes reliably in one
pass.

If a payload still comes back too large to aggregate consistently, **do not force a
number**. Say the sample could not be summarized reliably, report only the signals
that were stable across every attempt, and offer a smaller re-run. A finding built
on arithmetic you do not trust is worse than no finding.

### Sizing the sample

**Pass 1 — TTL and key distribution** (`ProjectionExpression` on):

| Table `ItemCount` | Segments | `Limit` per page | Pages per segment | Items sampled |
|---|---|---|---|---|
| < 1,000 | 1 | 100 | ≤ 3 | ≤ 300 |
| 1,000 – 1 M | 2 | 250 | 1 | 500 |
| > 1 M, or unknown/stale | 4 | 250 | 1 | 1,000 |

**Pass 2 — item size** (no projection, full items):

| Table `ItemCount` | Segments | `Limit` per page | Items sampled |
|---|---|---|---|
| any, including unknown | 4 | **25–50** | **100–200** |

Pass 2's small `n` is deliberate and must be carried into the confidence annotation:
`n=100` on a large table is a weak sample, and the confidence-downgrade rule in
`finding-logic.md` will usually apply. That is the correct trade — a defensible
weak finding beats an indefensible strong one.

`TotalSegments` must be ≥ `Segment` count used, and every segment index in
`0..TotalSegments-1` is sampled exactly once so the sample spans the key space
rather than one region of it.

**`Limit` is not the only page bound.** A `Scan` page stops at **1 MB of scanned
data** or `Limit` items, whichever comes first. With items averaging more than ~4 KB,
the 1 MB cap binds first and a page returns fewer than `Limit` items — so the actual
sample can be well below the planned size. Report `items_sampled` as what you
actually received, never the planned figure, and recompute `pct_of_table` from it.
Do not add pages to compensate: the page cap is a cost protection, and the reduced
`n` belongs in the confidence annotation instead.

When `mean_item_size_bytes` is unknown (stale `ItemCount`/`TableSizeBytes`), you
cannot predict where the 1 MB cap lands. Quote the cost estimate as an upper bound of
**`pages × 128` RCU** — a full 1 MB page read eventually-consistently costs
1,048,576 / 8,192 = **128 RCU** — and say it is an upper bound.

Do not apply a further 0.5 factor: the 128 figure already includes the
eventually-consistent discount. (An earlier version of this file halved it and
under-predicted a measured 450 RCU as 256.)

### Estimating cost

An eventually-consistent read covers **4 KB per 0.5 RCU** — i.e. 8 KB per RCU.
`Scan` capacity is charged on the bytes of items **examined**, so:

```
estimated_RCU ≈ (items_sampled × mean_item_size_bytes) / 8192
```

using `mean_item_size_bytes` from Phase A. Round up, and floor the estimate at
`0.5 × pages` since every page consumes at least the minimum read.

State the estimate in **read units**. If the user wants a dollar figure, derive it
from the account's billing mode and current published pricing — do **not** quote a
per-unit price from memory, because it varies by region and table class and
changes over time. An order-of-magnitude statement ("well under one cent at
typical on-demand pricing") is acceptable; a fabricated precise price is not.

### Projection mode — offer the choice when data is sensitive

`ProjectionExpression` does **not** reduce `Scan` capacity consumption. Capacity is
charged on the size of items examined, not the size returned. So projecting fewer
attributes costs the same RCU; what it changes is how much customer data crosses
the wire and passes through the agent.

Projection is therefore **not** primarily a cost lever — it is a payload and exposure
lever, which is why pass 1 always uses it:

| Pass | `ProjectionExpression` | Dimensions available | Data exposure |
|---|---|---|---|
| **1 — TTL & keys** | `#pk, #sk, #ttl` only | TTL, key distribution | no non-key values ever leave DynamoDB |
| **2 — item size** | none — full items required | item size distribution, attribute names and size contribution | full items transit the agent; values discarded immediately and never recorded |

**`minimal-exposure` mode = run pass 1 only, and skip pass 2.** Offer it proactively
when the table name, attribute names, or the user's wording suggest regulated or
personal data (`pii`, `patient`, `ssn`, `payment`, `card`, `health`, `kyc`, and
similar). Say plainly what it costs analytically: no item-size or 400 KB-proximity
findings, because those require reading whole items. It does not save money — only
exposure.

Use `ExpressionAttributeNames` for the projection — TTL and key attribute names
frequently collide with DynamoDB reserved words.

### The prompt

Render this verbatim, substituting real values, and add a projection-mode line when
minimal-exposure is being offered. Then stop and wait for a reply.

> ⚠️ **Data-plane sampling for `<table>`** — this reads items from a live table.
>
> | | |
> |---|---|
> | Table size | `<TableSizeBytes>` (`<ItemCount>` items) |
> | Plan | `<S>` parallel Scan segments × `Limit <L>` = **`<N>` items max** |
> | Estimated cost | ~`<RCU>` eventually-consistent RCU (~$`<USD>`) |
> | Recorded | item **byte sizes**, attribute **names**, TTL **timestamps** |
> | Not recorded | every other attribute value — redacted before analysis |
>
> This is `<pct>`% of the table. Sampling consumes read capacity on a production
> table and can contend with live traffic.
>
> 1. **Approve sampling** (recommended — needed for item-size and TTL findings)
> 2. **Skip** — deliver control-plane findings only

Put the table above in your **message text**, where it has room to be readable. If
your runtime also takes structured choices, keep each option's label and description
**under 80 characters** — some runtimes hard-reject longer ones and you lose a turn to
a validation error.

**Do not put the table name in an option description.** It is already in the question
and in the message text, and interpolating it is what pushes these strings over the
limit in practice. Use these exact short forms:

| Label | Description |
|---|---|
| `Approve sampling` | `Bounded, redacted Scan to check TTL health and item sizes` |
| `Skip sampling` | `Control-plane and CloudWatch findings only` |

## Hard caps

| Cap | Value | Rationale |
|---|---|---|
| Items sampled, default | per the sizing table (≤ 1,000) | bounded cost |
| Items sampled, absolute ceiling | **10,000** | may be raised to here on explicit request, never beyond |
| `TotalSegments` | ≤ 4 | bounded concurrency against a live table |
| `Limit` | ≤ 250 per page | bounded page size |
| `ConsistentRead` | always `false` | strongly consistent reads cost 2× and are never needed for sampling |
| `ReturnConsumedCapacity` | `TOTAL` | required — the abort check depends on it |
| Elapsed wall time | ≤ 60 s | abort rather than run long against production |
| Cumulative consumed RCU | ≤ estimate × 1.5 | abort on overshoot |

### Never

- A full-table `Scan`, or any `Scan` without `Limit`
- `Select: "COUNT"` over an entire table (it scans everything and bills for it)
- `ConsistentRead: true`
- `FilterExpression` as a cost-control device — filters are applied *after* items
  are read and billed, so they reduce results without reducing cost. A filter that
  matches nothing still bills for the whole scan.
- Following `LastEvaluatedKey` beyond the page cap
- `Scan` or `Query` against any table the user did not name
- Any write operation, including "harmless" ones

### Abort conditions

Stop immediately, keep what was collected, and report partial results with
`sampling: aborted` and the reason:

1. Cumulative `ConsumedCapacity` exceeds the estimate × 1.5
2. Elapsed time exceeds 60 s
3. A `ProvisionedThroughputExceededException` or `ThrottlingException` is returned
   — the sample is now contending with live traffic. Do not retry, do not back off
   and continue: abort, and say that sampling was throttled.
4. `RequestLimitExceeded` or any 5xx twice in a row

A partial sample is still usable — just carry the reduced `n` into the confidence
annotation.

## Redaction — applied as each item is read

Compute, then discard. Never buffer raw items beyond what is needed for the
current page's arithmetic.

**Record only:**

| Recorded | Form |
|---|---|
| Item byte size | integer |
| Attribute names present | string set, plus per-name aggregate byte contribution |
| Attribute type per name | `S`/`N`/`B`/`BOOL`/`NULL`/`L`/`M`/`SS`/`NS`/`BS` |
| TTL attribute | numeric value and its resolved type |
| Partition key value | **hashed or truncated**, see below |

**Never record, echo, quote, log, or place in the report:** any non-key attribute
value, any full item, any "example item", or any excerpt of item content — not in
the report, not in intermediate narration shown to the user, not in an artifact.

### Partition key values

Key distribution findings need to distinguish keys, not display them. Partition key
values are customer data and are frequently identifiers (user ids, tenant ids,
account numbers).

- Group by the key value internally to count frequency.
- In the report, render each key as a stable short digest — the first 8 characters
  of a hash, or `<first 4 chars>…<last 2 chars>` — plus its share of the sample.
- Render the full key value only when the operator explicitly asks for it, and only
  for the single top key they asked about.
- Contributor Insights key values from Phase A follow the same rule.

## Computing item size

DynamoDB item size = for every attribute, the UTF-8 byte length of the **attribute
name** plus the byte length of the **value**. The attribute name counts toward the
400 KB limit — this is why wide items with long attribute names are expensive.

Approximate value sizes:

| Type | Size |
|---|---|
| `S` | UTF-8 byte length |
| `N` | ~1 byte per two significant digits, plus 1 |
| `B` | raw byte length (the un-base64'd length) |
| `BOOL`, `NULL` | 1 byte |
| `L`, `M` | sum of contained sizes + 3 bytes per element; `M` also counts each key name |
| `SS`, `NS`, `BS` | sum of member sizes |

These are approximations, but good ones: against a live 2,001-item validation table
the computed total came within **0.2 %** of the capacity-derived total, and the RCU
estimate predicted actual consumption to within **1.00×** (449.5 estimated, 450.5
consumed). Treat a large drift as a signal that something is wrong with the
computation, not as normal.

**Cross-check them:** the sum of computed item sizes for
a page should be within ~10 % of `ConsumedCapacity × 8192` for that page. If it is
not, the computation is drifting — report item sizes as
`approximate (±<observed drift>%)` and do not assert a 400 KB proximity finding on
computed size alone when the drift exceeds 20 %. Prefer the capacity-derived total
for aggregate statements and computed sizes for ranking and distribution.

Statistics to produce: `min`, `median`, `p95`, `p99`, `max`, `mean`, and a
histogram with buckets `<1 KB`, `1–4 KB`, `4–16 KB`, `16–64 KB`, `64–256 KB`,
`256–350 KB`, `>350 KB`. Also record the top 10 attribute **names** by aggregate
byte contribution — this is what makes an attribute-bloat finding actionable.

## Evaluating TTL on sampled items

Requires `ttl.attribute_name` from Phase A. For each sampled item:

| Observation | Classification |
|---|---|
| Attribute absent | `missing` — TTL will never delete this item |
| Attribute present but not type `N` | `malformed_type` — **TTL silently ignores non-Number attributes** |
| Value ≤ 0 | `malformed_value` |
| Value > 1e11 | `malformed_scale` — almost certainly milliseconds; TTL expects **seconds**, so this date is ~5,000 years out and the item will never expire |
| Value > now + 5 years | `suspicious_future` |
| Value ≤ now | `expired` — record `now − value` in days |
| Otherwise | `pending` |

Then bucket the `expired` items by how long they have been expired. DynamoDB
deletes expired items "typically within a few days", so recency matters:

| Expired for | Meaning |
|---|---|
| ≤ 2 days | normal — TTL's documented deletion window |
| 3–7 days | watch — at the edge of the documented window |
| > 7 days | **backlog** — well beyond the documented window; this is the actionable signal |

Report the `> 7 days` fraction as the TTL backlog, not the raw expired fraction.
Reporting every expired item as a defect would flag a perfectly healthy table.

## Estimating an LSI item collection (only for tables with LSIs)

The 10 GB item-collection limit applies to all items sharing a partition key across
the base table and its LSIs. `ReturnItemCollectionMetrics` is a **write** parameter,
so a read-only skill cannot obtain the exact size. Estimate it instead:

1. Take the highest-frequency partition key from the sample, or the top Contributor
   Insights key.
2. `dynamodb:Query` that single partition key with `Select: "COUNT"` and
   `ConsistentRead: false`. Scoping `Select: COUNT` to **one partition key** is
   bounded and legitimate; the banned form is `Select: COUNT` across a whole table.
3. Estimate `collection_bytes ≈ count × mean_item_size_bytes × (1 + Σ LSI projection factor)`,
   where an `ALL`-projected LSI contributes ~1.0, `INCLUDE` ~0.3, `KEYS_ONLY` ~0.05.

Label the result **estimated**, state the method, and never present it as measured.
If the estimate lands above 8 GB, say that the exact figure requires
`ReturnItemCollectionMetrics=SIZE` on a write from the application, which is
outside this skill's read-only scope.

## Sampling provenance — always reported

Whatever happened, record it for `report-format.md`:

```yaml
sampling:
  status: "completed" | "declined" | "skipped" | "aborted"
  reason: <string> | null           # required unless completed
  mode: "shape" | "minimal-exposure" | null
  items_sampled: <int>
  segments: <int>
  pages: <int>
  consumed_rcu: <float>
  estimated_rcu: <float>
  pct_of_table: <float>
  elapsed_seconds: <float>
  size_drift_pct: <float> | null    # computed vs capacity-derived
  confidence: "sampled (n=<N>, <pct>% of table)"
```

## Critical rules

- **Consent before the first read.** Every run, every table.
- **Caps are ceilings.** 10,000 items is the absolute maximum under any request.
- **Compute then discard.** Values are never recorded or shown.
- **Abort, do not retry, on throttling.** A throttled sample means the sample is
  hurting the table.
- **A sample is biased, and can miss concentration entirely.** `Scan` returns items in
  partition-layout order, not randomly. This is measured, not theoretical: on a validation
  table where **40% of items shared one partition key, a bounded 4-segment sample measured
  that key's share at 0.3%** — the pages stopped before reaching the partition holding it. So
  a low sampled share carries almost no information. Report concentration when the sample
  shows it; never report evenness because the sample failed to show it.
- **A sample is biased.** `Scan` order follows partition layout. Never claim a hot
  key from sampling — that is Contributor Insights' job. Item *count* concentration
  is not traffic concentration.
- **Absence in a sample is not absence in the table.** Always phrase negative
  results as "none in the sample of `<N>`".
