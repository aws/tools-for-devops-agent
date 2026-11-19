# Changelog

All notable changes to the `iam-access-navigator` skill are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-25
### Pre-release fixes (2026-11-03)
- Least-privilege: `LookupEvents` sees management events only. Granted S3 object actions are kept and flagged as unverified when no data-event source exists, and a role is never called unused on that basis (new Nuance 4, also in the SKILL.md body).
- Access-key hygiene: data-event and SES SMTP caveats on last-used flags (marked unverified), an SMTP-rotation warning on the deactivate → monitor → delete ladder, and a coverage line naming a denied `iam:ListAccessKeys` or `iam:GetAccessKeyLastUsed`.
- README prerequisites name the key-metadata actions and no longer imply the AWS managed DevOps Agent policies cover them.
### Added
- Initial release: an advisory, read-only IAM identity-risk reasoning skill for
  AWS DevOps Agent.
- **No dependency on IAM Access Analyzer analyzers or Security Hub.** Triage
  derives its own findings from raw IAM + CloudTrail (the primitives every
  account has); Access Analyzer and Security Hub findings are optional enrichment
  only. Policy validation uses the on-demand Access Analyzer validation APIs,
  which need no analyzer configured.
- **Must-have capabilities:** risk triage + prioritization; blast-radius /
  change-safety reasoning; least-privilege synthesis (with the CloudTrail
  session-name-vs-role-name correction, honest unused→empty handling, and
  valid-IAM-action normalization including the Lambda API-version-date-suffix
  quirk); and an educational/conversational teaching character encoded as
  behavior.
- **Should-have capabilities:** access-key / credential hygiene with a safe
  deactivate→monitor→delete migration ladder; IAM policy validation via Access
  Analyzer plus dangerous-action and missing-condition heuristics; and rollback
  reasoning (pre-change snapshot, reversal steps, trigger conditions).
- **Ambitious capability (advisory):** forensics / backwards-troubleshooting that
  reconstructs an out-of-band IAM change from CloudTrail and correlates it to a
  symptom, with an explicit confidence rubric and confirming test.
- The **coverage contract** across all capabilities: every data source is
  reported as checked / empty / unavailable, and the skill refuses conclusions
  (and, for least privilege, refuses to propose a policy) when load-bearing data
  is unavailable.
- `references/` detail for each capability; `README.md` with the non-production
  disclaimer, prerequisites, usage, and the skill-vs-MCP boundary.
