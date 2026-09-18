---
name: acm-certificate-ops-review
description: "Investigation and review procedures for AWS Certificate Manager (ACM)\
  \ and ACM Private CA certificate health across one or more accounts and regions.\
  \ Use this skill when investigating TLS/SSL certificate problems or reviewing certificate\
  \ posture - certificates expiring soon or already expired, failed or stuck managed\
  \ renewals, certificates stuck in PENDING_VALIDATION, DNS or email domain validation\
  \ failures, endpoints still serving an old certificate after renewal, imported certificates\
  \ that ACM cannot auto-renew, weak or legacy key algorithms (RSA_1024), unused or\
  \ in-use certificates, missing CloudWatch DaysToExpiry expiry monitoring, ACM Private\
  \ CA issues, and readiness for the CA/Browser Forum TLS certificate validity reductions\
  \ (398 to 47 days by March 2029). Also use it for questions about certificate expiry\
  \ as a cause of outages, certificate renewal automation, or DV vs OV/EV certificate\
  \ strategy."
metadata:
  author: majamuda, vmgaddam
  version: "1.2.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  aws-devops-agent-skills.aws-services: "AWS Certificate Manager, AWS Private CA"
  aws-devops-agent-skills.technical-domains: "Security"
---

> **Important:** ACM and related services evolve frequently (new features,
> protocol support, pricing changes, validity rules). Before making any
> recommendation, verify the current service capabilities against the official
> AWS documentation. Do not rely on cached assumptions from prior runs or from
> this skill's reference files alone. If a feature status is uncertain,
> check the ACM What's New page and user guide for the latest updates before
> advising.

# ACM Certificate Operations Review

Use this skill when investigating or reviewing AWS Certificate Manager (ACM)
and ACM Private CA certificate health. Certificate expiry is a leading cause
of avoidable customer-facing outages, and the CA/Browser Forum has mandated
progressive reductions in TLS certificate validity (398 -> 198 -> 100 -> 47
days by March 2029), which makes manual certificate management increasingly
risky.

This skill has two phases:

- **Phase 1 - Operational review (always applies).** Inventory certificates,
  detect health problems, and produce a prioritized findings report. This is
  the core investigation runbook.
- **Phase 2 - CA/Browser Forum readiness (apply when the operator asks about
  strategic impact, validity reductions, automation readiness, or cost).**
  When the operator asks about strategic impact, validity reductions,
  automation readiness, or cost, load
  [references/cab-forum-readiness.md](references/cab-forum-readiness.md).
  Note: the migration decision tree covers TWO automation paths for workloads
  outside integrated AWS services: ACM ACME and AWS Workload Credentials Provider.

Threshold values, risk levels, and the required report layout are defined in
the reference files. Read them when you reach the step that needs them.

## When to use this skill

Load and follow this skill when the task involves any of the following:

- A certificate is expiring soon, has expired, or an operator wants to know
  what will expire in the next N days.
- A managed renewal failed, is stuck, or a certificate is stuck in
  `PENDING_VALIDATION`.
- An endpoint is still presenting an old certificate after a renewal or
  re-issue.
- Domain validation (DNS `CNAME` or email) is failing.
- An imported certificate is in use and ACM cannot manage its renewal.
- A certificate uses a weak or legacy key algorithm.
- There is no CloudWatch alarm on the `DaysToExpiry` metric for an important
  certificate.
- An ACM Private CA is expiring, disabled, or its certificates are affected.
- An operator wants a certificate posture review across an account or an
  organization.

## Scope of investigation

Before scanning, establish scope:

1. **Accounts** - a specific account, a list of accounts, or (only when
   explicitly requested) all linked accounts in the organization discovered
   via `organizations:ListAccounts` from the management/delegated account.
2. **Regions** - always scan `us-east-1` first, because CloudFront
   certificates must live there, then the remaining commercial regions in
   scope. If the operator names regions, honor them but still include
   `us-east-1`.

Guardrails:

- Default to the specific account(s) in the incident or request. Do **not**
  scan the whole organization unless the operator explicitly asks for an
  org-wide review, and confirm first if the scan will span many accounts.
- Treat GovCloud and China partitions separately. Do not scan them unless
  explicitly requested, and never mix their findings with commercial-partition
  findings in the same output - they have separate compliance requirements.
- Scan sequentially (one account at a time). On `TooManyRequestsException`,
  back off exponentially (2s -> 4s -> 8s, max 3 retries). If several
  consecutive accounts return `AccessDenied`, stop and report only the
  accounts you could access.

- [ ] **Step 1: Inventory certificates**

For each account and region in scope:

