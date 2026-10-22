---
name: coralogix-metrics-query
description: PromQL fundamentals and metric discovery/query workflow. Load when you need to explore metrics in your investigation or to answer a question about metrics. For service-level RED metrics (error rate, latency percentiles, throughput) or pod/JVM resource saturation, load the `coralogix-service-catalog` skill instead — it is a pre-aggregated path for that data; this skill is for custom, infrastructure, and hand-written PromQL work.
metadata:
  author: coralogix
  version: 1.0.0
---

# Metrics Skill - Analyzing metrics via Coralogix/PromQL

This skill describes how to discover and analyze metrics using your available tools and explains how to use PromQL for that goal.

## Core Workflow:

### 1. Initial Assessment
When a user reports a problem (e.g., "I have production issues"):
- If the problem is vague or broad, ASK 1-2 CLARIFYING QUESTIONS to get specifics
- Focus on: What exactly is failing? When did it start? What symptoms are users seeing?
- ONLY ask clarifying questions if absolutely necessary - prefer to start investigating immediately

### 2. Problem Decomposition
Once you understand the issue (e.g., "users get HTTP error unavailable for the last 30 minutes"):
- Break down the problem into SMALL, SPECIFIC questions that can each be answered with a single metric query
- Think systematically about layers: Application → Services → Infrastructure → Dependencies
- Generate questions like:
  * "Are there any K8S deployments down in the last 30 minutes?"
  * "What's the p99 latency in the ELB?"
  * "Are there any pods with high restart counts?"
  * "What RDS instances exist and are they healthy?"

### 3. Metric Discovery
- ALWAYS start by using `search_relevant_metrics` tool to find metrics related to the **subject the user is measuring** (e.g. "requests", "errors", "latency") — NOT the dimension they want to slice by (e.g. "user_email", "account_id"). If that metric doesn't carry the dimension, see "Handling a missing filter label" below — but don't go looking there unless a needed label is actually missing.
- Analyze the returned metrics and their descriptions to identify the most appropriate ones
- If no relevant metrics are found, try alternative search terms or broader keywords
- When two metric names differ only by a `_count` (or `_sum`) suffix, prefer the base metric. This follows Prometheus naming conventions: `_count` and `_sum` are the components a histogram or summary emits, where `_count` is the number of observations recorded — not the quantity being measured. Treat this as a heuristic, not a hard rule: if the user explicitly wants the number of observations, `_count` is the correct choice.
- **Match the metric to what the user is measuring, not to whichever metric happens to carry their filter label.** Identify the action or subject in the user's question (e.g. "requests served", "errors", "logins", "bytes sent") and pick the metric whose *description* reflects that outcome — even if a *different* metric is the one that exposes the label they want to slice by. Example: if the user asks "how many **requests** came from premium accounts?" and `http_requests_total` measures requests but lacks an `account_tier` label, while `sessions_total` has `account_tier` but counts sessions, still measure with `http_requests_total` and bring in the label via a join (see "Handling a missing filter label" below). Switching to `sessions_total` just because it has the label silently changes what you're counting (sessions ≠ requests). However you discover the bridge metric, the dimension filter must be applied inside a single PromQL `on()/group_left()` join — never by running separate queries and combining the numbers in prose.

### 4. Query Construction & Execution
- Based on the discovered metrics and labels, construct appropriate PromQL queries
- Use query_promql_instant for current state queries (e.g., "What is the current status?"), or single value queries (e.g., "How many users were active yesterday?")
    - **IMPORTANT**: You can use the `time` parameter to retrieve data from absolute dates.
- Use query_promql_range for queries that require comparison of different time periods (e.g., "What changed in the last hour?", "How many users were active per day in the last week?")
    - IMPORTANT: for the 'start' and 'end' parameters, use the 'now' keyword to get the current time, and use relative time like 'now-1h' to get the time 1 hour ago.
    - IMPORTANT: utilize the `step` parameter to control the resolution, when the resolution is too high, the query will return too many results, which can't be displayed or consumed.
- Start with simpler queries and build complexity as needed. If the query fails, analyze the error message, fix the query, and retry.
  You may check if an existing dashboard already tracks the same concept — reusing a known-good query is faster and keeps analysis consistent with existing monitoring:
  - `search_queries(search_type="semantic", query_text="p99 latency")` — find queries by meaning
  - `search_queries(search_type="by_field", field_path="k8s_pod_cpu_usage")` — find queries referencing a metric name

