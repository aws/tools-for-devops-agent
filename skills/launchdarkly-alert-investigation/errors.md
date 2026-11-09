# Alert investigation: errors

Load this file for an error alert: error count or rate, a new error group, crash rate.

## Before you look for a cause

- **Replay the firing** from `get-alert-firing-history`, then with `compareTo: "1w"`. An error count that was the same last week is a standing bug, not this firing's cause.
- **Name the groups.** `search-error-groups` with the alert's query, the firing window and `sort: "count"`; for new-group alerts, `sort: "first_seen"`.

## Investigation shape

1. **Read the top group** with `get-error-group` (`secureId`): stack, one occurrence, its `trace_id` and session. The originating frame is the deepest application frame, not framework code.
2. **Onset:** `search-aggregations` with `productType: "errors"`, the group's `exception.message` filter, over a window wider than the alert, `bucketCount` 24 to 48.
3. **What is over-represented:** group by `service_name`, the version key and `host.name` with `compareTo: "1d"`.
4. **What changed:** `get-changes` for the service from 1 to 2 hours before the first occurrence. A version first seen just before it is the first suspect.
5. **Scope:** `sort: "sessions"`, or `CountDistinct` of `secure_session_id` with `exact: true`.

## What goes in the diagnosis

- **What triggered:** alert, threshold, value, and the error group secure IDs behind it.
- **Likely cause:** the root frame, the trigger (version, flag, host), and one quoted error message.
- **Scope:** occurrences, users or sessions, first-seen time.
- **Next steps:** specific, such as "roll back version X" or "guard nil at handler.go:142".

## Common mistakes

- Citing a framework frame as the cause.
- Filtering on `event` instead of `exception.message`.
- Counting without a comparison window.
