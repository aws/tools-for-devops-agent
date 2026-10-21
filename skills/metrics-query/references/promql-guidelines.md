# PromQL Guidelines

This MCP exposes both PromQL **instant** and **range** queries. **`query_promql_instant`** calls Coralogix **`/query`** and accepts **`query`** with optional **`time`** (RFC-3339/ISO 8601 UTC only; omit for current time). **`query_promql_range`** calls Coralogix **`/query_range`** and accepts **`query`**, **`start`**, **`end`**, **`step`**, and **`limit`**. For **`start`** and **`end`**, pass relative times (`now`, `now-1h`, `6d`), a Unix timestamp, or RFC-3339/ISO 8601 UTC.

## Core Principles

1. **Range evaluation semantics**
   - **`query_promql_instant`** evaluates the expression **once** at a single timestamp. Use this for a current snapshot, a single aggregate, or any answer that should be "as of" one moment.
   - **`query_promql_range`** evaluates the expression **repeatedly** from **`start`** to **`end`** at **`step`** intervals (Prometheus `query_range` behavior). Use this for **time series** over a period (e.g., one point per day).
   - Note: The engine evaluates at each step timestamp. Example: **`step=1d`**, **`start=now-1d`**, **`end=now`**, and expression `max_over_time(metric[1d])` → two evaluation times one day apart; each evaluation applies its own `[1d]` lookback backward from that timestamp. Misaligned **`step`** vs in-expression windows is a common source of confusion.
   - **Example**: With **`step=1d`**, the evaluation at the **second** step timestamp can look back a full day from that moment, overlapping the window used at the first step — e.g. a rolling max can span more wall-clock time than the label “one day” suggests. For “max of x between fixed calendar dates”, align **`start`**, **`end`**, **`step`**, and the PromQL window, or simplify the question to match one evaluation.
   - For a **single value “as of now”** or "as of a specific time", prefer **`query_promql_instant`**. Use **`query_promql_range`** only when you explicitly need multiple evaluation points across time.

2. **Understand PromQL value types**
   - **Instant vector** — set of series with 1 sample each at eval time
   - **Range vector** — series with many samples over a window `[t-range, t]`
   - **Scalar** — single number
   - **String** — rare
   - Functions like `*_over_time()` **require a range vector**. Aggregations like `sum/max/min/avg ... by(...)` **consume instant vectors**.
   - **Important**: When using `*_over_time()` with **`query_promql_range`**, the first evaluation occurs at **`start`**; the in-expression window is relative to each evaluation timestamp.

3. **Separation of concerns**
   - Use `*_over_time()` for **temporal reductions** across a window (e.g., `max_over_time`, `avg_over_time`, `quantile_over_time`).
   - Use `sum/max/min/avg by (...)` for **label-set aggregation** across series at the eval point.
   - Chain them as needed (temporal reduction first, then label aggregation, or vice versa).

4. **Counters vs. gauges**
   - **Counters** (monotonic, suffixed `_total`) → use `rate()`/`irate()` or `increase()` over a window.
   - **Gauges** (current value) → use `avg_over_time`, `max_over_time`, etc., or plain `avg(...)` depending on intent.

5. **Suffix conventions**
   - Canonical: `_total` (counter), `_bucket/_sum/_count` (histogram), `_sum/_count` (summary), `_created`.
   - Non-standard: `_avg`, `_mean`, etc. Prefer computing averages via PromQL unless the exporter dictates otherwise.

---

## MCP usage

### `query_promql_instant`

Call **`query_promql_instant`** with:

| Parameter | Meaning |
|-----------|--------|
| **`query`** | PromQL expression (string) |
| **`time`** | Optional RFC-3339/ISO 8601 UTC timestamp only (not `now-1h`); omit to evaluate at the current time |

Use **`query_promql_instant`** for:
- Current state questions
- One-number or one-vector answers
- Time-window functions where you want a single final answer, such as `max_over_time(metric[7d])` "as of now"

### `query_promql_range`

Call **`query_promql_range`** with:

| Parameter | Meaning |
|-----------|--------|
| **`query`** | PromQL expression (string) |
| **`start`** | Range start — `now`, relative (`now-1h`, `6d`), Unix timestamp, or RFC-3339/ISO 8601 UTC (required) |
| **`end`** | Range end — same formats as **`start`**; typically `now` (required) |
| **`step`** | Resolution (e.g. `30s`, `1h`, `1d`) — duration string (required) |
| **`limit`** | Integer **1–200** (per tool description); keeps responses bounded |

**Example: absolute max per day over the last 7 days**

- **`query`**: `max by () (max_over_time(metric[1d]))`
- **`start` / `end` / `step`**: e.g. **`start=now-7d`**, **`end=now`**, **`step=1d`** so each day gets one evaluation.

**IMPORTANT**: Align **`step`** with any window used inside `*_over_time(...)`. If using `max_over_time(metric[1d])`, prefer **`step=1d`** when you want one sample per day.

**Example: single “current” snapshot (approximate)**

