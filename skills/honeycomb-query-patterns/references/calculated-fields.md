# Calculated Fields Reference

Calculated fields (also called derived columns) are per-event expressions evaluated
at query time. They let you transform, classify, and combine existing fields without
re-instrumenting your code.

## Scope Types

| Scope | Where it lives | Use when |
|-------|----------------|----------|
| **Query-scoped** | Single query session, not saved | One-off analysis, exploring |
| **Dataset-level** | Saved to one dataset | Field is meaningful only for that service |
| **Environment-level** | Saved across all datasets | Field is meaningful everywhere (e.g., `error_pct`) |

**Start query-scoped.** Only save a calculated field if you'll reuse it across multiple
queries or share it with your team. Saved fields clutter schema for everyone.

## Syntax

```
$column_name               # column reference
$"column with spaces"      # quoted column name (spaces or starts with number)
"string literal"           # interpreted string (supports \n, \" escapes)
`raw string`               # raw string (good for regex and file paths — no escaping)
```

**Primitives**: integers, floats, `true`/`false`, `null`

## Operator Quick Reference

### Conditional

| Operator | Usage | Notes |
|----------|-------|-------|
| `IF` | `IF(cond, val [, cond2, val2]...[, default])` | Multi-condition form is a case statement. Default is `null` if omitted. |
| `SWITCH` | `SWITCH(expr, case1, val1 [, case2, val2]...[, default])` | More efficient than `IF` when testing the same expression for exact equality. |
| `COALESCE` | `COALESCE(arg1, arg2, ...)` | First non-empty value. Good for merging field naming variants. |

**Use `SWITCH` over repeated `IF(EQUALS(...))` chains** — same expression, multiple
exact matches:

```ruby
# Bad: IF with repeated EQUALS on the same field
IF(EQUALS($region, "us-east-1"), "US East",
   EQUALS($region, "eu-west-1"), "EU West",
   "Other")

# Good: SWITCH — same logic, more efficient
SWITCH($region,
  "us-east-1", "US East",
  "eu-west-1", "EU West",
  "Other")
```

### Comparison

| Operator | Usage |
|----------|-------|
| `LT` / `LTE` / `GT` / `GTE` | Numeric or lexicographic comparison. Returns false if types don't match. |
| `EQUALS` | Strict equality. `200` (int) ≠ `"200"` (string) — type mismatch silently returns false. |
| `IN` | `IN($field, "a", "b", "c")` — compact OR equality check. |
| `EXISTS` | `EXISTS($field)` — true if field has a value. |

**Watch for type mismatches with `EQUALS`**: if your field stores HTTP status codes as
strings but you compare against integer `200`, it will silently return false on every
event. Use `find_columns` to check the field type first.

### Math

| Operator | Usage | Notes |
|----------|-------|-------|
| `SUM` | `SUM(arg1, arg2, ...)` | Sum of multiple fields on one event (not an aggregation across events) |
| `SUB` | `SUB(a, b)` | `a - b` |
| `MUL` | `MUL(a, b, ...)` | Product |
| `DIV` | `DIV(a, b)` | `a / b`. Division by zero → null. |
| `MOD` | `MOD(a, b)` | Remainder |
| `MIN` / `MAX` | `MIN(a, b, ...)` | Smallest/largest of arguments on same event |
| `LOG10` | `LOG10($field)` | Base-10 log. Useful for compressing wide-range numeric fields. |
| `BUCKET` | `BUCKET($field, size, [min, [max]])` | Bin a continuous field into categorical buckets. |

### String

