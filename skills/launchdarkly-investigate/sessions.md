# Investigating with sessions

Load this file when the investigation concerns user journeys, frontend behavior, or session replays.

## When to reach for sessions

- The user reports a frontend bug — "checkout broken", "infinite spinner", "empty state"
- You need to reconstruct what a user saw and did
- You have a session ID and want to pull events, logs, and errors within that session
- You're correlating frontend events with backend traces using a shared user identifier or timestamp

## Tool guidance (`query-sessions`)

The `query-sessions` tool returns sessions with user details and core attributes.

- `start_date` is required.
- `query` filters by attributes — e.g. `identifier='user@example.com' AND has_errors=true`.
- `count` defaults to 10, max 50.
- `sort_field` — `created_at`, `length`. Defaults to `created_at`.
- `sort_desc` — Boolean. Defaults to `true`.

**Fetching a specific session by secure_id.** Use a wide time window (you often don't know when the session happened):
```
{"start_date": "2026-01-01T00:00:00Z", "query": "secure_id=LWK4jxZch4GMmVYJ0rW3R6CNymSy", "count": 1}
```

**Relating events within a session.** Session filters like `visited-url=*/a* visited-url=*/b*` only check that both matched, in any order. To ask about order, absence, or which events happened together, wrap each event in `span(...)` or `log(...)` and join the blocks with `THEN`, `AND`, or `OR`, for example `span(view_name="/pricing") THEN span(view_name="/checkout")`. Load `relationship-search.md` for the full syntax.

**Session IDs in output.** When you reference sessions in your response, wrap session IDs in `<session-id>` tags so the UI can turn them into links:
```
<session-id>c6wX2TtznM6F0QByEiRBoQBFw1Bv</session-id>
```

## Supporting tools

- **`query-timeline-events`** — pull the event timeline from a session (navigations, clicks, errors, network). Use this to find the exact moment a user hit a problem.
- **`query-logs`** — pass `secure_session_id=<id>` in the query to get logs scoped to the session. `start_date` = session `created_at`, `end_date` = `created_at + 3 hours`.

## Typical patterns

1. **Bug reproduction** — start with the symptom ("infinite spinner on checkout"), find sessions that hit the target URL via `query="visited-url=*/checkout*"` (or narrow to the failing sequence with `query="span(view_name=\"/checkout\") THEN span(has_errors=true)"`), use `query-timeline-events` to walk chronologically and find the last successful action vs. the first failing one.
2. **User-specific investigation** — `query="identifier=<email>"` or by user ID. Pull recent sessions, look for errors or abnormal patterns.
3. **Correlated backend errors** — sessions with `has_errors=true` connect to error groups via the trace_id attribute in session events. Cross-reference.

## Interpreting results

- **Walk chronologically.** The transition from the last successful action to the first failing one is where the interesting detail sits.
- **Cite exact timestamps.** "Around 2:00 into the replay" is less useful than an absolute time.
- **If the session is truncated or missing segments**, say so explicitly.
- **Pull errors as a separate query** rather than paraphrasing from the session payload — the error group record has the stack trace.

## Common mistakes

- Telling the user that sessions search can't check event order or absence. Use relationship search (`relationship-search.md`).
- Putting session keys (`visited-url`, `clickTextContent`, `event`) inside `span(...)`. They parse but match nothing there; use the span keys in `relationship-search.md`.
- Forgetting to wrap session IDs in `<session-id>` tags. The UI can't link them otherwise.
- Filtering by user identifier without a time window. Returns all sessions ever — expensive and noisy.
- Using `query-timeline-events` for overview when you only need a high-level triage read, or skipping it when you actually need chronological detail. Match the tool to the depth you need.
