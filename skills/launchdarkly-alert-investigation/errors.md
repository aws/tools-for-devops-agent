# Alert investigation — errors

Load this file when investigating an error alert (error-rate threshold, new error group, crash rate).

## What the alert context carries

Error alerts carry:
- `alertID`, `alertName`, `alertValue` — threshold and value
- `group`, `groupValue` — e.g. `error_type=RuntimeError`, `service_name=checkout`
- `query` — error group filter
- `thresholdWindow` — condition-hold duration
- `errorsLink` — deep link
- `timeRange` — alert window

## Investigation shape

1. **Pull the matching error groups** via `query-error-groups` with the alert's query + window. Sort by frequency or first_seen depending on whether the alert is rate or newness.
2. **Read the stack trace.** Identify the originating frame in application code (not framework code). That's your starting point for the root cause.
3. **Assess scope.** Use `query-sessions` with `query="error_group_id=<id>"` to count distinct users hit. Use `query-aggregations` with `product_type="errors"` and `group_by="error_type"` for time-bucketed rate.
4. **Look for the trigger.** Recent deploy? Flag flip? Dependency upgrade? Traffic shift? New endpoint?

## What goes in the diagnosis

- **What triggered** — the alert name, threshold, the specific error group(s) involved.
- **Likely cause** — root frame in the stack trace, suspected trigger, and a quoted error message.
- **Scope** — affected user count, time-window of impact, first-seen timestamp (regression indicator).
- **Next steps** — specific: "revert commit <hash> that introduced the null check gap at handler.go:142", "add nil-guard on field Z", "disable flag <key> in <env> to mitigate until the fix lands".

## Common mistakes

- Citing the framework frame as the cause. Look for application code — deeper in the stack.
- Reporting "many errors" without quantifying. Use `query-aggregations` for a count, cite it.
- Missing the correlation with a deploy. Always check the deploy timeline within the alert's thresholdWindow.
- Confusing onset (new regression) with persistent error (ongoing bug). Different remediations.
