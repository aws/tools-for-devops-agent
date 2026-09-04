# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-09-01

### Added

- Monitoring and observability checks in D5, following TFC domain review feedback:
  **5.4** verifies an AWS Backup Audit Manager report plan is scheduled in each Region
  with backup activity — report plans are per Region, so one does not cover the
  others — and **5.5** verifies an Audit Manager framework is configured where
  protected resources exist, since a report plan alone reports job activity without
  evaluating control compliance. Both consume `ListReportPlans` and `ListFrameworks`,
  which the data collection phase already gathered but no check previously used.
  Coverage is a point-in-time state; these two ask whether a decline in it would be
  noticed.

- Initial release for AWS DevOps Agent.
- Read-only AWS Backup coverage and posture review across all enabled Regions of a
  single account.
- Five-state coverage model (`Protected`, `Stale`, `SelectedNotProtected`,
  `Unprotected`, `OptInBlocked`) that distinguishes backup plan membership from
  actual protection.
- 23 fixed, numbered checks across 5 dimensions: service enablement, coverage,
  plan quality, vault posture, and coverage integrity. Thresholds match the AWS
  Backup Audit Manager control defaults so results are comparable with Audit
  Manager output.
- Independent resource inventory with an AWS Config fast path
  (`config:SelectResourceConfig`) and a direct per-service enumeration fallback, so
  the review works in accounts where AWS Config is not recording.
- Per-Region resource type opt-in detection, covering the case where a backup plan
  and selection appear correct in the console but AWS Backup will never protect the
  resource.
- Selection breadth check that flags ARN-only backup selections, which cannot match
  resources created after the selection was written.
- Four-state status enum (`OK`, `NotConfigured`, `AccessDenied`, `ToolingFailure`)
  plus `NotEnumerated`, with the rule that permission gaps cap the Coverage Rating
  at Medium rather than being scored as coverage gaps.
- Coverage Rating roll-up (High / Medium / Low / Indeterminate) with deterministic
  criteria.
- Report format with a Coverage Matrix, a mandatory 23-row Check Coverage Matrix,
  severity-ranked findings, SLA-bucketed next steps, and 11 pre-render validation
  checks.
- Final Delivery Contract so the full report is returned verbatim regardless of how
  the request is phrased.
- Reference documents for data collection, coverage logic, report format, and
  best-practices remediation with a canonical AWS documentation URL list.
- Minimum report skeleton inlined into `SKILL.md` so the report structure survives
  when `references/` is not loaded — for example when the account sweep is
  delegated to a research subagent, which returns data but must never render the
  final answer.
- Region sweep discipline: every enabled Region is swept unless the user narrows
  scope, and any unswept Region is disclosed in the Scope table and caps the
  Coverage Rating at Medium, since the denominator is incomplete.
- Per-Region S3 evaluation: buckets are resolved to their own Region with
  `GetBucketLocation` and judged against that Region's opt-in setting, because S3
  can be opted in for one Region and out for another in the same account.
- Dangling-ARN sub-check on backup selections, escalating an ARN-only selection to
  CRITICAL when the referenced resource no longer exists.
- `OrphanedRecoveryPoint` coverage state for resources that still appear in
  `ListProtectedResources` after deletion. Excluded from the numerator, the
  denominator, and from `Stale`, since a deleted resource can be neither covered nor
  uncovered.
- Output Contract at the top of `SKILL.md` plus a countable self-check, after live
  testing showed the report being replaced by a conversational summary when the
  account sweep was delegated to a research subagent.
- Single-source-of-truth counting: aggregate counts are computed once in the
  account-wide by-resource-type table and quoted everywhere else. Per-Region totals
  and percentages were removed after they repeatedly disagreed with the account
  total.
- Precision discipline: the coverage percentage is presented as indicative, bulk
  resource-type counts must state their provenance or be marked `Unconfirmed` rather
  than estimated, and coverage totals may never be used to justify a severity.
- Pre-render validation expanded from 11 to 18 checks, adding arithmetic
  reconciliation, a prohibition on duplicate findings, and a prohibition on invented
  or blended severities.
- Documented that `AIDevOpsAgentAccessPolicy` already covers 43 of the 49 actions
  used, with only five needing to be added, and that each Agent Space has its own
  IAM role requiring the policy separately.
