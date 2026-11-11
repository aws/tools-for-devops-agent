# Changelog

## [1.0.0] - 2026-11-02
### Pre-release hardening (security)
- System prompt and drift prompt now treat all tool output (IAM names, policy text, MCP results) as untrusted data and never follow instructions found in it.
### Pre-release changes
- Drift prompt handles `throttled: true` captures, reports `intervening_snapshots`, and is the only caller that passes `record_baseline: true`.
- Key-hygiene prompt names `iam:ListAccessKeys` and `iam:GetAccessKeyLastUsed`, adds a coverage line for whichever was denied, and warns that rotating a key breaks SES SMTP until new SMTP credentials are generated.
- README prerequisites name the two key-metadata actions and note that the AWS managed DevOps Agent policies do not grant them.
### Added
- Initial release of the IAM Access Navigator custom agent.
- Interactive mode: capability introduction, service-state detection, per-answer coverage line, guided tour, and delegation of IAM reasoning to the `iam-access-navigator` skill.
- Scheduled access-key hygiene sweep (rotation due, multiple active keys, never used).
- Scheduled IAM drift check backed by the `iam-drift-diff` MCP server, with an "IAM Drift Report" artifact on every run.
- Read-only by design: no tool in this agent changes IAM.
