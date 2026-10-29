# Alert investigation — sessions

Load this file when investigating a session-based alert (session-error rate, user-facing failure, session-quality anomaly).

## What the alert context carries

Session alerts carry:
- `alertID`, `alertName`, `alertValue` — threshold and value
- `group`, `groupValue` — e.g. `has_errors=true`, `country=US`
- `query` — session filter
- `thresholdWindow` — hold duration
- `sessionsLink` — deep link
- `timeRange` — alert window

## Investigation shape

1. **Pull matching sessions** via `query-sessions` with the alert's query + window. Start small — 5–10 sessions sampled from the window.
2. **For each session, walk the timeline** via `query-timeline-events`. Find the last successful interaction and the first failing one. The transition is the key moment.
3. **Cross-reference errors.** If sessions have `has_errors=true`, pull the error group for each. If sessions share an error group, that's the common root.
4. **Correlate backend and frontend.** Session events often carry trace IDs — follow them to backend traces and logs for the full picture.
5. **Check for a common trigger.** Is it a specific browser? Geography? Time of day? Shared identifier attribute?

## What goes in the diagnosis

- **What triggered** — alert name, threshold, the query pattern matching the affected sessions.
- **Likely cause** — the common failure point across sessions with one quoted session ID as example. Cite specific timeline events.
- **Scope** — number of affected users, geographic or demographic clustering, time-window pattern.
- **Next steps** — concrete: "roll back the <feature> deploy", "disable flag <key>", "check for a degraded third-party script on the target page".

## Wrap session IDs

Whenever you reference session IDs in the diagnosis, wrap them in `<session-id>` tags:
```
<session-id>c6wX2TtznM6F0QByEiRBoQBFw1Bv</session-id>
```
The UI renders these as clickable links.

## Common mistakes

- Skipping the timeline walk and inferring behavior from session attributes alone.
- Paraphrasing errors instead of pulling the error group record.
- Forgetting to wrap session IDs in `<session-id>` tags. The UI can't link them otherwise.
