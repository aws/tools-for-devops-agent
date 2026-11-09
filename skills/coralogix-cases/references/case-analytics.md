---
name: cases-analytics-reference
description: Reference for fleet-level case analysis and discovery.
---

# Case Analytics

For counts, trends, distributions, listings, MTTR, MTTA, or other fleet-level case questions, load the existing [coralogix-coralogix-case-analytics skill](../../coralogix-case-analytics/SKILL.md) and the `coralogix-dataprime` skill.

Use the `system/labs.cases.state_updates` dataset with an explicit time range. Deduplicate by `caseId` before answering questions about cases rather than raw state-change events.

Use `manage_cases` only after analytics identifies a specific case and the user asks to inspect or mutate that individual case.
