---
name: coralogix-cases
description: Triage and manage Coralogix Cases. Load when a user wants to inspect a case, update it, add a comment, assign or acknowledge it, resolve or close it, change its priority, inspect its events, or inspect notification deliveries.
metadata:
  author: coralogix
  version: 1.0.0
---

# Cases Management

A Case groups related alert events into one investigation unit with a status, priority, category, and assignee. Use `manage_cases` to inspect a case and drive its lifecycle: `ACTIVE → ACKNOWLEDGED → RESOLVED → CLOSED`.

## Tool actions

| Action | Required inputs | Purpose |
| --- | --- | --- |
| `events` | `case_ids` | Inspect the first case's timeline. |
| `get_event` | `event_id` | Inspect one event in detail. |
| `notifications` | `case_ids` | Inspect delivery records for one or more cases. |
| `update` | `case_ids`, `title` and/or `resolution_reason` | Update mutable fields on the first case. |
| `comment` | `case_ids`, `text` | Add an investigation note to the first case timeline. |
| `assign` / `unassign` | `case_ids`, `user_id` for assign | Set or remove the first case assignee. `user_id` must be a Coralogix user ID. |
| `acknowledge` / `unacknowledge` | `case_ids` | Claim work on the first case or return it to active. |
| `set_priority` / `clear_priority` | `case_ids`, `priority` for set | Override priority with `P1`–`P5` or restore the computed priority. |
| `resolve` | `case_ids`, `reason` | Resolve the first case with a meaningful reason. Irreversible. |
| `close` | `case_ids` | Close the first case. Terminal. |

`case_ids` is always a list. Lifecycle actions and `events` use only its first entry; `notifications` uses every entry.

## Lifecycle

```text
PENDING_ACTIVATION → ACTIVE ↔ ACKNOWLEDGED
                         ↘       ↙
                           RESOLVED → CLOSED
ACTIVE ───────────────────────────→ CLOSED
```

- `unacknowledge` is the only reverse transition: `ACKNOWLEDGED → ACTIVE`.
- `RESOLVED` cannot be reopened; it can only be closed.
- `CLOSED` is terminal.
- Priorities run from `P1` (highest) to `P5`. An override is distinct from the system-calculated priority.

## Triage workflow

1. Inspect the live case with `get_alerts_object`; use its UUID or readable ID such as `CASE-123`.
2. Inspect the timeline with `manage_cases(action="events")` and notification delivery outcomes with `manage_cases(action="notifications")`.
3. Investigate the underlying Alert Definition and triggering telemetry before changing lifecycle state. Load the `coralogix-alerts` and `coralogix-single-case` skills.
4. Assign and acknowledge only after the user confirms ownership.
5. Record findings, links, root cause, and mitigation in a `comment`.
6. Resolve only with a meaningful `reason`; if impact differs from the calculated priority, set or clear an override while the case remains open.
7. Re-fetch the case after a mutation when confirmation of current state is required.

## Safety rules

- Never infer acknowledgement, resolution, or closure from an investigation result; obtain explicit user confirmation.
- `resolve` is irreversible and `close` is terminal. Prefer leaving an uncertain case acknowledged.
- Add a comment before resolving or closing when the case lacks investigation or remediation context.
- Do not fabricate case IDs or Coralogix user IDs.

## Examples

```json
{"action":"comment","case_ids":["CASE-123"],"text":"Mitigation deployed; monitoring recovery."}
```

```json
{"action":"set_priority","case_ids":["CASE-123"],"priority":"P1"}
```

```json
{"action":"notifications","case_ids":["CASE-123","CASE-456"]}
```

## References

- [Single-case investigation](references/single-case.md)
- [Case analytics](references/case-analytics.md)
