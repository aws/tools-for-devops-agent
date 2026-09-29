# Changelog

## [1.1.1] - 2026-09-29
### Changed
- Restructured the skill for progressive disclosure: the SKILL.md body is now a slim
  checkbox-checklist workflow with a dedicated validate-findings step, and detailed
  material lives in `references/` (billing-model, api-inventory, opportunities) and
  `assets/report-template.md`. Best-practices evals score 100/100.
### Added
- Migrated `evals/evals.json` to the current schema and made the functional suite
  file-independent and uplift-oriented (6 scenarios): inlined the duplicate-reasoning
  and artifact-naming data, added a dedup-vs-exclusion interaction scenario exercising
  the §4.1/§4.3 rule, and added a negative-trigger case. Structure, best-practices, and
  functional eval results committed.

## [1.1.0] - 2026-09-28
### Changed
- Added an explicit interaction rule to §4.1: de-duplicating to a single management-event trail makes the survivor the free first copy, so KMS/RDS exclusion and Read-event trimming must not also be recommended on it. Prevents the contradictory "delete the duplicate trail and exclude KMS/RDS on the surviving trail" recommendation that leaves no trail capturing those events.
- Rewrote §4.3 to require that a paid (second-or-later) management-event copy actually exists and is kept before recommending KMS/RDS exclusion. Excluding on the single/soon-to-be-single authoritative trail saves ~$0 (first copy per Region is free) and is now reported as inapplicable rather than as a saving.
### Added
- Known Quirk: de-duplication and management-event filtering are mutually exclusive on the same copy; never stack the two savings.

## [1.0.0] - 2026-09-24
### Added
- Initial release of the CloudTrail cost optimization skill for AWS DevOps Agent
- Read-only inventory of trails (including multi-Region shadow and Organizations trails) and CloudTrail Lake event data stores
- Cost optimization checks across seven areas: duplicate management-event trails, unnecessary Read management events, high-volume noise events (AWS KMS, RDS Data API), overly broad and duplicate data event logging, CloudTrail Lake pricing option/retention/duplicate ingestion, S3 destination lifecycle hygiene, and idle/stopped trails
- Cost attribution via Cost Explorer usage types and volume proxies (CloudWatch usage metrics, S3 bucket size) with estimated monthly savings
- Severity-ranked findings (CRITICAL, HIGH, MEDIUM, LOW, INFO) and a shareable Markdown report artifact named `cloudtrail-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
- Compliance-aware, read-only guidance — no trail, event selector, or Lake mutations
- Evaluation test cases (5 functional evals, 6 trigger queries)