| Operator | Usage | Notes |
|----------|-------|-------|
| `CONTAINS` | `CONTAINS($field, "substr")` | Substring check. Prefer over `REG_MATCH` when a simple substring match suffices. |
| `STARTS_WITH` | `STARTS_WITH($field, "prefix")` | Prefix check. More precise than `CONTAINS` for path routing. |
| `CONCAT` | `CONCAT(arg1, arg2, ...)` | Joins values into a string. Non-strings are coerced. |
| `TO_LOWER` | `TO_LOWER($field)` | Normalize case before comparison. |
| `LENGTH` | `LENGTH($field, "bytes"\|"chars")` | String length. |
| `REG_MATCH` | `REG_MATCH($field, \`regex\`)` | Boolean regex test. Use raw strings (backticks) for patterns with `\`. |
| `REG_VALUE` | `REG_VALUE($field, \`regex\`)` | Extract first submatch. |
| `REG_COUNT` | `REG_COUNT($field, \`regex\`)` | Count non-overlapping matches. |

**Always use backticks for regex patterns**: `` `Chrome/[\d.]+` `` avoids backslash
escaping issues. Double-quoted regex strings require double-escaping (`\\d`).

### Boolean

`NOT(arg)`, `AND(arg1, arg2, ...)`, `OR(arg1, arg2, ...)`

### Cast

`INT($field)`, `FLOAT($field)`, `BOOL($field)`, `STRING($field)`

### Time

| Function | Usage | Notes |
|----------|-------|-------|
| `UNIX_TIMESTAMP($field)` | RFC3339 string → epoch float | For computing durations from start/end timestamps |
| `EVENT_TIMESTAMP()` | Current event's timestamp | No arguments |
| `INGEST_TIMESTAMP()` | When Honeycomb received the event | Useful for debugging send latency |
| `FORMAT_TIME(format, ts)` | Epoch → formatted string | **Expensive — avoid in high-volume queries** |

## Good Patterns

### Error rate percentage
```ruby
# Saved as `error_pct` — use AVG(error_pct) to get percentage
MUL(IF($error, 1, 0), 100)
```

### Latency bucketing
```ruby
# Group requests into coarse latency tiers
IF(LT($duration_ms, 100), "fast",
   LT($duration_ms, 500), "ok",
   LT($duration_ms, 2000), "slow",
   "very_slow")
```

### Route classification (correct: STARTS_WITH, not EQUALS)
```ruby
IF(STARTS_WITH($http.route, "/admin"), "admin",
   STARTS_WITH($http.route, "/api/v2"), "api_v2",
   STARTS_WITH($http.route, "/api"), "api_v1",
   "other")
```

### Extract from structured field (k8s pod → deployment name)
```ruby
REG_VALUE($k8s.pod.name, `(.*)-[^-]+-[^-]+$`)
```

### Cross-field timing (compute duration from two timestamps)
```ruby
MUL(SUB(UNIX_TIMESTAMP($end_time), UNIX_TIMESTAMP($start_time)), 1000)
# Result: duration in ms
```

### Merge field naming variants across datasets
```ruby
COALESCE($service.name, $service_name, $serviceName, "unknown")
```

## Anti-Patterns

### ❌ Presentational (alias-only) calculated fields

```ruby
# Bad: wraps $http.response.status_code with no transformation
$http.response.status_code
```

A calculated field that does nothing but rename a field adds no analytical value,
clutters your schema with an extra name to remember, and creates ambiguity ("which
`status` is this?"). Use it if the field genuinely needs transformation; otherwise,
just reference the original field directly.

**Instead, compute something useful:**
```ruby
# Good: classifies status codes into actionable categories
IF(GTE($http.response.status_code, 500), "5xx",
   GTE($http.response.status_code, 400), "4xx",
   "ok")
```

### ❌ Regex on large or complex string fields

Running `REG_MATCH`, `REG_VALUE`, or `REG_COUNT` on long string fields (stack traces,
full SQL queries, JSON blobs, raw log lines) applies the regex across every matching
event and can substantially slow your query.

**Common traps:**
- `$exception.stacktrace` — may be 50+ lines of text per event
- `$db.statement` — full SQL with inline values
- `$http.request.body` / `$http.response.body` — arbitrary payloads
- `$log.message` — free-form log text

**Instead, check whether a more targeted field already exists:**
- `exception.type` or `exception.class` — OTel semantic convention for exception class
- `exception.message` — the exception message without the trace
- `db.operation` — OTel SQL operation name
- `http.route` — parsed route without query params

**If you must regex a large field**, add a `CONTAINS` or `STARTS_WITH` guard to limit
how many events reach the regex engine:

```ruby
# Bad: applies regex to every event with a stacktrace
REG_VALUE($exception.stacktrace, `^([A-Za-z][A-Za-z0-9_.$]*)`)

# Better: guard with CONTAINS first (cheaper substring check)
IF(
  CONTAINS($exception.stacktrace, "Exception"),
  REG_VALUE($exception.stacktrace, `^([A-Za-z][A-Za-z0-9_.$]*)`),
  IF(EXISTS($exception.type), $exception.type, "unknown")
)

# Best: check if exception.type exists before touching stacktrace at all
COALESCE($exception.type, REG_VALUE($exception.stacktrace, `^([A-Za-z][A-Za-z0-9_.$]*)`), "unknown")
```

### ❌ `FORMAT_TIME` in high-volume queries

`FORMAT_TIME` is explicitly documented as more expensive than other calculated field
functions and can slow queries, especially with complex format strings. Reserve it
for low-frequency queries (debugging, one-off analysis) or narrow time windows.

### ❌ Saving a calculated field you'll only use once

Query-scoped calculated fields (available without saving) are the right choice for
exploratory work. Saved dataset- or environment-level fields add to the schema that
every team member sees. Only save when the field is genuinely reusable.

### ❌ String comparison type mismatches

`EQUALS($http.status_code, 200)` silently returns false if `http.status_code` is
stored as a string. Use `find_columns` to check the column type before writing
comparisons. When in doubt, `EQUALS(STRING($field), "200")` normalizes to string,
or `EQUALS(INT($field), 200)` normalizes to integer.
