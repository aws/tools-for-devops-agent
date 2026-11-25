# Alert investigation: logs

Load this file for a log alert: a log count or rate threshold, an error-log spike, a message pattern.

## Before you look for a cause

- **Replay the firing** from `get-alert-firing-history`, then with `compareTo: "1w"`.
- **Group the matching logs** with `search-log-patterns` using the alert's query and the firing window. The top two or three templates usually are the alert. If one template is a known, harmless message, the alert's query needs an exclusion.

## Investigation shape

1. **Templates with counts:** `search-log-patterns`; add `patternKeys: ["service_name", "message"]` to see whether one service or all of them log it.
2. **Where:** `search-aggregations` with `productType: "logs"`, the alert's query, grouped by `host.name`, `service_name` or the version key, with `compareTo: "1d"`. A failure logged by every service on one host points at the host.
3. **Verbatim evidence:** `search-logs` for two or three examples, with `fields` to keep rows small. Follow a line's `trace_id` into `get-trace`.
4. **What changed:** `get-changes` for the service.

## What goes in the diagnosis

- **What triggered:** alert, threshold, replayed value.
- **Likely cause:** the template with its count, one verbatim line with timestamp and host, and the trigger.
- **Scope:** services, hosts and requests affected.
- **Next steps:** the fix, or an alert query change.

## Common mistakes

- Paging `search-logs` to count. Use `search-log-patterns`.
- Paraphrasing log lines. Quote them.
- Filtering on an unchecked key; a bad clause is dropped silently.
