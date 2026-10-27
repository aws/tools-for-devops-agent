# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-10-26

- Initial release for AWS DevOps Agent.
- Preview first (`StartLifecyclePolicyPreview` and `GetLifecyclePolicyPreview`) with a documented approval path for the agent guardrail, and a deterministic simulation fallback labelled `SIMULATED`.
- Per image verdicts `Safe`, `Expiring-Unused`, `Expiring-InUse`, `Expiring-Unknown`; repository rating `Healthy`, `Attention`, `AtRisk`, `Indeterminate`, both as ordered first match tables.
- In use cross reference on every run against `lastRecordedPullTime`, ECS running tasks, services and ACTIVE task definitions, AWS Batch job definitions, Lambda container image functions, App Runner services, EKS cluster presence, and optional CloudTrail pull events.
- 14 fixed checks, protected tag heuristic for production like tags under a catch all rule, and a protective rule suggestion handed to the operator, never applied.
- References for ECR lifecycle semantics with a worked 26 image example, API fields and error classification, and the report template. 10 evals.

### Changed (2026-10-27, after live test round 1, still 1.0.0)

- In use evidence is now ranked: (a) `lastRecordedPullTime`, (b) a consumer reference in ECS, Batch, Lambda or App Runner, (c) CloudTrail pull events. Only tier (c) is filtered.
- Push correlation rule for CloudTrail: `BatchGetImage`, `GetDownloadUrlForLayer`, `PutImage`, `InitiateLayerUpload`, `CompleteLayerUpload` or `BatchCheckLayerAvailability` events within 60 seconds of `imagePushedAt`, or from the pushing principal, are part of the push and never count as a consumer pull. In the live test every expiring image carried such an event 1 to 2 seconds after push and was wrongly rated `Expiring-InUse` (11 of 11 false positives).
- Verdicts: CloudTrail evidence alone gives `Expiring-InUse` only when a qualifying pull remains more than 60 seconds after push; tier (a) or (b) evidence gives `Expiring-InUse` regardless of denied checks; `Expiring-Unknown` is reserved for denied checks when (a) and (b) are empty.
- Every Expiring Images row names the evidence tier that produced its verdict.
- Check Matrix grows to 15 rows: R1 follows the filtered result, new U8 (LOW, informational, never moves the rating) reports how many CloudTrail events were excluded as push correlated. CloudTrail probe also looks up `PutImage` to learn the pushing principal.
- Two evaluation style evals added (push correlated event excluded, consumer pull three days later). 12 evals.