1. Call `acm:ListCertificates` and paginate with `NextToken`. If you filter by
   key type, be aware new key types (for example post-quantum algorithms) can
   be missed - when in doubt, omit the key-type filter so every certificate is
   returned regardless of algorithm.
   **CRITICAL - always open BOTH filter axes on EVERY `ListCertificates` call.**
   `ListCertificates` silently drops certificates behind TWO independent default
   filters, and a certificate is only returned when BOTH are broadened together:
   - **Key-pair origin** - the `CertificateKeyPairOrigins` parameter defaults to
     `AWS_MANAGED` + `CUSTOMER_PROVIDED`, so ACME-origin certs are excluded.
   - **Key type** - the `Includes.keyTypes` parameter defaults to `RSA_1024` +
     `RSA_2048`, so ECDSA (e.g. `EC_prime256v1`) certs are excluded.
   Opening only one axis is the trap: an ACME cert with an ECDSA key stays
   invisible until you expand BOTH in the same call. Never issue a default or
   single-axis `ListCertificates` call. When running this step, load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the exact origin and key-type values to pass.
   **Do NOT conclude "no ACME certs" or "no ECDSA certs exist" from a call that
   did not expand both axes** - that is a false negative, not an empty result.
2. For each certificate ARN, call `acm:DescribeCertificate` to retrieve
   `Status`, `NotAfter`, `NotBefore`, `Type` (`AMAZON_ISSUED`, `IMPORTED`, or
   other values including ACME-origin certs which may show a distinct key source),
   `RenewalEligibility`, `RenewalSummary`, `KeyAlgorithm`, `InUseBy`,
   `DomainValidationOptions`, `SubjectAlternativeNames`, and key source
   (check for ACME-issued certs which appear alongside standard types).
3. For imported certificates, `InUseBy` and `NotAfter` are still available;
   note that ACM cannot auto-renew imported certificates.
4. **Verify filter coverage before reporting.** Before presenting the inventory
   or concluding a category is absent, confirm the `ListCertificates` call(s)
   for each region expanded BOTH the key-pair origin axis (including `ACME`) and
   the key-type axis (including the `EC_*` types). If either axis was left at its
   default, re-run the call with both expanded. Only after this check may you
   state whether ACME-origin or ECDSA certificates are present or absent.
5. Present a short inventory summary (account, region, certificate count)
   before moving on, and skip account/region pairs that return zero
   certificates.

- [ ] **Step 2: Detect issues**

Evaluate every certificate against the checks below. When evaluating
certificates in this step, load
[references/acm-thresholds.md](references/acm-thresholds.md) for the thresholds
and risk levels.

1. **Expiry** - compute days until `NotAfter`. Flag expired and
   soon-to-expire certificates, weighted higher when `InUseBy` is non-empty.
2. **Renewal health** - inspect `RenewalSummary.RenewalStatus`. Flag
   `PENDING_VALIDATION`, `FAILED`, and `PENDING_AUTO_RENEWAL` that is not
   progressing. Capture `RenewalStatusReason` and the per-domain
   `ValidationStatus`.
3. **Validation failures** - for `PENDING_VALIDATION`, check
   `DomainValidationOptions`: for DNS validation confirm the required `CNAME`
   `ResourceRecord` exists and resolves; for email validation note that it
   blocks automated renewal.
4. **Email-validated certificates (CA/B Forum deprecation)** - identify
   `AMAZON_ISSUED` certificates where `DomainValidationOptions.ValidationMethod
   = EMAIL`. Classify using these rules (use `acm:DescribeCertificate` - no new
   permissions required):
   - `AMAZON_ISSUED` + `ValidationMethod=DNS` - DNS validated (GREEN, no action)
   - `AMAZON_ISSUED` + `ValidationMethod=EMAIL` - flag as **AMBER**: email
     validation is being deprecated by the CA/B Forum. ACM will stop issuing
     email-validated certificates on **March 31, 2027** and stop renewing them
     on **September 30, 2027**. Recommend switching to DNS validation NOW using
     `UpdateCertificateOptions` (ARN stays the same - no disruption to
     load balancers, CI/CD, or service integrations). The customer has 72 hours
     to add the CNAME records after initiating the switch. Monitor progress via
     `ListCertificateDomainValidations`.
   - `AMAZON_ISSUED` + `CertificateKeyPairOrigin=ACME` - ACM ACME issued, not
     in scope for email-to-DNS migration (ACME certs use client-side key and
     PRE_APPROVED endpoint authorization - no email/DNS challenge at issuance).
   - `IMPORTED` or `PRIVATE` - not in scope for this check.
5. **Imported certificates in use** - flag `Type = IMPORTED` with a non-empty
   `InUseBy`, since these will not auto-renew and are an outage risk.
6. **Weak or legacy keys** - flag `KeyAlgorithm` of `RSA_1024` (and any
   algorithm below current best practice). When flagging, recommend the
   stronger alternative:
   - RSA_1024 → recommend minimum RSA_2048 (or ECDSA P-256 for better
     performance and smaller key size)
   - RSA_2048 is acceptable today but note that ECDSA P-256 (EC_prime256v1)
     or P-384 (EC_secp384r1) are the modern best practice (faster TLS
     handshake, stronger security per bit, and the default for ACME clients).
   Always verify the current list of algorithms ACM supports at runtime
   (check ACM docs / API for supported keyTypes). When new algorithms are
   added (e.g. post-quantum), include them in the recommendation if they
   offer stronger security. Do not limit recommendations to a static list.
