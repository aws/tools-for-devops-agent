# ACM Findings Report Format Reference

Use this layout for the report produced in SKILL.md Step 4.

## 1. Executive summary

One short paragraph:

- Overall posture: RED / AMBER / GREEN (see rollup in `acm-thresholds.md`).
- Count of certificates scanned, and counts by risk level.
- The single most urgent item and its deadline.
- Scope covered (accounts, regions), and any accounts skipped
  (`AccessDenied`, throttled).
- Sources covered: ACM certificates per Region, Private CAs, and IAM server
  certificates, each with a count ("none found" when empty).

## 2. Prioritized findings table

Sort by risk (RED first), then in-use before unused, then ascending days to
expiry.

| Account | Region | Certificate / Domain | Type | Status | Days to expiry | In use | Risk | Recommendation |
|---|---|---|---|---|---|---|---|---|
| 1111... | us-east-1 | www.example.com | AMAZON_ISSUED | ISSUED | 9 | Yes | RED | Renewal FAILED - fix DNS CNAME, then re-validate |
| 4444... | eu-west-1 | api.example.com | IMPORTED | ISSUED | 27 | Yes | RED | Imported cert cannot auto-renew - migrate to ACM-managed |

Include the certificate ARN in a detail section or as a tooltip/footnote
rather than in the main row, to keep the table readable.

## 3. Remediation list

Ordered by priority. For each item: what to do, which certificate/account it
applies to, and the AWS action or console path involved. Example ordering:

1. Certificates expired or expiring within 14 days and in use.
2. Failed or stuck renewals (fix validation, then renewal proceeds).
3. Imported in-use certificates without a renewal path.
4. Weak-key certificates.
5. In-use certificates missing a `DaysToExpiry` alarm.
6. Unused certificates to clean up.
7. Legacy IAM server certificates and disabled Private CAs to migrate or clean up.

## 4. Finding detail (RED and AMBER findings)

Give every RED and AMBER finding three parts, directly under the table or in the
remediation list:

- **Why** - the risk if nothing is done.
- **Action** - exactly what to do, with the AWS action or console path. For DNS
  validation, show the exact CNAME name and value from `DomainValidationOptions`
  (`ResourceRecord`); do not just say "fix DNS".
- **Complications to check** - what could go wrong if the operator acts without
  checking first. Use the table below where it applies.

| Finding | Complication to flag |
|---|---|
| Delete an expired or disabled Private CA | AWS does not check that the certificates the CA issued have expired before it deletes the CA. Keep the CA disabled until all of them have expired. If it must go earlier, also revoke the CA certificate. Only ACM-registered certificates are visible to this review; an audit report (operator-generated, ACTIVE or DISABLED CAs only) lists everything the CA issued. A CA deleted from `PENDING_CERTIFICATE` or `DISABLED` can be restored for 7 to 30 days, and restoring bills the gap. A CA deleted while `CREATING` or `FAILED` cannot be restored. |
| Remove an expired certificate from a distribution or load balancer | Confirm which certificate is actually attached in the listener or distribution configuration. A newer certificate may already be serving. |
| Delete an unused certificate | `InUseBy` may not be populated for every integration (for example API Gateway custom domains or Elastic Beanstalk). Check the domain against active DNS and consumers first. |
| Migrate imported OV or EV to ACM | ACM issues DV only. Check contractual, compliance, and regulatory requirements before recommending. |
| Fix DNS validation records | DNS changes affect live validation. Give the exact record expected. |
| Switch email validation to DNS | The certificate ARN stays the same. The CNAME records must be added within the validation window. |
| Migrate an IAM server certificate to ACM | Find and update every listener or distribution that references the IAM certificate before removing it. |
| Remove a duplicate certificate | Confirm which duplicate is in use before deleting the other. |
| Create an ACME interface endpoint (PrivateLink) | It must be in the same Region as the ACME endpoint. Standard PrivateLink charges apply. Check which Availability Zones the service supports before choosing subnets. |
| Enable private DNS on the ACME VPC endpoint | It changes how clients in that VPC resolve the existing ACME directory URL. Existing client configuration does not need to change, but test with one client first. |
| Fix the ACME VPC endpoint policy | The policy must cover both the ACME endpoint resource and `certificate/*` (for `acm:RequestCertificate` and `acm:RevokeCertificate`), or issuance fails at finalize. |
| GovCloud or China partition findings | Separate compliance requirements apply. Do not recommend deletion without that context. |

## 5. Disclaimer

End the report with an AI-generated-content disclaimer, for example:

> This report was generated with AI assistance from ACM and CloudWatch data at
> the time of the scan. Validate findings against the live environment before
> acting.

## Formatting notes

- Every number must be computed from retrieved values, never estimated.
- If an interactive HTML dashboard is requested, mirror the same sections and
  the same risk color coding (RED / AMBER / GREEN).
