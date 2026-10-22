---
name: cases-single-case-reference
description: Reference for investigating one specific case before taking lifecycle action.
---

# Single Case Investigation

For a detailed, evidence-based investigation of one case, load the existing [coralogix-coralogix-single-case skill](../../coralogix-single-case/SKILL.md) together with the `coralogix-alerts` skill.

Use `get_alerts_object` to retrieve the live case and its related indicators. Then use:

- `manage_cases` with `events` to inspect lifecycle changes and comments.
- `manage_cases` with `get_event` to inspect an individual event.
- `manage_cases` with `notifications` to inspect delivery outcomes.

Investigate the Alert Definition and triggering evidence before acknowledging, resolving, or closing a case. Never treat an AI summary as the sole source of truth.
