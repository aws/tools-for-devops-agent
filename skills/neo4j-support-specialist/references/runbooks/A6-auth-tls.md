# A6: Authentication, SSO and TLS

**Problem it solves:** TLS mistakes stop the server at startup with the cause in container output. Authentication
failures appear there only as a generic `unauthorized` warning; the reason (token claims, LDAP certificate path,
client IP) is in security.log or debug.log, and client-side TLS failures are in client logs.

**What to read.** SSL policies: `dbms.ssl.policy.<bolt|https|cluster|backup>.enabled`, `.base_directory`,
`.private_key`, `.public_certificate`, `.trusted_dir`, `.client_auth`, `.ciphers`, `.tls_versions`; Bolt
`server.bolt.tls_level`. The Helm chart mounts certificates from the Secrets named in `ssl.<policy>` values into
`/var/lib/neo4j/certificates/<policy>` (secret names only are visible; never the contents). Authentication:
`dbms.security.authentication_providers`, `dbms.security.authorization_providers`, `dbms.security.oidc.<provider>.*`,
`dbms.security.ldap.*`, and proxy or trust-store flags in `server.jvm.additional`.

**Log formats.** A failed login writes `WARN [bolt-<n>] The client is unauthorized due to authentication failure.`
to container output and `ERROR Exception thrown, 42NFF: The client is unauthorized due to authentication failure.` to
the default text security.log, neither with user, reason or client address. With security.log switched to the JSON
layout, the entry adds `failed to log in: invalid principal or credentials`, the user and
`client/<ip>:<port>`.

## A6.1 Server fails to start with TLS enabled

**Signature:** startup failure, exit 1, with `CertificateParsingException: signed fields invalid` or `Neither RSA, DSA
nor EC worked` in container output, on the same startup path as the SSL policy error in A6.2.

**Cause:** The certificate file isn't a plain PEM certificate (for example a key or bundle in the wrong order), or the
private key is in a format Neo4j can't read (encrypted, or an unexpected header).

**Fix (operator):** Use a PEM `public.crt` with the server certificate first, and an unencrypted PKCS#8 `private.key`
(`openssl pkcs8 -topk8 -nocrypt -in key.pem -out private.key`). Check both with `openssl x509 -in public.crt -noout -text`
and `openssl pkey -in private.key -noout`.

## A6.2 SSL policy misconfiguration

**Signature:** container output `Base directory '/ssl/bolt' for SSL policy with name 'bolt' does not exist.`,
exit 1. Other variants name a missing `private.key`, `public.crt` or `trusted` directory.

**Cause:** An enabled policy points at a path that isn't mounted, or files have other names than the policy expects
(`private.key`, `public.crt` by default). On Kubernetes this is usually a Secret not mounted, or mounted at a different
path than `base_directory`.

**Check:** `dbms.ssl.policy.<name>.enabled` and `.base_directory`; volume mounts for that path; Helm `ssl.<name>` Secret
names; recent changes to them.

**Fix (operator):** Mount the certificates at the policy's base directory (the Helm `ssl.<policy>` values do this), or
point `base_directory` at the mount. Files must be readable by uid 7474.

## A6.3 Client TLS handshake or trust failure

**Signature:** client `SSLHandshakeException`, `PKIX path building failed`, `unable to find valid certification path to requested target`.

**Cause:** The client doesn't trust the server's CA (private CA, self-signed certificate) or a corporate proxy
re-signs traffic. Where TLS ends matters: on the NLB (ACM certificate) or on Neo4j (its own certificate).

**Check:** NLB listener protocol (TLS or TCP) and ACM certificate status and expiry; client URI scheme (`+s` verifies the
CA, `+ssc` accepts any certificate).

**Fix (operator):** Add the CA to the client trust store, or use a certificate from a CA the clients trust. Use `+ssc`
only for testing.

## A6.4 Cipher mismatch

**Signature:** handshake failure (`no cipher suites in common`, `handshake_failure`) right after the SSL policy changed.

**Fix (operator):** Allow at least one cipher and TLS version the clients support, or leave `ciphers` unset to use the
JVM defaults.

## A6.5 LDAP over TLS certificate path

**Signature:** LDAP logins fail with `SunCertPathBuilderException: unable to find valid certification path to
requested target`. The LDAP errors are in security.log or debug.log.

**Cause:** The JVM doesn't trust the LDAP server certificate.

**Fix (operator):** Import the LDAP CA into a trust store and pass it with `-Djavax.net.ssl.trustStore=<path>` (and
password) in `server.jvm.additional`.

## A6.6 SSO token rejected

**Signature:** the IdP login succeeds, then Neo4j rejects the token (Browser: `SSO token was not accepted by neo4j`).
Container output has only `The client is unauthorized due to authentication failure.`; token validation detail is in
security.log or debug.log.

**Cause:** The token doesn't match the provider configuration: wrong `audience`, an `issuer` that differs from the
token's `iss`, the username or groups claim missing (`claims.username`, `claims.groups`), the wrong token type
(`token_type_principal`, `token_type_authentication`), an expired token, or Neo4j couldn't reach the provider's keys.

**Check:** `dbms.security.oidc.<provider>.well_known_discovery_uri`, `.audience`, `.issuer`, `.claims.username`,
`.claims.groups`, `.token_type_principal`; `dbms.security.authentication_providers` includes `oidc-<provider>`.

**Fix (operator):** Decode a sample token (header and payload only) and align `aud`, `iss` and the claim names with the
settings.

## A6.7 SSO discovery through a proxy

**Symptom:** SSO fails for everyone; debug.log shows errors fetching the discovery document or keys.

**Fix (operator):** Add `-Dhttps.proxyHost=<host> -Dhttps.proxyPort=<port>` (and `-Dhttp.nonProxyHosts` for internal
addresses) to `server.jvm.additional`, or allow direct egress to the IdP.

## A6.8 SSO users have no permissions

**Symptom:** SSO login works but users can't read or write; `Permission denied` or empty results.

**Cause:** No `claims.groups`, or no `authorization.group_to_role_mapping` entry for the user's groups, so the user
gets no roles beyond `PUBLIC`.

**Fix (operator):** Set `dbms.security.oidc.<provider>.claims.groups` and
`dbms.security.oidc.<provider>.authorization.group_to_role_mapping`, and include `oidc-<provider>` in
`dbms.security.authorization_providers`.

## A6.9 Identify client IPs

**Symptom:** a question of which client is failing logins or sending requests. Only security.log in the JSON layout
has the client address for failed logins; container output and the default text security.log don't. query.log has
`client/<ip>:<port>` for queries.

**Fix (operator):** Switch the security log appender in `server-logs.xml` to the JSON layout, or read client addresses
from query.log.