### 5. Result Validation & Retry Logic
- If a query returns no results or fails validation:
  1. Analyze what might be wrong (syntax, metric name, labels, time range)
  2. Try alternative metric names or adjust the query structure
  3. Consider broader or narrower filtering criteria
  4. Maximum 5 retry attempts with improvements each time
- If the results return with empty labels, and the question requires a specific label, try refining your query to filter out null values for the label.
    - Example: If the question is "Which deployment has the highest CPU usage?", and you used the query `max by (k8s_deployment_name) (rate(k8s_pod_cpu_usage[5m]))`, you should refine the query to `max by (k8s_deployment_name) (rate(k8s_pod_cpu_usage{k8s_deployment_name!=""}[5m]))`
- If still no results after retries, explain what was attempted and suggest alternatives

### 6. Pattern Recognition and Root Cause Analysis
- Look for correlations across different metrics
- Identify temporal patterns, like high loads on a recurring basis, or spikes in error rates, etc.
- Identify potential root causes based on the evidence
- Provide actionable next steps for resolution

## Handling a missing filter label (cross-metric joins)

This is an uncommon case — most questions are answered by a single metric, so skip this section entirely when your measurement metric already carries the labels the user wants to filter or group by. Only when a label the user wants is **not present on your measurement metric** do you need to join to a "bridge" metric that has it.

**Terminology** (the four roles in the join pattern below):
- **Measurement metric** — the metric that answers *what you're counting/measuring* (e.g. requests, tokens, sessions). It drives the value in the result.
- **Dimension** — the label the user wants to filter or group by (e.g. `plan`, `user_email`, `account_slug`) that is **missing** from the measurement metric.
- **Join key** — a label present on **both** metrics that links their series (typically `user_id`, `account_id`, `service`, `pod`, `tenant_id`).
- **Bridge metric** — a metric that carries **both** the missing dimension AND the join key; it projects the dimension onto the measurement metric.

**Flow:**

