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
  \ (398 to 47 days by March 2029). Also use it to list or inventory ACM certificates, including ACME-issued and ECDSA ones, and for questions about certificate expiry\
  \ as a cause of outages, certificate renewal automation, or DV vs OV/EV certificate\
  \ strategy."
metadata:
  author: majamuda, vmgaddam
  version: "1.3.0"
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
2. **Regions** - sweep every enabled Region, starting with `us-east-1`
   (CloudFront certificates must live there). Only Regions the operator names
   narrow the scope; still include `us-east-1`. A Region list in your task or
   brief counts as operator scope only when the brief quotes the user naming
   those Regions (for example "user asked for us-east-1 only"). Any other Region
   list, including one taken from the agent space topology, lists Regions where
   resources were discovered, not all enabled Regions: ignore it and sweep every
   enabled Region. If unsure, sweep every enabled Region.

Guardrails:

- Default to the specific account(s) in the incident or request. Do **not**
  scan the whole organization unless the operator explicitly asks for an
  org-wide review, and confirm first if the scan will span many accounts.
- Treat GovCloud and China partitions separately. Do not scan them unless
  explicitly requested, and never mix their findings with commercial-partition
  findings in the same output - they have separate compliance requirements.
- Process accounts one at a time, but inside one account run independent API
  calls in parallel across regions (see Step 1). On `TooManyRequestsException`,
  back off exponentially (2s -> 4s -> 8s, max 3 retries) for the throttled calls
  only. If several consecutive accounts return `AccessDenied`, stop and report
  only the accounts you could access.

- [ ] **Step 1: Inventory certificates**

Collect data in parallel batches. Calls inside one batch do not depend on each
other, so send them together in ONE step across all regions in scope, and do not
wait for or inspect one result before sending the next. Writing narration
between individual calls is the main cause of slow runs. Every `use_aws` call
must include `service_name` and `operation_name` - see the call format in
[references/acm-detection-details.md](references/acm-detection-details.md).

**Never call `acm:ListCertificates`.** With its default filters it hides
ACME-origin and ECDSA certificates and returns a false "none found". Take the
certificate inventory from `acm:SearchCertificates` only.

**If you delegate the sweep to a subagent**, the subagent does not see these
steps. Do not put a Region list in its brief unless the user named those
Regions; tell it to call `ec2:DescribeRegions` and sweep every enabled Region. Put the Batch A and Batch B calls below and the rule above into its brief,
and ask it to return one row per certificate with the fields listed in Batch A.
Do not accept a subagent inventory that came from `ListCertificates`.

1. **Batch A (one step, all regions in parallel).** Always call
   `ec2:DescribeRegions` once first, unless the user explicitly named the
   Regions (see Scope). Then,
   for every enabled Region at the same time, call:
   - `acm:SearchCertificates` with no `FilterStatement` and `MaxResults` 500,
     paginating with `NextToken` until none is returned. It returns ACME-origin
     and ECDSA certificates without any filter parameters.
   - `acm-pca:ListCertificateAuthorities`.
   In the same step, once per account, call `iam:ListServerCertificates` (IAM is
   global, so use one region, for example `us-east-1`).
   Each search result already carries the certificate ARN, `Subject`, `Issuer`,
   subject alternative names, `KeyAlgorithm`, `NotBefore`, `NotAfter`, `Status`,
   `Type`, `InUse`, `RenewalEligibility`, `ValidationMethod`, and
   `CertificateKeyPairOrigin` (plus the ACME endpoint ARN and account ID for
   ACME certificates).
2. **If the search is denied or cancelled.** If `acm:SearchCertificates` is
   denied, report "Unable to verify - access denied" for that Region and name
   `acm:SearchCertificates` (Resource `*`) as the missing permission. If the
   platform cancels it, record "Unable to verify - platform guardrail". Do not
   substitute another inventory call, and never report that Region as empty.
3. Extract every certificate ARN and every Private CA ARN from the Batch A
   results in a single pass.
