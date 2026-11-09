# ACM Thresholds and Risk Levels Reference

Use these thresholds when detecting issues (SKILL.md Step 2) and when
classifying findings (SKILL.md Step 3). Values reflect common operational
best practice; adjust to a customer's own policy when one is documented.

## Expiry thresholds (in-use certificates)

| Days to expiry (`NotAfter` - now) | Risk |
|---|---|
| Already expired | RED |
| <= 14 days | RED |
| 15 - 30 days | AMBER |
| 31 - 45 days | AMBER |
| > 45 days | GREEN |

For certificates **not** in use (`InUseBy` empty), lower the risk by one level
(RED -> AMBER, AMBER -> GREEN) because there is no live traffic impact, but
still list them as cleanup candidates.

## Renewal status

| `RenewalSummary.RenewalStatus` | Risk | Notes |
|---|---|---|
| `FAILED` | RED | Capture `RenewalStatusReason`. |
| `PENDING_VALIDATION` | RED (in use) / AMBER | Domain validation is blocking renewal. |
| `PENDING_AUTO_RENEWAL` (progressing) | GREEN | Normal state ~60 days out. |
| `SUCCESS` | GREEN | |

## Certificate type

| Condition | Risk | Recommendation |
|---|---|---|
| `IMPORTED` and in use | AMBER (RED if <= 30 days) | ACM cannot auto-renew imported certs. Move to an ACM-managed (`AMAZON_ISSUED`) certificate where possible, or ensure an external renewal + re-import process exists. |
| `AMAZON_ISSUED` with DNS validation | GREEN | Eligible for managed renewal. |
| `AMAZON_ISSUED` with email validation | AMBER | Email validation does not support fully automated renewal. Recommend switching to DNS validation. |

## Key algorithm

APIs can spell key algorithms differently (`RSA_2048` or `RSA-2048`). Treat the
underscore and hyphen forms as the same value.

| `KeyAlgorithm` | Risk |
|---|---|
| `RSA_1024` | RED (deprecated) |
| `RSA_2048`, `EC_prime256v1`, `EC_secp384r1` and stronger | GREEN |

## Monitoring

| Condition | Risk |
|---|---|
| In-use certificate with **no** CloudWatch alarm on `DaysToExpiry` | AMBER |
| In-use certificate with a `DaysToExpiry` alarm | GREEN |

The ACM expiry metric is `DaysToExpiry` in the `AWS/CertificateManager`
namespace, dimension `CertificateArn`.

## ACM Private CA

| Condition | Risk |
|---|---|
| CA `EXPIRED` with ACM certificates it issued still in use | RED |
| CA `DISABLED` with ACM certificates it issued still in use | AMBER (RED if one has a failed renewal with reason `PCA_INVALID_STATE`) |
| CA expiring within 90 days | AMBER |
| CA healthy | GREEN |

## Certificate status

| Condition | Risk |
|---|---|
| `FAILED` or `VALIDATION_TIMED_OUT` | RED |
| `PENDING_VALIDATION` for more than 24 hours | AMBER (RED if in use) |

## Legacy IAM server certificates

| Condition | Risk | Recommendation |
|---|---|---|
| Expired | RED | Replace; confirm what still references it. |
| Expires within 90 days | AMBER | Migrate to ACM before expiry. |
| Any IAM server certificate | AMBER | IAM certificates never auto-renew. Migrate to ACM. |

## Hygiene

| Condition | Risk |
|---|---|
| Duplicate certificates for the same domain where one is failed, expired, pending, or unused | AMBER |
| Region at 80 percent or more of the default quota of pending and issued certificates (imported and non-imported counted separately; actual quota not read) | AMBER |

## Private CA additions

| Condition | Risk |
|---|---|
| CA status `FAILED` | INFO (cleanup, not billed, cannot be recovered) |
| CA `DISABLED` with no ACM certificate from it visible | INFO (billed, may be mid-retirement; certificates issued directly through the Private CA API are not visible) |
| CA `PENDING_CERTIFICATE` or `CREATING` | INFO (billed, not issuing; report age, no fixed threshold) |
| General-purpose CA with no CRL or OCSP revocation configured | AMBER (short-lived-certificate CAs are exempt) |

## ACME network path (PrivateLink)

Applies only in Regions that have ACME-issued certificates.

| Condition | Risk |
|---|---|
| No `acm-acme-enroll` interface endpoint | INFO (advisory, public path works) |
| Endpoint present but not available | AMBER |
| Endpoint present with private DNS disabled | AMBER |
| Custom endpoint policy missing the certificate resource statement | AMBER |
| No security group rule allows inbound 443 | AMBER |
| Endpoint in a single subnet or Availability Zone | INFO |

## Overall posture rollup

- **RED** if any RED finding exists.
- **AMBER** if no RED but one or more AMBER findings.
- **GREEN** only if every finding is GREEN.
