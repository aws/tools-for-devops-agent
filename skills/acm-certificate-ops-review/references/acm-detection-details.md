# ACM detection details

Detailed enumerations and sub-procedures for the certificate inventory and
detection steps. Load this when running Step 1 (inventory) and Step 2 checks 4
(email validation), 6 (weak keys), 8 (ACME renewal pipeline), 9 (expiry
monitoring), and 11 to 15 (Private CA, IAM server certificates, hygiene,
DV/OV/EV, ACME PrivateLink).

## SearchCertificates (Step 1, primary)

`acm:SearchCertificates` is the primary inventory call. With no
`FilterStatement` it returns every certificate in the Region, including
ACME-origin and ECDSA certificates, with no filter parameters. Page size is up
to 500; paginate with `NextToken`. In a test account the unfiltered call returned
the ACME ECDSA certificate.

Each result has `X509Attributes` (`Subject`, `Issuer`, subject alternative
names, `KeyAlgorithm`, `NotBefore`, `NotAfter`, `SerialNumber`) and
`CertificateMetadata.AcmCertificateMetadata` (`Status`, `Type`, `InUse`,
`RenewalEligibility`, `ValidationMethod`, `CertificateKeyPairOrigin`,
`AcmeEndpointArn`, `AcmeAccountId`, `Exported`, `CreatedAt`, `IssuedAt`,
`ImportedAt`). It does not return which resources use the certificate, the
domain validation records, or a renewal failure reason; use
`DescribeCertificate` for those.

### ACME cross-check

The ACM user guide says ACME certificates are returned only when the key-pair
origin filter is set to `ACME`. In a test account the unfiltered call returned the
ACME certificate anyway, so the unfiltered call stays primary. When it returns no
ACME-origin certificate in any Region, cross-check each Region with this
`FilterStatement` before reporting that none exist:

```
{"Filter": {"AcmCertificateMetadataFilter": {"CertificateKeyPairOrigin": "ACME"}}}
```

If this returns certificates the unfiltered call missed, use them and note the
discrepancy in the report.

## Email-validated certificates (Step 2, check 4)

Email validation is being deprecated under the CA/B Forum rules. ACM stops
issuing email-validated certificates on March 31, 2027 and stops renewing them
on September 30, 2027. Verify these dates against current ACM documentation
before quoting them.

- Recommend switching to DNS validation now with `UpdateCertificateOptions`. The
  certificate ARN stays the same, so load balancers, CI/CD, and service
  integrations are not disrupted.
- The CNAME records must be added within 72 hours of starting the switch.
- Monitor progress with `ListCertificateDomainValidations`.

## Weak or legacy keys (Step 2, check 6)

- `RSA_1024`: recommend at least `RSA_2048`, or ECDSA P-256 for better
  performance and a smaller key.
- `RSA_2048` is acceptable today. ECDSA P-256 (`EC_prime256v1`) or P-384
  (`EC_secp384r1`) is the modern best practice: faster TLS handshakes, more
  security per bit, and the default for ACME clients.
- Verify the key types ACM supports at runtime from the ACM docs or API. If new
  algorithms are added (for example post-quantum) and offer stronger security,
  include them. Do not limit recommendations to a fixed list.

## Expiry monitoring (Step 2, check 9)

Recommend both options where possible:

- **CloudWatch `DaysToExpiry` alarm** (per certificate) - works for every
  certificate type, including imported and ACME. Threshold at most 30 days,
  period 1 day, statistic Minimum.
- **EventBridge `ACM Certificate Approaching Expiration`** (no per-certificate
  setup) - fires daily from 30 days before expiry for public certificates.
  `ACM Certificate Expired` events are not sent for imported certificates, so a
  CloudWatch alarm is the only safety net for them.

## ACME renewal-pipeline sub-checks (Step 2, check 8)

When ACME-issued certificates are found, run these additional sub-checks to
verify the renewal pipeline is healthy:

- **7a. ACME endpoint health** - retrieve the ACME endpoint that issued the
  cert (the certificate's `AcmeEndpointArn`, then `DescribeAcmeEndpoint`, which returns its `Status`). Confirm
  it is enabled/active. If disabled or deleted, flag RED - renewals will fail.
- **7b. EAB status** - check if the External Account Binding credential used to
  register the ACME account is still valid (not revoked, not expired). Use
  `ListAcmeExternalAccountBindings` for the endpoint; each binding has `RevokedAt`,
  `ExpiresAt`, and `LastUsedAt`. If the EAB is revoked or
  expired, flag AMBER (existing accounts still work, but no new registrations
  possible - note: revoking an EAB does NOT affect already-registered accounts).
- **7c. ACME account status** - check if the registered ACME account is active
  or revoked. Prefer `ListAcmeAccounts`, which returns each account's `AccountUrl` and `Status`.
  `DescribeAcmeAccount` takes `AcmeEndpointArn` and `AccountUrl`, not an account
  ID, so passing an `AcmeAccountId` fails parameter validation. These calls return
  account contact addresses; never copy them into the report. If revoked, flag
  RED - this is irreversible, the client can no longer issue or renew certs.

If the endpoint is disabled OR the account is revoked, override the cert
classification to RED regardless of current expiry date - the renewal pipeline
is broken and the cert will silently expire without renewal.

If a sub-check call is cancelled with a message such as "Cancelled mutative
operation ... requires an operator approval", the DevOps Agent platform guardrail
has classified that read-only ACME API as mutative. This is a platform
restriction, not an IAM problem. Do not retry the call and do not invent a
result. Record the sub-check as "Unable to verify - platform guardrail", do not
classify it RED or AMBER on the missing data, and say in the report that the
renewal pipeline could not be confirmed.

## API call format

Every `use_aws` call needs `service_name` and `operation_name`, plus
`aws_region` and the operation parameters. Omitting `service_name` fails
validation and wastes the call. Primary inventory call:

```
service_name: acm
operation_name: search_certificates
aws_region: us-east-1
parameters:
  MaxResults: 500
```

ACME cross-check call (only when no ACME-origin certificate was found):

```
service_name: acm
operation_name: search_certificates
aws_region: us-east-1
parameters:
  MaxResults: 500
  FilterStatement:
    Filter:
      AcmCertificateMetadataFilter:
        CertificateKeyPairOrigin: ACME
```

## ACM Private CA assessment (Step 2, check 11)

Sources: `acm-pca:ListCertificateAuthorities` and `DescribeCertificateAuthority`
for the CAs, and `DescribeCertificate` for ACM certificates of type `PRIVATE`.
`DescribeCertificate` returns `CertificateAuthorityArn`, which is how a
certificate is matched to its CA.

### What each CA status allows

From the AWS Private CA user guide (CA status):

| Status | Issues certificates | Revokes certificates | Audit report | Billed |
|---|---|---|---|---|
| `CREATING` | No | No | No | Yes |
| `PENDING_CERTIFICATE` | No | No | No | Yes |
| `ACTIVE` | Yes | Yes | Yes | Yes |
| `DISABLED` | No | Yes | Yes | Yes |
| `EXPIRED` | No | No | No | Yes |
| `FAILED` | n/a | n/a | n/a | No |

A `DISABLED` CA still answers OCSP and CRL requests. A `FAILED` CA cannot be
recovered. The list and describe calls report `EXPIRED` whenever the CA
certificate has expired, even if the CA was `ACTIVE` or `DISABLED` before, so an
`EXPIRED` CA may also have been disabled. CA certificates are not renewed
automatically. `ListCertificateAuthorities` returns the account's own CAs by
default and at most 100 per page, so paginate with `NextToken`.

ACM renews a private certificate by calling `IssueCertificate` on the CA on the
customer's behalf (the audit report shows these requests with
`requestedByServicePrincipal` set to `acm.amazonaws.com`). A CA that cannot issue
therefore cannot renew. AWS documents `PCA_INVALID_STATE` as the renewal failure
reason when the CA is not in an active state (AWS re:Post knowledge center
article on private certificate renewal failures).

### Rules

- **Matching** - compare each private certificate's `CertificateAuthorityArn`
  with the CA list. An ARN that is not in the list belongs to a CA in another
  account (shared CAs are not listed by default). Report "issuing CA in another
  account, not assessed".
- **`EXPIRED` CA with ACM certificates it issued still in use** - RED. It can
  neither issue nor revoke.
- **`DISABLED` CA with ACM certificates it issued still in use** - AMBER, because
  those certificates cannot be renewed from it. RED if any of them has a failed
  renewal with `RenewalStatusReason` `PCA_INVALID_STATE`.
- **`DISABLED` CA with no ACM certificate from it visible** - INFO. It is still
  billed and may be part of a planned retirement. Report how long it has been in
  that state using `LastStateChangeAt`. Do not call it unused: certificates
  issued straight through the Private CA API are not visible.
- **`PENDING_CERTIFICATE` or `CREATING`** - INFO. The CA is billed but cannot
  issue. Report its age from `CreatedAt` and ask whether activation is still
  planned. There is no documented age that makes a CA "stuck", so do not invent
  a threshold.
