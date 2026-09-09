# ACM detection details

Detailed enumerations and sub-procedures for the certificate inventory and
detection steps. Load this when running Step 1 (inventory) and Step 2 check 7
(ACME renewal-pipeline verification).

## ListCertificates filter completeness (Step 1)

`acm:ListCertificates` silently drops certificates unless the filter is opened
up on two independent axes. Always set both.

### Key-pair origins

Include every certificate key-pair origin via the `CertificateKeyPairOrigins`
parameter, which is a separate top-level filter, not inside `Includes`:

- `AWS_MANAGED`
- `CUSTOMER_PROVIDED`
- `ACME`

By default, `ListCertificates` excludes ACME-issued certificates.

### Key types

Include all key types in the `Includes.keyTypes` filter:

- `RSA_1024`
- `RSA_2048`
- `RSA_3072`
- `RSA_4096`
- `EC_prime256v1`
- `EC_secp384r1`
- `EC_secp521r1`

By default, only `RSA_1024` and `RSA_2048` are returned. ACME certs often use
ECDSA (`EC_prime256v1`) and are silently excluded without this.

Always include every known key type and every known key-pair origin to avoid
missing certificates. Check current ACM docs for any newly added values (for
example post-quantum algorithms).

## ACME renewal-pipeline sub-checks (Step 2, check 7)

When ACME-issued certificates are found, run these additional sub-checks to
verify the renewal pipeline is healthy:

- **7a. ACME endpoint health** - retrieve the ACME endpoint that issued the
  cert (endpoint ID is in the cert metadata or `DescribeAcmeEndpoint`). Confirm
  it is enabled/active. If disabled or deleted, flag RED - renewals will fail.
- **7b. EAB status** - check if the External Account Binding credential used to
  register the ACME account is still valid (not revoked, not expired). Use
  `ListAcmeExternalAccountBindings` for the endpoint. If the EAB is revoked or
  expired, flag AMBER (existing accounts still work, but no new registrations
  possible - note: revoking an EAB does NOT affect already-registered accounts).
- **7c. ACME account status** - check if the registered ACME account is active
  or revoked. Use `ListAcmeAccounts` or `DescribeAcmeAccount`. If revoked, flag
  RED - this is irreversible, the client can no longer issue or renew certs.

If the endpoint is disabled OR the account is revoked, override the cert
classification to RED regardless of current expiry date - the renewal pipeline
is broken and the cert will silently expire without renewal.