4. **Batch B (one step, everything in parallel).** Send together:
   - `acm:DescribeCertificate` only for certificates that need what the search
     does not return: certificates with `InUse` true, certificates whose
     `Status` is not `ISSUED` or `EXPIRED` (for example `PENDING_VALIDATION`,
     `FAILED`, `VALIDATION_TIMED_OUT`), and every `PRIVATE` certificate (its
     `CertificateAuthorityArn` links it to its CA for check 11). For all other
     certificates the search data is enough. Describing adds `InUseBy`,
     `RenewalSummary` and its failure reason, and `DomainValidationOptions`
     (the DNS records).
   - `cloudwatch:DescribeAlarmsForMetric` for every certificate with `InUse` true.
   - `acm-pca:DescribeCertificateAuthority` for every Private CA ARN.
   - `iam:GetServerCertificate` for every IAM server certificate found in Batch A.
   - `ec2:DescribeVpcEndpoints`, only in Regions where Batch A returned
     ACME-origin certificates, filtered on the service name
     `com.amazonaws.<region>.acm-acme-enroll` (see check 15).
   - For each distinct ACME endpoint ARN on the ACME-origin certificates (search
     results carry `AcmeEndpointArn` and `AcmeAccountId`):
     `acm:DescribeAcmeEndpoint`, `acm:ListAcmeAccounts`, and
     `acm:ListAcmeExternalAccountBindings` (see check 8).
5. **Batch C (only if Batch B found an ACME VPC endpoint).** Call
   `ec2:DescribeSecurityGroups` with `GroupIds` set to the groups attached to it.
   Never call it unfiltered: an account can have hundreds of security groups.
6. **Data notes.** ACME-issued certificates can have an empty `Subject`; identify
   them by their subject alternative names. A `FAILED` or never-validated
   certificate can have no `NotAfter` or `Issuer`; skip date arithmetic for it
   and report "no expiry date". Imported certificates cannot be auto-renewed by
   ACM. Key algorithm names can be spelled `RSA_2048` (underscore) or `RSA-2048`
   (hyphen) depending on the API. Treat the two forms as identical in every
   key-algorithm check.
7. **Verify inventory completeness before reporting.** Before presenting the
   inventory or concluding that a category is absent, confirm each Region's
   inventory came from a `SearchCertificates` call with all pages read (no
   `NextToken` left). If a Region was not searched or its search was denied,
   it is "not verified", never "none". If no Region returned an ACME-origin
   certificate, send one more `SearchCertificates` call per Region, all in
   parallel in one step, with a `FilterStatement` that filters
   `CertificateKeyPairOrigin` on `ACME` (see
   [references/acm-detection-details.md](references/acm-detection-details.md)),
   before stating that no ACME-origin certificates exist. Only then may you say
   whether ACME-origin or ECDSA certificates are present or absent.
8. Present a short inventory summary (account, region, certificate count)
   before moving on, and skip account/region pairs that return zero
   certificates.

- [ ] **Step 2: Detect issues**

Evaluate every certificate against the checks below. When evaluating
certificates in this step, load
[references/acm-thresholds.md](references/acm-thresholds.md) for the thresholds
and risk levels.