- **`FAILED`** - INFO, cleanup only. Not billed; recommend deleting it.
- **CA certificate expiring** - use `NotAfter` from `DescribeCertificateAuthority`
  and the CA expiry threshold in `acm-thresholds.md`.
- **Revocation** - `RevocationConfiguration` with neither CRL nor OCSP enabled is
  AMBER, because issued certificates cannot be revoked in a way clients can
  check. Apply this only when `UsageMode` is `GENERAL_PURPOSE`. A
  `SHORT_LIVED_CERTIFICATE` CA issues certificates valid for at most seven days
  and may omit revocation by design, so do not flag it.
- Compute any cost figure in code from current AWS Private CA pricing; do not
  quote a remembered number.

### Which certificates did this CA issue?

No `acm-pca` action lists the certificates a CA issued. `GetCertificate` needs a
certificate ARN you already have. The documented way to list everything a CA
issued or revoked, including certificates that are not in ACM, is the audit
report.

The skill is read-only and must not generate one. `CreateCertificateAuthorityAuditReport`
writes a report file into an S3 bucket. Tell the operator how to do it instead:

- It works only while the CA is `ACTIVE` or `DISABLED`, not `EXPIRED`,
  `PENDING_CERTIFICATE`, or `CREATING`.
- One report can be generated every 30 minutes. It is not supported for a CA that
  has issued more than 100 million certificates.
- The S3 bucket needs a policy that lets AWS Private CA write to it, and it must
  not use S3 Object Lock. Reports are written to `audit-report/CA_ID/UUID.json`
  or `.csv`.
- It is a point-in-time snapshot with certificate ARN, serial, subject, validity
  dates, issue time, revocation time and reason, and the requesting service
  principal. It has no subject alternative names; `GetCertificate` with the
  certificate ARN returns the full certificate, but only while the CA still
  exists.
- CloudTrail is the complementary source: it records each API call and signing
  operation as it happens.

### Retiring or deleting a CA

AWS's guidance, for remediation text:

1. Create the replacement CA.
2. When it is in production, disable the old CA. Do not delete it yet.
3. Keep the old CA disabled until every certificate it issued has expired.
4. Delete the old CA.

AWS does not check that the issued certificates have expired before it processes
a delete request. If a CA must be deleted early, AWS recommends also revoking the
CA certificate, so the parent CA lists it in its CRL and clients stop trusting
it. An expired certificate, including an expired CA certificate, cannot be
revoked. An `ACTIVE` CA must be disabled before it can be deleted. A CA can be
deleted in the `PENDING_CERTIFICATE`, `CREATING`, `EXPIRED`, `DISABLED`, or
`FAILED` state.

Restoration: a CA deleted from `PENDING_CERTIFICATE` or `DISABLED` can be
restored for 7 to 30 days (default 30). A CA deleted while `CREATING` or `FAILED`
cannot be restored. Restoring bills the time between deletion and restoration.
The guide's text and its console steps differ on `EXPIRED` CAs, so tell the
operator to read the restoration option shown in the console.

## Legacy IAM server certificates (Step 2, check 12)

Server certificates uploaded to IAM do not auto-renew and are not managed by
ACM.

- `iam:ListServerCertificates` once per account, then `iam:GetServerCertificate`
  for each result.
- Expired - RED. Expiring within 90 days - AMBER. Any other IAM server
  certificate - AMBER, with the recommendation to migrate to ACM.
- AWS recommends ACM in every Region ACM supports; in a Region ACM does not
  support, IAM is the required certificate store. IAM certificates are global and
  the IAM APIs do not show which Region uses them, so tell the operator to confirm
  the Region of the referencing load balancer before migrating. Check ACM Region
  support on the ACM endpoints page in the AWS General Reference; do not name
  Regions from memory.
- A certificate whose path starts with `/cloudfront/` is used by CloudFront,
  which takes ACM certificates from `us-east-1`, so migration always applies.
- Before recommending removal or migration, tell the operator to find which
  load balancer listeners or CloudFront distributions reference the certificate;
  they must be moved to the new certificate first.

## Certificate hygiene (Step 2, check 13)

- **Duplicates** - two or more certificates covering the same domain names where
  one is `FAILED`, `EXPIRED`, `PENDING_VALIDATION`, or not in use. This usually
  means a renewal failed and a replacement was issued alongside. AMBER; point at
  the one actually in use.
