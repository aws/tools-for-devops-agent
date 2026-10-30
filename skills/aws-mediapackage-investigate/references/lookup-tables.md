# MediaPackage Deep Investigation: Lookup Tables

Metric catalogs, status tables and field tables relocated from SKILL.md so they load
only when the step that uses them runs. Each heading names the SKILL.md step and
subsection the table belongs to; the surrounding instructions stay in SKILL.md.

## Step 2B: v2 ingest health: v2 ingest metrics

| Metric | Statistic | Healthy | Unhealthy |
|---|---|---|---|
| IngressBytes | Sum | > 0 | = 0 (no content arriving) |
| IngressRequestCount (2xx) | Sum | > 0 | = 0 |
| IngressRequestCount (4xx) | Sum | = 0 | > 0 (auth or format errors) |
| IngressRequestCount (5xx) | Sum | = 0 | > 0 (server-side errors) |

## Step 3: Egress error analysis: v1 egress metrics

| Pattern | Meaning | Investigation |
|---|---|---|
| 4xx high, 2xx normal | Some requests failing (subset of players) | Check client auth, path patterns |
| 4xx high, 2xx zero | All requests failing | Endpoint config issue or content not available |
| 5xx any | Server-side packaging error | MP internal issue or resource exhaustion |
| 2xx dropping, no errors | Players stopping requests (not an MP issue) | Viewer behavior change |

## Step 4: CDN authorization diagnosis (v2 only): CDN authorization metrics

| StatusDetails value | Meaning |
|---|---|
| `HeaderSecretMatched` | Valid CDN auth header — request authorized |
| `MissingCdnAuthHeader` | No CDN auth header sent — request rejected |
| `HeaderSecretMismatched` | Header present but value doesn't match secret |
| `MissingCdnAuthConfiguration` | CDN auth not configured on this endpoint |
| `MissingCdnAuthHeaderAndConfiguration` | Neither header sent nor auth configured |
| `MissingCdnIdentifierSecretArns` | Policy exists but no secret ARNs specified |
| `MissingSecretsRoleArn` | Policy exists but no role ARN to read secrets |
| `SecretsManagerInvalidParameterError` | Secrets Manager parameter issue |
| `SecretsManagerInternalServiceError` | Secrets Manager internal failure |
| `SecretsManagerThrottlingError` | Secrets Manager rate limit hit |
| `MediaPackageSecretsValidationError` | Secret value failed MP validation |
| `OtherErrors` | Unclassified CDN auth error |

## Step 5: ForceEndpointErrorConfiguration awareness (v2 only): EndpointErrorConditions

| Condition | Behavior |
|---|---|
| `STALE_MANIFEST` | Returns 404 when manifest hasn't been updated within threshold |
| `INCOMPLETE_MANIFEST` | Returns 404 when manifest doesn't have all expected tracks |
| `MISSING_DRM_KEY` | Returns 404 when DRM encryption key is unavailable (includes SPEKE v2 key-fetch failures via `EncryptionContractConfiguration`) |
| `SLATE_INPUT` | Returns 404 when the active input is a slate (non-primary content) |
