# Investigating with error groups

Load this file when the investigation concerns exceptions, crashes, stack traces, or a new error.

## When to reach for error groups

- The user reports a crash, an exception or a regression
- You need an error's first-seen time, frequency, stack, or affected users
- You have an error group ID and want its occurrences, traces and sessions

An error group collapses many occurrences by stack similarity. A group can still hold unrelated messages, so read its occurrences before concluding.

## Find groups (`search-error-groups`)

- `startDate` is required. Only `OPEN` groups are returned unless `state` says otherwise (`ANY` for every state).
- Filter on `exception.message`, `exception.type`, `service_name` and `environment`. Do not filter on `event`: it matches only the group's original title.
  ```
  query: exception.message="Cannot use 'in' operator*" AND service_name=gonfalon-web
  ```
- `sort`: `spike` for groups growing fastest (count in the window divided by the count in the previous window of the same length; `in_window` adds `baseline_count`, `spike_ratio` and `new_in_window`, and the response gives `spike_baseline_window`), `count` for the biggest in the window, `first_seen` for new groups, `sessions` for user impact (backend-only groups have no sessions and are left out).
- Each group's `in_window` block counts only the matching occurrences in your window.

## Read one group (`get-error-group`)

- `secureId` from `search-error-groups`. It returns the state, the stack and one occurrence (the latest, or the latest in `startDate`..`endDate` that matches `query`) with its `trace_id` and session.
- `include: ["distribution", "trend"]` adds context over `startDate`..`endDate` (default the last 7 days, echoed as `context_window`): `distribution` gives the top values of browser, os_name, environment, service_name and service_version with count and percent, so "92 % on version X" or "only Safari" shows up in one call; `trend` gives occurrence counts in up to 60 buckets with the `peak` bucket; the first non-zero bucket is the group's onset in that window. Not with `occurrences`.
- Frames carry `in_app`, `link` (to the source on GitHub when connected) and `source_map_error`; `top_frame` adds `code_before` and `code_after`.
- Step through occurrences with `next_id` and `previous_id`, or set `occurrences` (with `startDate`) to list them: each row has timestamp, service, version and session.
- Pivot: `_pivots` holds ready `get-trace` and `search-logs` (`trace_id=<id>`, ±1 h) arguments for the occurrence; pass them as they are. Without `_pivots`, build them from the occurrence's `trace_id`.
- `search-logs` rows at error level and above carry `error_group_secure_id` and `error_object_id` when the log matches an error object, which links a log line straight to its group.

## Typical patterns

1. **New regression:** `search-error-groups` with `sort: "spike"` (or `"first_seen"`) over the onset window, then `get-changes` for the service: did a version appear just before the first occurrence?
2. **What is over-represented:** `get-error-group` `include: ["distribution"]` for one group, or `search-aggregations` with `productType: "errors"`, grouped by `service_name`, the version key or `host.name`, with `compareTo: "1d"`. For a flag, filter `feature_flag.key=<flag>` and group by `feature_flag.result.value`.
3. **Blast radius:** `sort: "sessions"`, or `search-aggregations` `CountDistinct` of `secure_session_id` for the group's filter with `exact: true`.
4. **Stack analysis:** the originating frame is the deepest frame in application code, not framework code. If it is in a third-party dependency, say so.

## Interpreting results

- **Scope first, cause second.** One user in a rare path is different from 30 % of traffic.
- **Onset vs standing.** Compare the group's count with `compareTo`; a group that was just as busy last week is not this incident's cause.
- **Cite** the error group secure ID, the occurrence count, first-seen time, and one trace ID.

## Common mistakes

- Filtering on `event`. Use `exception.message`.
- Reporting "many errors" without a number and a comparison window.
- Treating backend errors that are only logged (not recorded as error groups or error spans) as absent. Check error logs too.
