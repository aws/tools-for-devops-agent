# Changelog

## [1.1.1] - 2026-09-29
### Changed
- Sharpened the Runtime Monitoring ↔ VPC Flow Log offset check (§4.2 in
  `references/opportunities.md`): the agent-gap case now spells out the "worst of both
  worlds" mechanism — when the agent is not transmitting the offset does not apply, so
  the account keeps paying VPC Flow Log processing charges *and* the Runtime Monitoring
  plan while getting no runtime coverage; fix agent coverage rather than treating it as
  a saving.
### Added
- Migrated `evals/evals.json` to the current schema and added a file-independent,
  uplift-oriented functional eval suite (6 scenarios incl. runtime-offset,
  log-config-quirk, runtime-agent-gap, security-tradeoff, and a negative-trigger case).
  Best-practices, structure, and functional eval results all pass (best-practices
  100/100).

## [1.1.0] - 2026-09-28
### Changed
- Restructured the skill for progressive disclosure to fix failing best-practices evals (BP-03, BP-12, BP-16) and the BP-17 warning. The SKILL.md body is now a slim checkbox-checklist workflow; detailed material moved into linked files.
- Converted the Step 1–5 workflow to a `- [ ] Step N` checklist and added a dedicated **Step 5: Validate findings** self-check (savings sum and trace to signals, correct byte-to-GB/TB conversions, every plan reduction framed as a cost-vs-risk tradeoff, Runtime Monitoring ↔ VPC Flow Log offset accounted for, no mutations) before report generation.
### Added
- `references/billing-model.md` (per-plan metric/unit/pricing table and the two critical billing behaviors), `references/data-collection.md` (inventory APIs and usage-metric collection), and `references/opportunities.md` (the full Step 4.1–4.7 checks).
- `assets/report-template.md` holding the report structure and table schemas, linked from Step 6.

## [1.0.0] - 2026-09-24
### Added
- Initial release of the Amazon GuardDuty cost optimization skill for AWS DevOps Agent
- Read-only inventory of detectors, enabled protection plans, Runtime Monitoring coverage, and organization member coverage
- Per-protection-plan spend attribution from the `AWS/GuardDuty` and `AWS/GuardDuty/MalwareProtection` CloudWatch usage metrics, reconciled against Cost Explorer when available
- Cost optimization checks across seven areas: high-cost/low-signal protection plans, the Runtime Monitoring ↔ VPC Flow Log charge offset, S3 Protection cost-vs-value, Malware Protection for S3 scan volume, 30-day free-trial post-trial cost projection, duplicate/inconsistent multi-account and unused-Region coverage, and Security Hub consolidated-pricing awareness
- Cost-vs-security framing throughout, using `GetFindingsStatistics` as the value signal
- Severity-ranked findings (CRITICAL, HIGH, MEDIUM, LOW, INFO) and a shareable Markdown report artifact named `guardduty-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
- Read-only guidance — no detector or protection-plan mutations
- Evaluation test cases (5 functional evals, 6 trigger queries)