- **Quota proximity** - the ACM documentation lists a default of 2,500 ACM
  certificates and a separate default of 2,500 imported certificates per Region
  per account, and both are adjustable. Only certificates in the pending or
  issued state count, so expired certificates do not. Count `PENDING_VALIDATION`
  and `ISSUED` certificates per Region, imported and non-imported separately,
  and compare each with the default. 80 percent or more of a default - AMBER.
  State in the report that the account's actual quota was not read and may be
  higher. Confirm the current defaults in the ACM quotas documentation.

## DV/OV/EV classification of imported certificates (Step 2, check 14)

ACM-issued certificates are always DV. For `IMPORTED` certificates, derive the
level from the `Subject` field:

- **DV** - the subject contains only `CN=<domain>` with no organization fields.
- **OV** - the subject contains `O=<organization>` together with location
  fields such as `C=`, `ST=`, `L=`.
- **EV** - the OV fields plus `serialNumber=`, `businessCategory=`, or
  `jurisdictionC=`.

The CA/Browser Forum assigns an OID to each validation level in the certificate
policies extension: 2.23.140.1.2.1 for domain validated, 2.23.140.1.2.2 for
organization validated, and 2.23.140.1.1 for extended validation. A third level,
individual validated (2.23.140.1.2.3), exists for certificates that name a
person; a subject with `GivenName` or `Surname` and no `Organization` points to
it. The ACM inventory calls do not return the policy OIDs, so the subject text
is only a proxy. If the operator can supply the certificate PEM, the OID is
authoritative and overrides the subject-based result.

This is a heuristic on the subject text, so label the result "derived" in the
report. Report the DV, OV, and EV counts. DV certificates are migration
candidates to ACM-issued; OV and EV certificates cannot be reissued by ACM
(DV only) and need an automation or hybrid import strategy.

## ACME network path over AWS PrivateLink (Step 2, check 15)

ACM offers two independent interface endpoint services in each Region:

- `com.amazonaws.<region>.acm-acme-enroll` carries the ACME protocol itself:
  account registration, orders, finalize, download, and revocation from ACME
  clients. This is the one that matters for issuance and renewal.
- `com.amazonaws.<region>.acm-acme` carries the management operations a PKI
  administrator uses, such as creating ACME endpoints, domain validations, and
  EAB credentials. It has its own endpoint and policy. Never report a missing
  management endpoint as a finding.

Run this check only in Regions where Step 1 returned certificates with a
key-pair origin of `ACME`. Call `ec2:DescribeVpcEndpoints` with a `service-name`
filter of `com.amazonaws.<region>.acm-acme-enroll`. The scope is Regions with
ACME-origin certificates, because ACME availability by Region has not been
verified. A Region where an ACME endpoint exists but has issued no certificates
yet is therefore not covered, and the report should say so.

Rules:

- **No interface endpoint** - INFO. ACME issuance uses the public path. Suggest
  PrivateLink when ACME clients run in VPCs without internet egress, or when
  policy requires issuance traffic to stay on the AWS network. The API does not
  show where the clients run, so do not escalate. Standard PrivateLink charges
  apply; do not quote a price, and compute any estimate from current pricing.
- **Endpoint not in the available state** - AMBER.
- **Private DNS disabled** - AMBER. Private DNS is what makes the existing ACME
  directory URL resolve to the interface endpoint inside the VPC. Without it,
  clients cannot reach the ACME endpoint through the VPC endpoint: they fall back
  to the public path if the subnet has internet egress (so the traffic is not
  private), or fail if it does not.
- **Custom endpoint policy** - read it. A policy that restricts access to one
  ACME endpoint must cover both the ACME endpoint resource and the
  `certificate/*` resource with `acm:RequestCertificate` and
  `acm:RevokeCertificate`. If the certificate statement is missing, flag AMBER:
  issuance and renewal fail at the finalize step. Do not flag `"Action": "*"` on
  the ACME endpoint statement; AWS documents it as required there. The default
  policy (full access) is fine.
- **Security group** - the groups on the endpoint must allow inbound TCP 443
  from the client subnets. Use `ec2:DescribeSecurityGroups`. If no rule allows
  443 at all, flag AMBER. If a rule exists, state that client reachability could
  not be confirmed from the API.
- **One subnet or Availability Zone only** - INFO, resilience note.
- **Region** - interface endpoints do not support cross-Region requests, so an
  endpoint counts only in the Region of the ACME endpoint. ACM may not support
  the service in every Availability Zone; the console marks unsupported ones.

This check cannot confirm that clients actually use the endpoint. CloudTrail and
the ACME CloudWatch metrics show real activity.