- Use a **short** `[start, end]` window and a **`step`** that yields one or few evaluation points, e.g. **`start`** and **`end`** a few minutes apart with **`step`** equal to that span, depending on what the PromQL expression needs.

---

## PromQL Fundamentals

### Label Matching & Aggregation

- Matchers: `{label="v"}`, `{label!="v"}`, `{label=~"re.*"}`, `{label!~"re"}`
- Aggregate **by** labels to keep them; use **without** to drop them.

```promql
sum by (job) (rate(http_requests_total[5m]))
sum without (instance) (up)
```

### Temporal Reductions (range → instant)

```promql
max_over_time(cpu_usage[1h])
avg_over_time(node_memory_Active_bytes[30m])
quantile_over_time(0.99, queue_length[1h])
```

### Counters: Rates, Increases, Windows

Per-instance RPS:
```promql
rate(http_requests_total[5m])
```

Total RPS across fleet:
```promql
sum by () (rate(http_requests_total[5m]))
```

Events in last day (per user, then count actives):
```promql
count( sum by (user_id) (increase(api_call_count[24h])) > 0 )
```

### Histograms & Summaries

p95 from a histogram:
```promql
histogram_quantile(
  0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m]))
)
```

Average from summary parts:
```promql
sum(rate(req_duration_seconds_sum[5m]))
/
sum(rate(req_duration_seconds_count[5m]))
```

### Max over a Period

Correct — temporal reduction, then aggregation:
```promql
max by () (max_over_time(metric[4d]))
```

Per-label max:
```promql
max by (label) (max_over_time(metric[4d]))
```

Incorrect — `max()` cannot take a range vector:
```promql
max(metric[4d])   ← error
```

### Top-k / Ranking

```promql
topk(5, sum by (instance) (rate(http_requests_total[5m])))
```

---

## Common Tasks (ready to adapt)

1. **Absolute peak per instance over 7d, then pick the winner**

```promql
topk(1, max by (instance) (max_over_time(my_metric[7d])))
```

Use **`query_promql_instant`** for a single answer "as of now", or **`query_promql_range`** with **`start`/`end`** covering “now” and **`step`** chosen so you get the evaluation cadence you need when you truly want a time series.

2. **Global CPU usage % (avg across cores & hosts)**

```promql
avg by () (
  rate(process_cpu_seconds_total[5m])
) * 100
```

3. **Error rate (%) per route**

```promql
100 * sum by (route) (rate(http_requests_total{code=~"5.."}[5m]))
    / sum by (route) (rate(http_requests_total[5m]))
```

4. **Daily active users over a week (time series)**

Expression:
```promql
count(count by (user_id) (increase(api_call_count[1d]) > 0))
```

Use **`query_promql_range`** with **`step=1d`**, **`start`** / **`end`** spanning the week. (Align with how `increase` looks back from each evaluation point.)

---

## Performance & Safety Guidelines

- Prefer **short windows** for `rate()` (e.g., 1–5m) unless data is bursty or sparse.
- Avoid unbounded fan-out (e.g., joining massive label sets).
- Keep **cardinality** under control; aggregate early (`sum by (...)`) when only totals are needed.
- Use `clamp_max`/`clamp_min` to tame outliers when needed.
- For histograms, **always** aggregate buckets (`sum by (le, ...)`) before `histogram_quantile`.
- Be mindful of counter resets; `rate()`/`increase()` handle resets automatically.

---

## Frequent Gotchas (and fixes)

- **"Why am I getting many points when I want one number?"**
  Prefer **`query_promql_instant`**. **`query_promql_range`** always returns a **range** result.

- **`max(metric[...])` errors.**
  `max()` can't take a range vector. Use `max_over_time(metric[...])`, then aggregate with `max by () (...)`.

- **`_over_time(metric[...]) by (label)` errors.**
  `_over_time` aggregations cannot include a `by` clause. Use `max_over_time(metric[...])`, then `max by (label) (...)`.

- **"Avg looks wrong for counters."**
  Counters need `rate()`/`increase()`, not `avg_over_time`.

- **"p95 from a summary?"**
  Summaries expose quantiles directly via the `quantile` label. For histograms, use `histogram_quantile` on bucket rates.

- **"Results show empty label values."**
  Add `{label!=""}` to the selector to filter out empty label values. Example: `max by (deployment) (rate(cpu_usage{deployment!=""}[5m]))`.

---

## Mini Cheat-Sheet

| Goal | PromQL |
|---|---|
| Rate of a counter | `rate(x_total[5m])` |
| Increase last 24h | `increase(x_total[24h])` |
| Avg of a gauge over 1h | `avg_over_time(x[1h])` |
| Max over 4d (absolute) | `max by () (max_over_time(x[4d]))` |
| Top 5 by RPS | `topk(5, sum by (instance) (rate(x_total[5m])))` |
| p95 latency (histogram) | `histogram_quantile(0.95, sum by (le) (rate(x_bucket[5m])))` |
| Filter labels | `{env="prod", job=~"api\|web"}` |
| Drop a label in agg | `sum without (instance) (x)` |
| Time travel | `expr @ <unix_ts>` or `expr offset 1h` |
