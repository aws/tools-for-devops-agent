# Changelog

All notable changes to the `acm-certificate-ops-review` skill are documented
in this file. The format is based on Keep a Changelog, and this project follows
semantic versioning.

## [1.1.0] - 2026-09-10

Authors: Tejas Majamudar (majamuda), Manoj Gaddam (vmgaddam)

### Added
- AWS Workload Credentials Provider (WCP) as a second automation path in the
  CA/Browser Forum migration decision tree, alongside ACM ACME.
- ACME certificate discovery: dual-axis `ListCertificates` filtering that
  expands both `CertificateKeyPairOrigins` (to include `ACME`) and
  `Includes.keyTypes` (to include EC key types), so ACME-origin and ECDSA
  certificates are no longer silently dropped by the default filters.
- Step 1 verification step: confirm both filter axes were expanded before
  reporting inventory or concluding that a certificate category is absent.
- New reference file `references/acm-detection-details.md` holding the full
  key-pair origin / key-type filter values and the ACME renewal-pipeline
  sub-checks (endpoint health, EAB status, ACME account status).
- Functional evaluation suite (`evals/evals.json`) covering ACME discovery,
  risk classification, and negative-trigger cases.

### Changed
- Converted the Step 1-6 headings to a checklist format for clearer sequential
  execution.
- Moved the detailed detection enumerations out of `SKILL.md` into
  `references/acm-detection-details.md`, keeping the body concise.
- Narrowed the declared agent type to Chat tasks only, and aligned the README.

## [1.0.0] - 2026-07-12

Authors: Tejas Majamudar (majamuda), Manoj Gaddam (vmgaddam)

### Added
- Initial release of the ACM Certificate Operations Review skill.
- Phase 1 operational investigation runbook: certificate inventory across
  accounts/regions, issue detection (expiry, renewal health, validation
  failures, imported-in-use, weak keys, unused certs, missing DaysToExpiry
  monitoring, stale endpoints, ACM Private CA), risk classification, and a
  prioritized findings report.
- Reference files: `acm-thresholds.md`, `report-format.md`, and
  `cab-forum-readiness.md` (Phase 2 CA/Browser Forum readiness).
- Read-only IAM permission set documented in the README.
