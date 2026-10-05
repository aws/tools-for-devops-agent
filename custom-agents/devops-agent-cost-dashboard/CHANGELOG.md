# Changelog

## 1.0.0

- Initial version
- Uses the `devops-agent-cost-insights` skill for every calculation; the agent supplies configuration, scope, execution behaviour, and a fixed report layout
- Config table holds `ACCOUNT_ID`, `REGION`, `SPACE_NAME`, `SPACE_ID`, `ROLE_NAME`, `ROLE_ARN`, and `WINDOW_DAYS`, plus two optional credit inputs, `SUPPORT_PLAN` and `PRIOR_MONTH_SUPPORT_CHARGE`; everything else refers to them by name
- Exact-role scope: reports one configured IAM role and never discovers, infers, or adds another, including other `DevOpsAgentRole-AgentSpace-*` suffixes
- Rolling window of `WINDOW_DAYS` (default 15) recomputed on each run, treated as half-open `[START, END)`, so a scheduled run always covers the trailing period
- Credits: the credit rate is derived from `SUPPORT_PLAN` using the skill's published tier table and the monthly credit is computed as `support_charge × credit_rate`, shown as account-level reference only; at exact-role single-space scope the credit is never subtracted and `Net Direct Cost` reports `unavailable at this scope`
- CloudTrail contract: retrieve by `EventName`, filter the serialized event on the full `ROLE_ARN`, then verify `sessionIssuer.arn` on the parsed record; `events: []` is a valid no-match, `events: null` is a failure
- `GetMetricData` and X-Ray pricing defer to the skill's Step 3 for the exact quantity fields (read from the data event's `requestParameters`), avoiding duplication across the agent and skill
- Journal records read directly with the attached `get_investigation_journal_records`, `get_other_agentspace_journal_records`, and `get_tool_calls` tools, scoped to the configured window, space, and role; no subagent delegation
- Silent execution: no narration, progress, retries, tool names, raw responses, or query and execution IDs are surfaced; the run emits one final message
- Fixed output: a charted "DevOps Agent Cost Dashboard" artifact (refreshed in place, not duplicated) followed by a fixed-format text summary
- Summary sections: direct usage (space-scoped), credits (reference), downstream (exact-role), tool usage (exact-role), validation notes; space direct cost and exact-role downstream are reported separately, never as one combined total
