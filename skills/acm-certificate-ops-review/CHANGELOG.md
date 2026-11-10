# Changelog

All notable changes to the `acm-certificate-ops-review` skill are documented
in this file. The format is based on Keep a Changelog, and this project follows
semantic versioning.

## [1.3.0] - 2026-10-16

Authors: Tejas Majamudar (majamuda)

### Added
- Legacy IAM server certificate check (Step 2, check 12).
- Certificate hygiene check (Step 2, check 13): duplicate certificates and
  certificate quota proximity. There is no check for certificate transparency
  opt-out, because ACM removed that option in June 2026.
- Private CA assessment (Step 2, check 11) rebuilt from the AWS Private CA user
  guide: status handling for expired, disabled, pending, creating, and failed
  CAs, matching of ACM private certificates to their CA, revocation configuration
  for general-purpose CAs, the CA retirement sequence, and the audit report as the
  operator-run way to list certificates a CA issued.
- DV/OV/EV derivation for imported certificates (Step 2, check 14).
- ACME PrivateLink check (Step 2, check 15) for Regions with ACME certificates:
  interface endpoint presence, state, private DNS, endpoint policy, and security
  group. Based on the October 2026 ACM PrivateLink launch.
- Why / Action / Complications detail for every RED and AMBER finding, with a
  complications table in `references/report-format.md`.
- Status thresholds for `FAILED`, `VALIDATION_TIMED_OUT`, and long-pending
  validation.

### Changed
- Step 1 now collects data in parallel batches across Regions instead of one
  call at a time, to reduce narration overhead and review time.
- Step 1 now inventories with `acm:SearchCertificates`, which returns ACME-origin
  and ECDSA certificates without filter parameters, so the two default
  `ListCertificates` filters no longer hide certificates. `ListCertificates` is
  no longer used. If the search is denied, the skill reports "Unable to verify -
  access denied" and names the missing permission. When no ACME certificate is
  found, one `SearchCertificates` call filtered on key-pair origin `ACME` confirms
  it before the skill reports none.
- Key algorithm checks treat `RSA_2048` and `RSA-2048` spellings as the same.
- ACME renewal-pipeline calls (`DescribeAcmeEndpoint`, `ListAcmeAccounts`,
  `ListAcmeExternalAccountBindings`) now run in the Step 1 parallel batches, using
  the endpoint ARN from the search results. `DescribeAcmeAccount` needs an
  `AccountUrl`, not an account ID.
- `acm:DescribeCertificate` now runs only for certificates that are in use, are
  not `ISSUED` or `EXPIRED`, or are `PRIVATE`, because the search results already
  cover what the checks need for the rest.
- Documented the `use_aws` call format and how to record a sub-check that the
  platform guardrail cancels.
- Step 1 now forbids `ListCertificates` and tells a delegated subagent to use
  `SearchCertificates`, after a functional run showed a subagent inventorying with
  default `ListCertificates` and missing the ACME certificate.
- The description now covers plain "list my certificates" requests.
- The report must cover ACM certificates, Private CAs, and IAM server
  certificates even when empty, name each Private CA by common name, say a
  pending or disabled CA is billed but cannot issue, and never claim a CA has no
  dependent certificates.
- A fixed sentence now states the Private CA visibility limit, every IAM server
  certificate finding must include the migrate to ACM action, a revoked external
  account binding is stated as blocking only new registrations, the email
  validation answer names AMBER, `UpdateCertificateOptions` and
  `ListCertificateDomainValidations`, and the datetime tool is called at most
  once.
- Check 12 now makes the IAM server certificate check mandatory and its "migrate
  to an ACM certificate" action required, even for narrowly phrased requests.
- Each finding now gets exactly one risk level, and the executive summary counts
  must match the findings table. Follow-up answers keep the IAM action and count
  totals from the listed items.
- The CA/B snapshot and the full readiness assessment now classify certificates
  with the same renewal-mechanism rules, leave failed and self-signed
  certificates out of the counts, and the CA/B offer ends the user-facing
  answer.
- Step 1 now always calls `ec2:DescribeRegions` and sweeps every enabled Region,
  after a test where the agent took its Region list from the agent space topology
  and missed two eu-west-1 certificates. Unswept Regions are listed in the report.
  A Region list in a task or brief narrows the sweep only when it quotes the
  user naming those Regions. Agent space topology maps application resources,
  not certificates: in the test it reported eu-west-1 as empty while that Region
  held two ACM certificates, so it cannot replace `ec2:DescribeRegions`.
- The CA/B snapshot and full assessment now count only publicly trusted
  certificates, define the self-signed test, and show not-issued, self-signed,
  and private certificates as separate uncounted groups. The CA/B offer is now
  the last line of the report.
- The IAM server certificate migrate-to-ACM action now applies where ACM is
  supported; in a Region ACM does not support, the skill recommends monitoring
  and re-upload instead.
- Moved the email-validation deadlines, key-algorithm recommendations, and
  expiry-monitoring settings from SKILL.md into `references/acm-detection-details.md`.
- Added `acm:SearchCertificates`, the ACME read actions (`acm:DescribeAcmeEndpoint`,
  `acm:ListAcmeAccounts`, `acm:ListAcmeExternalAccountBindings`), the IAM,
  `ec2:DescribeRegions`, `ec2:DescribeVpcEndpoints`, and
  `ec2:DescribeSecurityGroups` permissions to the required list.

## [1.2.0] - 2026-09-18

Authors: Tejas Majamudar (majamuda)

### Added
- Email-validated certificate detection (Step 2, check #4): identifies
  `AMAZON_ISSUED` certificates where `ValidationMethod = EMAIL` and flags
  them as AMBER. The CA/B Forum is deprecating email-based domain validation
  for publicly trusted certificates - ACM will stop issuing email-validated
  certificates on **March 31, 2027** and stop renewing them on
  **September 30, 2027**. Remediation: switch in-place via
  `UpdateCertificateOptions` (ARN unchanged, 72-hour CNAME window). ACME-origin
  and IMPORTED/PRIVATE certificates are explicitly excluded from this check.
- New eval scenario `acm-email-validation-deprecation` covering the AMBER
  classification, correct 2027 deadlines, and `UpdateCertificateOptions`
  remediation assertions.

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
