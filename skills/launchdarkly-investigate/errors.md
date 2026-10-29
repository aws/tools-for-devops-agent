# Investigating with error groups

Load this file when the investigation concerns error groups, exception patterns, or crash analysis.

## When to reach for error groups

- The user reports a crash, exception, or regression
- You need to understand scope of impact (users affected, frequency, timeline)
- You're hunting for a recent regression and need to find the first-seen timestamp
- You have an error group ID and want to pull its stack trace and associated sessions

Error groups collapse many individual errors into a single entity by stack-trace similarity. That's your unit of investigation.

## Tool guidance (`query-error-groups`)

The `query-error-groups` tool returns error groups with frequency, stack traces, and attributes.

- `start_date` is required; ISO format.
- `end_date` defaults to now.
- `query` filters by attributes — e.g. `error_type='RuntimeError' AND environment=production`.
- `count` defaults to 10, max 50.
- `page` for pagination.

**Important query note.** Do NOT use the `event` attribute — it's not valid. Use `exception.message` to filter on error message content:
```
query="exception.message=\"Cannot use 'in' operator*\" and service_name=gonfalon-web"
```

## Typical patterns

1. **New error detection** — compare two time windows via `query-aggregations` with `product_type="errors"` and `group_by="error_type"`; investigate error types with higher counts in the recent window.
2. **Regression hunt** — query error groups in the last N hours, note `first_seen` timestamps, cross-reference with deploy/flag-flip timeline.
3. **Blast-radius estimate** — for a specific error group, count distinct session IDs via `query-sessions` with `query="error_group_id=<id>"`.
4. **Stack-trace analysis** — read the trace as a narrative. The originating frame is the lowest-level application code frame (not framework code).

## Interpreting results

- **Scope first, cause second.** One user hitting a RuntimeError in a rare code path is different from a regression affecting 30% of traffic.
- **Look for a change that correlates with onset** — a deploy, a flag flip, a dependency upgrade, a traffic spike, a time-of-day pattern.
- **Cite the error group ID, affected count, and first-seen timestamp** in your summary.
- **If the stack points into a third-party dependency**, say so — the fix may not be in our code.

## Common mistakes

- Using `event` in the query. Use `exception.message`.
- Reporting "many errors" without specifying which error group or how many. Always quantify.
- Ignoring the distinction between error onset (new regression) and persistent errors (ongoing bug). They call for different remediation.