1. **Expiry** - compute days until `NotAfter`. Flag expired and
   soon-to-expire certificates, weighted higher when the certificate is in use.
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
   = EMAIL`. Classify using these rules (`ValidationMethod` is already in the
   Step 1 search results, so no extra call is needed):
   - `AMAZON_ISSUED` + `ValidationMethod=DNS` - DNS validated (GREEN, no action)
   - `AMAZON_ISSUED` + `ValidationMethod=EMAIL` - **AMBER**. In every answer
     about email validation, state AMBER, name `UpdateCertificateOptions` as the
     fix and `ListCertificateDomainValidations` as the monitoring call. Load
     [references/acm-detection-details.md](references/acm-detection-details.md)
     for the deadlines and switch procedure.
   - `AMAZON_ISSUED` + `CertificateKeyPairOrigin=ACME` - ACM ACME issued, not
     in scope for email-to-DNS migration (ACME certs use client-side key and
     PRE_APPROVED endpoint authorization - no email/DNS challenge at issuance).
   - `IMPORTED` or `PRIVATE` - not in scope for this check.
5. **Imported certificates in use** - flag `Type = IMPORTED` with a non-empty
   `InUseBy`, since these will not auto-renew and are an outage risk.
6. **Weak or legacy keys** - flag `RSA_1024` (also spelled `RSA-1024`) and any
   algorithm below current best practice, and recommend a stronger one. Load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the recommendations.
7. **Unused certificates** - flag issued certificates that are not in use
   (`InUse` false, or an empty `InUseBy` where it was fetched) as cleanup or
   cost-optimization candidates (do not auto-delete).
8. **ACME-issued certificates** - identify certificates with key source ACME
   (key-pair origin `ACME` in the Step 1 results). These auto-renew via
   the ACME client and have short validity (currently 45 days). Classify as
   GREEN if the ACME client is active; flag as RED if the cert is expired
   (suggests the client stopped renewing).
   When ACME certs are found, run the renewal-pipeline sub-checks (endpoint
   health, EAB status, ACME account status) to verify renewals are healthy,
   using the ACME call results collected in Step 1.
   When running this check, load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the full sub-check procedures and their RED/AMBER classification rules.
   Check 15 covers the network path to the ACME endpoint. A revoked external
   account binding blocks only new ACME account registrations. Never present it
   as a cause of a failed renewal on an existing `VALID` account; say that
   renewals on existing accounts are not affected.
9. **Missing expiry monitoring** - for in-use certificates, check for a
   CloudWatch alarm on the ACM `DaysToExpiry` metric
   (`AWS/CertificateManager`, dimension `CertificateArn`) via
   `cloudwatch:DescribeAlarmsForMetric`. Flag certificates with no alarm. Load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the recommended alarm and EventBridge settings.
10. **Stale endpoint after renewal** - if a certificate was renewed or
   re-issued but a dependent endpoint still serves the old certificate,
   confirm the resource references the new certificate ARN and that the
   distribution/load balancer has finished deploying.
11. **ACM Private CA** - using the Step 1 results, assess each CA by its status,
   by its revocation configuration (general-purpose CAs only), and by the ACM
   certificates issued from it, matched with the `CertificateAuthorityArn` that
   `DescribeCertificate` returns. A CA problem affects every certificate it
   issued. Report `DISABLED`, `PENDING_CERTIFICATE`, and `CREATING` CAs as billed
   but not issuing, and `FAILED` CAs as cleanup. Never state that a CA has no
   dependent certificates: Private CA has no API that lists the certificates a CA
   issued, so only ACM-registered certificates are visible. When running this
   check, load
   [references/acm-detection-details.md](references/acm-detection-details.md).
12. **Legacy IAM server certificates** - from the Step 1 IAM results, flag
   expired certificates, certificates expiring within 90 days, and any IAM
   server certificate at all. They never auto-renew and IAM is not shown in the
   ACM console, so every IAM server certificate is a finding. Its stated action
   MUST be "migrate to an ACM certificate" where ACM is supported in the Region
   that uses it. In a Region ACM does not support, IAM is the required store:
   say so, and recommend expiry monitoring and a planned re-upload instead.
   Never skip or defer the IAM check, and include it even when the request is
   phrased narrowly (for example "what is stuck or will not renew").
   Load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the procedure.
13. **Certificate hygiene** - flag duplicate certificates for the same domain
   (often a failed renewal with a replacement issued alongside), and Regions
   whose certificate count is close to the ACM certificate quota. Load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the rules.
14. **DV/OV/EV classification of imported certificates** - ACM does not expose
   a validation level, so derive it from the certificate `Subject` using the
   rule in
   [references/acm-detection-details.md](references/acm-detection-details.md).
   Record the DV, OV, and EV counts; Step 5 and
   [references/cab-forum-readiness.md](references/cab-forum-readiness.md) use
   them to choose the migration path.
15. **ACME network path (AWS PrivateLink)** - only in Regions where Step 1
   found ACME-origin certificates. Using the Step 1 VPC endpoint results, report
   whether ACME issuance runs over PrivateLink and whether that path is healthy.
   No PrivateLink endpoint is an INFO advisory, not a defect, because ACME works
   over the public path. If an endpoint exists, check its state, private DNS
   setting, endpoint policy, and security group. The scope is Regions with ACME
   certificates, so no extra ACME calls are needed. Load
   [references/acm-detection-details.md](references/acm-detection-details.md)
   for the rules.

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
- For every RED and AMBER finding: why it matters, the exact action, and the
  complications to check before acting (for example an empty `InUseBy` that is
  not actually unused). Use the finding detail format and the complications
  table in the report-format reference.

Reporting rules:

- Compute every number (days to expiry, counts, any cost estimate) in code or
  by explicit arithmetic on retrieved values - never estimate figures. Call the
  datetime tool at most once, for the current time, then compute every
  days-to-expiry value by explicit arithmetic on the retrieved `NotAfter` values
  in one pass, not one certificate at a time.
- Cover every source collected in Step 1 in the report, even when a source is
  empty or the question was about something else: ACM certificates per Region,
  Private CAs, and IAM server certificates. Write "none found" for an empty
  source. A question about stuck or non-renewing certificates still covers IAM
  server certificates, which never auto-renew. Every IAM server certificate
  finding must include the action "migrate to an ACM certificate" (or, in a
  Region ACM does not support, the monitor-and-re-upload action from check 12),
  even when the certificate is not near expiry.
- Name a Private CA by its subject common name, not only its ARN. For a CA in
  `PENDING_CERTIFICATE`, `CREATING`, or `DISABLED`, say it is billed but cannot
  issue certificates. Never say the CA has no dependent certificates. When no
  ACM-registered certificate references the CA, write this sentence in full: "No
  ACM-registered certificate references this CA. Certificates issued directly
  through the Private CA API are not visible, so this does not show that the CA
  has issued nothing."
- For a certificate in `PENDING_VALIDATION`, state the action: the DNS validation
  (CNAME) record must be added.
- List every enabled Region that was not swept under "Regions not swept". If any
  were skipped, never call the inventory account-wide.
- Rate each finding once: exactly one of RED, AMBER, GREEN, or INFO. Never write
  a combined label such as "RED/AMBER"; resolve it with the thresholds reference
  (for example, lower one level for a certificate that is not in use).
- Self-check before sending: count the rows of each risk level in the findings
  table, and make the executive summary counts match those row counts exactly.
  If they differ, fix the summary, not the table.
- Follow-up answers in the same conversation follow the same rules: every IAM
  server certificate mentioned carries the action "migrate to an ACM
  certificate", and any total is counted from the listed items, not estimated.
- Include an AI-generated-content disclaimer on the report.
- If this report may be shared outside the operations team, keep it factual
  and free of internal-only identifiers.

- [ ] **Step 5: CA/B Readiness Snapshot (always run)**

After the findings report, ALWAYS append a brief CA/B readiness snapshot
using the Phase 1 inventory. The CA/B Forum limits cover publicly trusted
certificates only. Count a certificate (in use or not) only when it is:
- ACM-issued public (`AMAZON_ISSUED`, including ACME) and issued, or
- `IMPORTED` or an IAM server certificate whose issuer differs from its subject.
  The API cannot prove the issuer is a public CA, so add "verify the issuer is a
  public CA" for these.

A certificate is self-signed when its Issuer CommonName and Organization match
its Subject CommonName and Organization. Classify each counted certificate by
how it renews (the snapshot and the full assessment use the same rules):
- GREEN: ACM-managed with DNS validation, or ACME-issued and not expired.
- AMBER: ACM-managed with email validation, or an exportable certificate
  without the Workload Credentials Provider configured.
- RED: imported or IAM certificates from a public CA, and ACME-issued
  certificates that have expired (the client stopped renewing).

Do not count, and show each group with its count: "not issued" (`FAILED`,
`VALIDATION_TIMED_OUT`, `PENDING_VALIDATION`), "self-signed", and "private"
(`PRIVATE` certificates from a Private CA).

Present as a 3-line summary:
- GREEN count, AMBER count, RED count
- One-sentence risk statement (e.g. "X of Y active certificates will require
  manual rotation at 47-day intervals by March 2029 without remediation.")
- Offer: "For detailed migration paths and automation options, ask for the
  full CA/B Forum readiness assessment."
Make this offer the last line of the report, so an agent that summarizes the
report can carry it forward, and end the user-facing answer with it as well.

- [ ] **Step 6 (on request): Full CA/B Forum readiness**

If the operator asks for the full assessment (migration paths, gap analysis,
automation options, cost), load
[references/cab-forum-readiness.md](references/cab-forum-readiness.md), which
uses the Phase 1 inventory as its input.

## Required IAM permissions

Read-only. See `README.md` for the full list. Core actions:
`acm:SearchCertificates`, `acm:DescribeCertificate`, `acm:DescribeAcmeEndpoint`,
`acm:ListAcmeAccounts`, `acm:ListAcmeExternalAccountBindings` (only when
ACME-origin certificates exist), `acm-pca:ListCertificateAuthorities`, `acm-pca:DescribeCertificateAuthority`,
`cloudwatch:DescribeAlarmsForMetric`, `iam:ListServerCertificates`,
`iam:GetServerCertificate`, `ec2:DescribeRegions` (to sweep every enabled
Region), `ec2:DescribeVpcEndpoints` and
`ec2:DescribeSecurityGroups` (only in Regions with ACME certificates), and, for org-wide scans,
`organizations:ListAccounts`.
