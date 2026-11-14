# Changelog

## 1.0.0

- Initial version: one Systems Manager skill with a routing table, a shared safety contract and task chapters loaded on demand.
- Automation chapters: runbook discovery (catalog of 485 AWS-owned runbooks published 2026-11-04 by symptom category and target resource type, with descriptions, required parameters and risk tiers; Region confirmation with `DescribeDocument`; fallback search of account-owned runbooks), execution (rate-controlled, alarm-protected start commands for a person to run; monitoring and diagnosis from step status; worked examples from real executions), and hardening (static review with checks backed by public Systems Manager and IAM documentation, and a hardened document).