7. **Unused certificates** - flag issued certificates with an empty `InUseBy`
   as cleanup or cost-optimization candidates (do not auto-delete).
8. **ACME-issued certificates** - identify certificates with key source ACME
   (visible in ListCertificates / DescribeCertificate). These auto-renew via
   the ACME client and have short validity (currently 45 days). Classify as
   GREEN if the ACME client is active; flag as RED if the cert is expired
   (suggests the client stopped renewing).
   When ACME certs are found, run the renewal-pipeline sub-checks (endpoint
   health, EAB status, ACME account status) to verify renewals are healthy.
   When running this check, load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the full sub-check procedures and their RED/AMBER classification rules.
9. **Missing expiry monitoring** - for in-use certificates, check for a
   CloudWatch alarm on the ACM `DaysToExpiry` metric
   (`AWS/CertificateManager`, dimension `CertificateArn`) via
   `cloudwatch:DescribeAlarmsForMetric`. Flag certificates with no alarm.
   Two monitoring options exist (recommend both where possible):
   - **CloudWatch DaysToExpiry alarm** (per-cert, self-managed) - works for
     ALL certificate types (imported, ACM-issued, and ACME). Recommended
     threshold: <= 30 days, period 1 day, statistic Minimum.
   - **EventBridge `ACM Certificate Approaching Expiration`** (automatic,
     no per-cert setup) - fires daily starting 30 days before expiry for
     public certs. NOTE: `ACM Certificate Expired` events are NOT available
     for imported certificates - so CloudWatch alarms are the only safety
     net for imported certs.
10. **Stale endpoint after renewal** - if a certificate was renewed or
   re-issued but a dependent endpoint still serves the old certificate,
   confirm the resource references the new certificate ARN and that the
   distribution/load balancer has finished deploying.
11. **ACM Private CA** - where relevant, call `acm-pca:ListCertificateAuthorities`
   and `acm-pca:DescribeCertificateAuthority`; flag CAs that are `DISABLED`,
   `EXPIRED`, or nearing expiry, since a CA problem affects every certificate
   it issued.

- [ ] **Step 3: Classify and prioritize**

Assign each finding a risk level (RED / AMBER / GREEN). When classifying in
this step, load [references/acm-thresholds.md](references/acm-thresholds.md)
for the criteria. Rank by risk, then by whether the certificate
is in use, then by days to expiry. In-use certificates always outrank unused
ones at the same expiry distance.

- [ ] **Step 4: Produce the findings report**

When producing the report in this step, load
[references/report-format.md](references/report-format.md) and generate a
prioritized findings report following its structure. It must include:

- A one-paragraph executive summary (overall posture, count by risk level,
  most urgent item).
- A prioritized findings table (account, region, certificate/domain, type,
  status, days to expiry, in-use, risk, recommendation).
- A remediation list ordered by priority.

Reporting rules:

- Compute every number (days to expiry, counts, any cost estimate) in code or
  by explicit arithmetic on retrieved values - never estimate figures.
- Include an AI-generated-content disclaimer on the report.
- If this report may be shared outside the operations team, keep it factual
  and free of internal-only identifiers.

- [ ] **Step 5: CA/B Readiness Snapshot (always run)**

After the findings report, ALWAYS append a brief CA/B readiness snapshot
using the Phase 1 inventory. Classify each in-use certificate into:
- GREEN: fully automated renewal in place (ACM-managed on integrated services,
  or ACME-issued with active client). No action needed as validity shrinks.
- AMBER: partially automated or has a constraint (e.g. email validation,
  exportable cert without Workload Credentials Provider configured).
- RED: manual renewal process (imported certs with no automation path).

Present as a 3-line summary:
- GREEN count, AMBER count, RED count
- One-sentence risk statement (e.g. "X of Y active certificates will require
  manual rotation at 47-day intervals by March 2029 without remediation.")
- Offer: "For detailed migration paths and automation options, ask for the
  full CA/B Forum readiness assessment."

- [ ] **Step 6 (on request): Full CA/B Forum readiness**

If the operator asks for the full assessment (migration paths, gap analysis,
automation options, cost), load
[references/cab-forum-readiness.md](references/cab-forum-readiness.md), which
uses the Phase 1 inventory as its input.

## Required IAM permissions

Read-only. See `README.md` for the full list. Core actions:
`acm:ListCertificates`, `acm:DescribeCertificate`,
`acm-pca:ListCertificateAuthorities`, `acm-pca:DescribeCertificateAuthority`,
`cloudwatch:DescribeAlarmsForMetric`, and, for org-wide scans,
`organizations:ListAccounts`.
