# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-10-26

- Initial release for AWS DevOps Agent.
- Preview first (`StartLifecyclePolicyPreview` and `GetLifecyclePolicyPreview`) with a documented approval path for the agent guardrail, and a deterministic simulation fallback labelled `SIMULATED`.
- Per image verdicts `Safe`, `Expiring-Unused`, `Expiring-InUse`, `Expiring-Unknown`; repository rating `Healthy`, `Attention`, `AtRisk`, `Indeterminate`, both as ordered first match tables.
- In use cross reference on every run against `lastRecordedPullTime`, ECS running tasks, services and ACTIVE task definitions, AWS Batch job definitions, Lambda container image functions, App Runner services, EKS cluster presence, and optional CloudTrail pull events.
- 14 fixed checks, protected tag heuristic for production like tags under a catch all rule, and a protective rule suggestion handed to the operator, never applied.
- References for ECR lifecycle semantics with a worked 26 image example, API fields and error classification, and the report template. 10 evals.
