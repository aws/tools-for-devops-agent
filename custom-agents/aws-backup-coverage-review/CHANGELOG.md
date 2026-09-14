# Changelog

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Uses the `aws-backup-coverage-review` skill for domain knowledge, check definitions, thresholds, and report format
- Requires the `use_aws` tool for read-only resource inspection
- Output includes scope with Regions swept and not swept, a Coverage Rating, an executive summary by dimension, a coverage matrix, findings with severities taken from the check definitions, a 23-row check coverage matrix, and next steps bucketed by SLA
- Restates the report structure in the system prompt so the report artifact is produced reliably even when the account sweep is delegated to a research subagent, which may not load the skill's reference files
- Read-only by design: never applies a change, and when asked to remediate a finding it returns the exact action and resource identifiers for a human to apply rather than attempting the call