**When is `by_label` required?** `by_label` discovery (steps 1–2) is **OPTIONAL only** when a *single* metric in your earlier `search_relevant_metrics` results (whichever mode you used) already lists labels that include **both** (i) the missing dimension **and** (ii) a proper join key shared with your measurement metric. In that case the bridge is already fully confirmed — skip to step 3 and build the join. **OTHERWISE `by_label` is MANDATORY:** if no `by_description` metric exposes *both* labels (the common case — `by_description` ranks by measurement subject, so the bridge usually isn't in those results, or only shows a partial label set), you MUST resolve the bridge with `search_relevant_metrics(<dimension>, mode="by_label", join_key_label=<join_key>)` before building the join. Do **not** infer a bridge from a metric that shows only one of the two labels. Step 3 (the join itself) is never optional.

**Choosing the join key.** The join key must be a label present on **both** the measurement metric and the bridge. When several shared labels are candidates, pick the one whose **entity granularity matches the dimension** — the identifier for the *same entity* the dimension describes:
- `user_email` (a per-user attribute) → join on `user_id`, **not** `team_name`/`account_id` (coarser — over-aggregates and misattributes across users) and **not** `pod_name`/`instance` (infra, a different entity — usually won't even co-occur with the dimension).
- Match the noun: `user_*` dimensions ↔ a `user_*` key; `account_*` ↔ an `account_*` key; `route`/`http_route` ↔ an `http_*`/`route` key.
- Prefer the **most specific** (closest-granularity / highest-cardinality) shared identifier. Pass that label as `join_key_label` so the `by_label` result is restricted to metrics that carry the dimension AND that key on the same series (guaranteed bridges).

1. **Find candidate label names.** Call `search_labels(<dimension_substring>)`. This returns label names containing the substring. Use a short, distinctive substring (e.g. `email`, not the full phrase).
   - `search_labels` queries the **current, account-wide label index** (it is intentionally NOT pinned to the investigation's time window, since label names are schema, not data). It reliably surfaces high-cardinality, application-specific labels such as `user_email`, `user_id`, `route`, and `tenant_id` — trust its results.
   - **If `search_labels` returns nothing** for a dimension you're confident exists, the label is almost certainly only present on metrics that aren't currently active (the index reflects the present schema). Don't get stuck — proceed with either:
     - (a) Re-read the `search_relevant_metrics` output from step 3 — each metric entry already lists its labels. Find the metric that exposes your dimension there.
     - (b) Call `search_relevant_metrics(<canonical_label>, mode="by_label")` directly with the canonical name (e.g. `user_email`, `user_id`, `route` / `http_route`). The `by_label` mode lists the distinct metrics that carry the label (deduplicated server-side), so a real label is confirmed (a wrong guess returns no metrics) — and if the result is truncated, narrow it with the `name_filter` argument.
2. **Find candidate bridge metrics.** For each promising label name (usually 1), call `search_relevant_metrics(<dimension>, mode="by_label", join_key_label=<join_key>)`, passing the join key you chose above. With `join_key_label` set, the result is restricted to metrics whose series carry **both** the dimension and that join key — every metric returned is therefore a usable bridge (no separate `get_metric_labels` cross-check needed). A standalone metric is shown by its full name (e.g. `requests_total` or `up`). Suffix variants of one logical metric are collapsed into a **metric family** with their suffixes in parentheses, e.g. `http_request_duration (_bucket, _sum, _count)`; when the bare base metric also exists alongside its variants you'll see `base (plain, _total)` — the `plain` tag means `base` itself is directly queryable. Pick the concrete name when you build the query (`_total` + `rate()` for counters, `_bucket` for histograms).
   - **Empty result?** It means no single metric carries both the dimension and that join key on the same series. Either (a) retry with a different join-key candidate (another shared label), or (b) drop `join_key_label` to list *every* metric exposing the dimension and inspect the candidates' labels with `get_metric_labels`. If still nothing pairs the dimension with a shared key, no bridge exists (see Caveats).
   - **Omitting `join_key_label`** falls back to listing all metrics that expose the dimension. The list may then be truncated for labels carried by many metrics: only when the output ends with a truncation hint, re-call with `name_filter` set to a metric-name substring to narrow to the family you care about.
3. **Build the PromQL join.** The canonical pattern:
   ```promql
   <measurement> * on(<join_key>) group_left(<dimension>) <bridge>{<dimension>!=""}
   ```
   Then add the user's actual filter on `<dimension>` (e.g. `=~`, `!=`).
   - **Counting distinct entities (very common):** when the user asks "how many distinct X", you must collapse cardinality with an explicit `count by`. Otherwise `count(...)` will count *series* (often dozens per entity due to other labels like `account_id`, `route`, `status_code`) and inflate the answer by an order of magnitude.
     - Pattern: `count(count by (<join_key>) (<join expression> > 0))`
   - **Never stitch in prose.** Do NOT answer a cross-metric question by running one query for the dimension population and a separate query for the measurement, then combining the counts in text. The dimension filter MUST live inside one PromQL expression via `on(<join_key>) group_left(<dimension>)`. If your written answer claims "users/accounts who also had activity" but no query you ran contained `group_left`, you did not actually join — redo it as a single joined expression.
   - **Magnitude sanity check.** A distinct-entity count produced by a join is bounded by activity on the *measurement* metric and is therefore **≤** the size of the filtered *bridge* population. If your result comes out roughly equal to the whole filtered bridge population (e.g. every user who merely opened a chat, every account that merely exists), you almost certainly counted the bridge alone and skipped the join — recompute with the `on()/group_left()` expression before answering.

**Worked example** — "How many distinct users on the `premium` plan made requests over the last 7 days?"
- Subject is "made requests" → `http_requests_total` (request counter). Dimension is `plan` (filter).
- Step 3: `search_relevant_metrics("requests")` returns:
  * `http_requests_total` (labels: `user_id, route, ...`) — no `plan` ✗
  * `sessions_total` (labels: `user_id, plan, ...`) — has `plan` ✓
- **Choice**: measure with `http_requests_total`, because the user asked about requests (per-request activity), not sessions. Do NOT switch to `sessions_total` just because it has `plan`.
- The filter label `plan` is missing from the measurement metric → join (see below).
- **Join key**: `http_requests_total` exposes `user_id` and `route`. The dimension `plan` is a per-user attribute, so the matching-granularity key is `user_id` (not `route`).
- `search_labels("plan")` → `[plan, billing_plan]`. (If it returns nothing, fall back to the metric labels you already saw in step 3.)
- `search_relevant_metrics("plan", mode="by_label", join_key_label="user_id")` → `sessions_total`, …. Confirms `sessions_total` carries both `plan` and `user_id`, so it's a usable bridge.
- Build the join. Right shape for "distinct users":
  ```promql
  count(
    count by (user_id) (
      increase(http_requests_total[7d])
      * on(user_id) group_left(plan)
      max by (user_id, plan) (sessions_total{plan="premium"})
      > 0
    )
  )
  ```
  Wrong shape (counts series, not users): `count((increase(http_requests_total[7d]) > 0) and on(user_id) sessions_total{plan="premium"})` — typically gives a much larger number.

**Caveats — this approach does not always work:**
- **A bridge metric may not exist.** Not every dimension is reachable via a join — the data simply may not be there. If `search_relevant_metrics(<dimension>, mode="by_label", join_key_label=<key>)` returns nothing for every plausible join key (and a join-key-less `by_label` shows the dimension only on metrics that share no key with your measurement metric), say so and offer the closest partial answer (or a logs/spans alternative) instead of forcing a join or inventing a metric.
- **A matching label name is not proof of a correct join.** Two metrics can both have a `user_id` (or `account_id`, `service`, …) whose values come from different sources/ID spaces, so an `on(<key>)` join occasionally yields empty or misleading results even when it "type-checks". You don't need to verify every join — trust a plausible result and move on. Only when a join comes back **empty or clearly implausible** should you suspect the key isn't truly shared and reconsider the bridge/key (a quick `get_metric_label_values` on both sides confirms whether values overlap).

## Available Tools:
- **search_relevant_metrics**: Find metrics related to the user's question. Supports three modes via the `mode` arg:
    - `by_description` (default): semantic search over a natural-language description of what to measure.
    - `by_name`: wildcard metric-name pattern matching (e.g. `http_*`, `*_total`).
    - `by_label`: list which metrics expose an EXACT label name (e.g. `user_email`), to pick a bridge metric for a PromQL join (use after `search_labels`). Optional `name_filter` (a metric-name substring) narrows a truncated result; optional `join_key_label` (a second label) restricts results to metrics carrying both labels. See "Handling a missing filter label" above for the full workflow.
- **query_promql_instant**: Use this to query a metric at a specific time
- **query_promql_range**: Use this to query a metric over a time range
- **get_metric_labels**: Use this to get the labels of a metric
- **get_metric_label_values**: Use this to get the values of a specific label for a metric
- **search_labels**: Find label names matching a substring across all metrics. Cheap discovery call — use when the user mentions a dimension/filter but you don't yet know which metric carries it. Follow up with `search_relevant_metrics(<label>, mode="by_label")`.

## Key Principles:
- **Be Proactive**: Don't wait for the user to ask specific questions - drive the investigation
- **Chain Steps**: Use answers from one query to inform the next step
- **Think Holistically**: Consider all layers of the stack (app, network, compute, storage, dependencies)
- **Be Systematic**: Follow a logical troubleshooting flow from symptoms to root cause
- **Explain Your Reasoning**: Help the user understand why you're checking specific metrics

## Common Investigation Patterns:

**For HTTP Errors:**
1. Check deployment/pod status
2. Check service health and connectivity
3. Check resource utilization (CPU, memory)
4. Check dependencies (databases, external services)
5. Check network and load balancer metrics

**For Performance Issues:**
1. Check resource saturation (CPU, memory, disk, network)
2. Check application metrics (latency, throughput, errors)
3. Check scaling metrics (pod counts, autoscaling triggers)
4. Check dependency performance

**For Availability Issues:**
1. Check pod/deployment readiness and restarts
2. Check node health and capacity
3. Check service discovery and networking
4. Check infrastructure dependencies

# PromQL Guidelines

## Core Principles

1. **Pick the right API**
   - **Instant queries** evaluate an expression at a single timestamp (now, or a given `time`). Use when the user wants **one number or one vector** *as of* a moment, essentially any query that does not require results over different timeframes.
   - **Range queries** evaluate the expression **repeatedly** across `[start, end]` at a given `step`. Use for **time series** over a period (e.g., daily active users per day).
     - Important: Note that Range queries **evaluate the expression repeatedly** at all given step. i.e if you set `step=1d`, `start=now-1d`, `end=now`, and the query is `max_over_time(metric[1d])`, the query will be evaluated 1 time at `now-1d`, and 1 time at `now`, which means it will evaluate 2 days of data.
   - Prioritize Instant Queries over Range Queries for most questions, except for questions that require comparing different time frames.

2. **Understand PromQL value types**
   - **Instant vector** (set of series with 1 sample each at eval time)
   - **Range vector** (series with many samples over a window `[t-range, t]`)
   - **Scalar** (single number)
   - **String** (rare)
   - Functions like `*_over_time()` **require a range vector**. Aggregations like `sum/max/min/avg ... by(...)` **consume instant vectors**.
    - **Important**: When using `*_over_time()` functions with Range Queries you must be aware that the query will also be evaluated at the `start` time, and include the window specified in the `*_over_time()` function.
    - **Example**: If you use `max_over_time(metric[1d])` with `start=now-1d`, `end=now`, `step=1d`, the query will be evaluated at `now-1d` and `now`, and the result will be the max of the metric over the window `[now-2d, now]`. This is a very common mistake, you must avoid! If a user asks "What is the max of x between 2025-01-01 and 2025-01-07?" and you use `max_over_time(x[7d])` with `start=2025-01-01`, `end=2025-01-07`, `step=1d`, the query will be evaluated at `2025-01-01` and `2025-01-07` - which is wrong! You must use Instant Query to avoid this mistake.

3. **Separation of concerns**
   - Use `*_over_time()` for **temporal reductions** across a window (e.g., `max_over_time`, `avg_over_time`, `quantile_over_time`).
   - Use `sum/max/min/avg by (...)` for **label-set aggregation** across series at the eval point.
   - Chain them as needed (temporal reduction first, then label aggregation, or vice versa).

4. **Counters vs. gauges**
   - **Counters** (monotonic, suffixed `_total`) → use `rate()`/`irate()` or `increase()` over a window.
   - **Gauges** (current value) → use `avg_over_time`, `max_over_time`, etc., or plain `avg(...)` depending on intent.

5. **Suffix conventions**
   - Canonical: `_total` (counter), `_bucket/_sum/_count` (histogram), `_sum/_count` (summary), `_created`.
   - Non-standard: `_avg`, `_mean`, etc. Prefer computing averages via PromQL unless exporter dictates otherwise.

---

## PromQL Tool Usage

### Instant Query

**Example: absolute max over last 24h (single result)**

```promql
max by () (max_over_time(http_requests_in_flight[24h]))
```

### Range Query

**Example: Absolute max per day over the last 7 days**

```promql
max by () (max_over_time(metric[1d]))
```
Set `start=now-7d`, `end=now`, `step=1d`.

**IMPORTANT**: When using `range` queries, you must align the `step` parameter, with any range parameters you use in temporal reduction functions. i.e if you use `max_over_time(metric[1d])`, you must set `step=1d`.


## PromQL Fundamentals (with examples)

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

- Per-instance RPS:

```promql
rate(http_requests_total[5m])
```

- Total RPS across fleet:

```promql
sum by () (rate(http_requests_total[5m]))
```

- Events in last day (per user, then count actives):

```promql
count( sum by (user_id) (increase(api_call_count[24h])) > 0 )
```

### Histograms & Summaries

- p95 from a histogram:

```promql
histogram_quantile(
  0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m]))
)
```

- Average from summary parts:

```promql
sum(rate(req_duration_seconds_sum[5m]))
/
sum(rate(req_duration_seconds_count[5m]))
```

### Max over a Period

- **Correct:**

```promql
max_over_time(metric[4d])
```

- **Aggregate across series (absolute max):**

```promql
max by () (max_over_time(metric[4d]))
```

- **Aggregate across series (absolute max) per label:**

```promql
max by (label) (max_over_time(metric[4d]))
```

- **Incorrect:** `max(metric[4d])` (aggregation cannot take a range vector)

### Top-k / Ranking

```promql
topk(5, sum by (instance) (rate(http_requests_total[5m]))
```

---

## Common Tasks (ready to adapt)

1. **Absolute peak per instance over 7d, then pick the winner**

```promql
topk(1, max by (instance) (max_over_time(my_metric[7d])))
```

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

- Expression:

```promql
count(count by (user_id) (increase(api_call_count[1d]) > 0))
```

- Use `query_promql_range` with `step=1d`, `start=now-6d`, `end=now`. (Note we start from 6 days ago, because the increase function takes the earlier day into account)

---

## Performance & Safety Guidelines

- Prefer **short windows** for `rate()` (e.g., 1-5m) unless data is bursty or sparse.
- Avoid unbounded fan-out (e.g., joining massive label sets).
- Keep **cardinality** under control; aggregate early (`sum by (...)`) when you only need totals.
- Use `clamp_max`/`clamp_min` to tame outliers when needed.
- For histograms, **always** aggregate buckets (`sum by (le, ...)`) before `histogram_quantile`.
- Be mindful of counter resets; `rate()`/`increase()` handle resets automatically.

---

## Frequent Gotchas (and fixes)

- **“Why am I getting steps when I only want one number?”**
  You're using `query_promql_range`. Use `query_promql_instant` instead.

- **“`max(metric[...])` errors.”**
  `max()` can't take a range vector. Use `max_over_time(metric[...])`, then aggregate with `max by () (...)` if needed.

- **“`_over_time(metric[...]) by (label)` errors.”**
  `_over_time` aggregations cannot include a `by` label clause. Use `max_over_time(metric[...])`, then aggregate with `max by () (...)`.

- **“Avg looks wrong for counters.”**
  Counters need `rate()`/`increase()`, not `avg_over_time`.

- **“p95 from summary?”**
  Summaries expose quantiles directly via the `quantile` label. For histograms, use `histogram_quantile` on bucket rates.

---

## Mini Cheat-Sheet

- **Rate of a counter:** `rate(x_total[5m])`
- **Increase last 24h:** `increase(x_total[24h])`
- **Avg of a gauge over 1h:** `avg_over_time(x[1h])`
- **Max over 4d (absolute):** `max by () (max_over_time(x[4d]))`
- **Top 5 by RPS:** `topk(5, sum by (instance) (rate(x_total[5m])))`
- **p95 latency (histogram):** `histogram_quantile(0.95, sum by (le) (rate(x_bucket[5m])))`
- **Filter labels:** `{env="prod", job=~"api|web"}`
- **Drop a label in agg:** `sum without (instance) (x)`
- **Time travel:** `expr @ <unix_ts>` or `expr offset 1h`

## Related Skills

- If the question is about a specific service/pod/entity's RED metrics, health, or resource
  saturation (CPU/memory/OOMKilled, JVM heap/GC), load the `coralogix-service-catalog` skill first — it's a
  curated, pre-aggregated path for that data rather than hand-writing PromQL. Fall back to this
  skill for ad-hoc metrics beyond the fixed Service Catalog columns.

## MCP tools

### `query_promql_instant`

- **`query`**: PromQL expression
- **`time`** (optional): RFC-3339/ISO 8601 UTC only; omit for current time. Relative strings like `now-1h` are **not** accepted.

### `query_promql_range`

- **`query`**: PromQL expression
- **`start`** / **`end`**: `now`, relative (`now-1h`, `now-6d`), Unix timestamp, or RFC-3339/ISO 8601 UTC
- **`step`**: resolution (e.g. `30s`, `1h`, `1d`)
- **`limit`**: max samples per series (1–200)

### `get_datetime`

Returns the current UTC time as ISO 8601. Use for an explicit **`time`** on instant queries; for range queries you can pass `now` / `now-1h` directly to **`start`** / **`end`**.

### `search_relevant_metrics`

- **`query`**: search term, interpreted per **`mode`** (description text, name pattern, or EXACT label name)
- **`mode`**: `by_description` (default) / `by_name` / `by_label`
- **`top_k`**: max results, **`by_description`** only (1–100, default 5)
- **`name_filter`** (optional, **`by_label`** only): metric-name substring to narrow a truncated result
- **`join_key_label`** (optional, **`by_label`** only): EXACT second label (the shared join key); returns only metrics carrying BOTH `query` and this label on the same series (guaranteed bridges)

### `search_labels`

- **`substring`**: case-insensitive substring matched against label names across all metrics; exact match returned first. Returns one label name per line (with a truncation hint when more match).
