# MediaPackage v2 Health Checklist

Mechanical pass/fail checklist for evaluating a MediaPackage v2 channel
and its origin endpoints.

## Prerequisites

- v2 channel confirmed (get-channel succeeded)
- Channel group name and channel name known
- Time window established
- Dimension discovery completed

## Key differences from v1

| Aspect | v1 | v2 |
|---|---|---|
| Authentication | WebDAV credentials per endpoint | SigV4 (IAM-based) |
| Metric dimension for errors | `StatusCodeRange` ("4xx", "5xx") | `StatusCode` (individual codes) |
| CDN authorization | Per-endpoint `Authorization` object | Endpoint **policy** via `get-origin-endpoint-policy` |
| ForceEndpointError | Not supported | Supported (deliberate 404s) |
| Access logs | Native config (IngressAccessLogs/EgressAccessLogs) | Vended Logs (delivery sources) |
| Input types | HLS only | HLS or CMAF |
| Container types | TS only | TS, CMAF, or ISM |
| Quality metrics | None | MQCS (CMAF only) |
| Active input metric | `ActiveInput` (IngestEndpoint+OriginEndpoint dims) | None — use MQCS or per-endpoint IngressBytes |
| Root dimension | `Channel` | `ChannelGroup` + `Channel` |
| State reset | Not supported | `reset-channel-state` / `reset-origin-endpoint-state` |

## Checklist

### 1. Channel configuration

```
aws mediapackagev2 get-channel \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --no-cli-pager --output json
```

Extract:
- `IngestEndpoints[]` — URLs for SigV4-authenticated ingest
- `InputType` — HLS or CMAF
- `InputSwitchConfiguration` — CMAF input failover config (if present)
- `ResetAt` — if present, indicates a recent channel state reset

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Channel exists and is accessible | ✅ | ResourceNotFoundException | Critical |
| InputType is as expected | ✅ | — | Informational |
| ResetAt is NOT recent (within impact window) | ✅ | Recent reset | Medium — may explain discontinuity |

### 2. SigV4 authentication and resource policies

v2 uses IAM for ingest authentication. No per-endpoint credentials exist.

Check channel policy:
```
aws mediapackagev2 get-channel-policy \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --no-cli-pager --output json 2>&1
```

If the response is ResourceNotFoundException → no resource policy exists.
This is fine for same-account ingest but will block cross-account pushers.

For cross-account ingest (different account pushing to this channel):
- A resource policy MUST exist granting `mediapackagev2:PutObject` to the
  pusher's account/role
- Missing policy → pusher gets 403

Check origin endpoint policy (for cross-account egress AND CDN authorization):
```
aws mediapackagev2 get-origin-endpoint-policy \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json 2>&1
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Same-account ingest (no policy needed) | ✅ | — | — |
| Cross-account: policy grants PutObject to pusher | ✅ | No policy or missing principal | High — ingest will 403 |

### 3. Ingest health

Namespace: `AWS/MediaPackage`
Dimensions: `ChannelGroup` + `Channel`

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| IngressBytes Sum > 0 | ✅ | = 0 | Critical — no content arriving |
| IngressRequestCount (2xx) Sum > 0 | ✅ | = 0 | Critical — no successful pushes |
| IngressRequestCount (4xx) Sum = 0 | ✅ | > 0 | High — auth or format errors |
| IngressRequestCount (5xx) Sum = 0 | ✅ | > 0 | Critical — server-side errors |

Note: Use `StatusCode` dimension for IngressRequestCount (not StatusCodeRange).

If 4xx on ingest:
- 403 → SigV4 auth failure (check IAM role and resource policy)
- 400 → Malformed content (wrong format for InputType)
- 404 → Wrong ingest URL or channel doesn't exist

### 4. InputSwitchConfiguration (CMAF only)

For CMAF input type channels:

```
aws mediapackagev2 get-channel \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --query 'InputSwitchConfiguration' \
  --no-cli-pager --output json
```

Fields:
- `MQCSInputSwitching` (boolean) — enables automatic quality-based switching
- `PreferredInput` (integer 1 or 2) — tie-breaker when MQCS scores are equal

This controls how v2 handles failover between ingest endpoints for CMAF.
If not configured, default behavior applies.

### 5. Origin endpoint configuration

```
aws mediapackagev2 list-origin-endpoints \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --no-cli-pager --output json
```

For each endpoint:
```
aws mediapackagev2 get-origin-endpoint \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json
```

Key fields:

| Field | Check | Impact |
|---|---|---|
| `ContainerType` | TS, CMAF, or ISM | Determines available protocols and DRM options |
| `ForceEndpointErrorConfiguration` | Present? What conditions? | Deliberate 404s |
| `HlsManifests[].Url` / `DashManifests[].Url` | Accessible? | Player endpoint URLs |
| `LowLatencyHlsManifests[].Url` | If LL-HLS configured | LL-HLS player URLs |
| `MssManifests[].Url` | If ISM container type | MSS player URLs (`.isml/Manifest`) |
| `StartoverWindowSeconds` | > 0 for DVR | = 0 means no rewind |
| `Segment.SegmentDurationSeconds` | Reasonable (2–10s typical) | Very short = more load |
| `ResetAt` | If present | Recent reset may explain discontinuity |

**ContainerType-specific notes:**

| ContainerType | Protocols | DRM | Constraints |
|---|---|---|---|
| `TS` | HLS | AES-128, SAMPLE-AES | — |
| `CMAF` | HLS, DASH, LL-HLS | CENC (Widevine, FairPlay, PlayReady) | Supports MQCS, SCTE-35 |
| `ISM` | MSS (Smooth Streaming) | CENC + PlayReady only | No key rotation, no SCTE-35, lookahead=2 |

**Note on CDN authorization:** CDN auth configuration is NOT on the
endpoint object. It is on the endpoint **policy** — see Check 7 below.

### 6. ForceEndpointErrorConfiguration

```
aws mediapackagev2 get-origin-endpoint \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --query 'ForceEndpointErrorConfiguration.EndpointErrorConditions' \
  --no-cli-pager --output json
```

| Condition | Meaning | Impact on metrics |
|---|---|---|
| `STALE_MANIFEST` | Return 404 when manifest not updated within threshold | Elevated 404s during ingest gaps |
| `INCOMPLETE_MANIFEST` | Return 404 when tracks are missing | Elevated 404s when audio/video track missing |
| `MISSING_DRM_KEY` | Return 404 when DRM key unavailable (incl. SPEKE v2) | Elevated 404s during key-fetch failures |
| `SLATE_INPUT` | Return 404 when active input is slate | Elevated 404s during slate playback |

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| ForceEndpointError conditions NOT triggering | ✅ | Conditions active with healthy ingest | Medium — investigate packaging |
| ForceEndpointError conditions triggering with stale ingest | Expected | — | Informational (designed behavior) |

**Behavioral nuance:** `STALE_MANIFEST` only fires on actual encoder/path
failures. When MediaLive stops cleanly, it sends `EXT-X-ENDLIST`, which
converts the stream to VOD rather than triggering a 404.

### 7. CDN authorization

CDN authorization is configured on the origin endpoint **policy**, NOT on
the endpoint object itself. Retrieve it via:

```
aws mediapackagev2 get-origin-endpoint-policy \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json 2>&1
```

If `ResourceNotFoundException` → no endpoint policy (CDN auth not configured).

If a policy exists, inspect `CdnAuthConfiguration`:
- `CdnIdentifierSecretArns[]` — Secrets Manager secret ARNs
- `SecretsRoleArn` — IAM role MP assumes to read the secrets

The CDN sends the header `X-MediaPackageV2-CDNIdentifier` with each request.

If CDN auth is configured, query metrics with `CDNAuthorizationStatus` dimension:

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| CDNAuthorizationStatus=Authorized dominant | ✅ | Mostly Unauthorized | High |

Detailed diagnosis via `CDNAuthorizationStatusDetails` dimension:

| StatusDetails value | Meaning | Severity |
|---|---|---|
| `HeaderSecretMatched` | Valid header — authorized | ✅ Working |
| `MissingCdnAuthHeader` | CDN not sending header | High |
| `HeaderSecretMismatched` | Header value doesn't match secret | High |
| `MissingCdnAuthConfiguration` | Auth not configured on endpoint | Informational |
| `MissingCdnAuthHeaderAndConfiguration` | Neither header nor config present | Informational |
| `MissingCdnIdentifierSecretArns` | Policy exists, no secret ARNs | High |
| `MissingSecretsRoleArn` | Policy exists, no role ARN | High |
| `SecretsManagerInvalidParameterError` | Secrets Manager parameter issue | High |
| `SecretsManagerInternalServiceError` | Secrets Manager internal failure | High |
| `SecretsManagerThrottlingError` | Secrets Manager rate limit hit | High |
| `MediaPackageSecretsValidationError` | Secret value failed validation | High |
| `OtherErrors` | Unclassified CDN auth error | Medium |

### 8. Egress health

Dimensions: `ChannelGroup` + `Channel` + `OriginEndpoint` + `StatusCode`

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| EgressRequestCount (2xx) Sum > 0 | ✅ | = 0 | Critical — no successful responses |
| EgressRequestCount (4xx) Sum = 0 | ✅ | > 0 (non-ForceEndpointError) | High |
| EgressRequestCount (5xx) Sum = 0 | ✅ | > 0 | Critical |
| EgressBytes Sum > 0 | ✅ | = 0 | Critical |
| EgressResponseTime Average < 1000ms | ✅ | > 2000ms | High |

Additional v2 dimensions for deeper breakdown:
- `RequestType` = `manifest` or `segment`: Isolate manifest vs segment failures
- `OutputType` (or `OuputType`): `HLS`, `DASH`, `MSS`, `CMAF` — per-format analysis

**IMPORTANT: AWS docs typo warning.** The v2 dimension for output format is
documented as `OuputType` (missing a 't') in some doc versions. CloudWatch
dimension keys are case-sensitive. Query both `OutputType` and `OuputType`
defensively until AWS resolves the inconsistency.

### 9. MQCS quality (CMAF input type only)

Dimensions: `ChannelGroup` + `Channel` + `TrackType`

TrackType values: `Video`, `Audio`, `Subtitle`

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| ChannelMQCS Average > 80 | ✅ | < 50 | High — quality degradation |
| ChannelMQCS Average 50–80 | ⚠️ | — | Medium — quality concern |
| ChannelMQCS stable (low variance) | ✅ | Rapidly declining | High |

**Dimension note:** The `*Sequence` variants (`ChannelMQCSSequence`,
`IngressMQCSSequence`) do NOT support the `TrackType` dimension. Only
`ChannelMQCS` and `IngressMQCS` support per-track breakdown.

**Active-input determination:** v2 has no `ActiveInput` metric (that is
v1-only). For v2 CMAF channels, query `IngressMQCS` with the
`IngestEndpoint` dimension to see per-pipeline quality. The pipeline with
the higher MQCS is typically the active source.

If MQCS metrics don't exist:
```
DATA GAP: MQCS metrics not available. Channel InputType may not be CMAF,
or insufficient content has been processed for quality scoring.
For HLS-input v2 channels, per-ingest-endpoint IngressBytes is the only
indicator of which pipeline is actively receiving.
```

### 10. v2 harvest jobs

If the customer mentions VOD clips or harvest jobs:

```
aws mediapackagev2 list-harvest-jobs \
  --channel-group-name $GROUP \
  --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json
```

Optionally filter by status: `--status QUEUED|IN_PROGRESS|CANCELLED|COMPLETED|FAILED`

For details on a failed job:
```
aws mediapackagev2 get-harvest-job \
  --channel-group-name $GROUP \
  --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --harvest-job-name $JOB_NAME \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Job status COMPLETED | ✅ | FAILED | High |
| Job status IN_PROGRESS | ⚠️ (check duration) | QUEUED for too long | Medium |
| ErrorMessage empty | ✅ | Present | High — read error details |

### 11. Stuck state and reset history

Check if the channel or endpoint has been recently reset:

```
aws mediapackagev2 get-channel \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --query 'ResetAt' \
  --no-cli-pager --output json
```

```
aws mediapackagev2 get-origin-endpoint \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --query 'ResetAt' \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| No recent ResetAt (or before impact window) | ✅ | ResetAt within impact window | Medium — may explain discontinuity |

If endpoint appears stuck (healthy ingest but no egress, no ForceEndpointError):
- Recommend `reset-channel-state` or `reset-origin-endpoint-state`
- **WARNING:** This is a WRITE operation that discards in-flight content

### 12. Vended Logs (access log availability)

v2 uses Vended Logs (CloudWatch Vended Logs delivery) rather than the
native log configuration that v1 uses.

```
aws logs describe-delivery-sources \
  --no-cli-pager --output json
```

Filter results for `resourceArn` containing this channel's ARN or
`mediapackagev2` in general.

If delivery sources exist, identify the destination:
- CloudWatch Logs group
- S3 bucket
- Firehose delivery stream

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Vended Logs delivery source exists | ✅ | No delivery configured | DATA GAP |
| Destination log group has recent events | ✅ | Empty or stale | DATA GAP |

If not configured:
```
DATA GAP: Vended Logs not configured for this MediaPackage v2 channel.
Per-request access logs (client IPs, paths, response codes, latencies)
are unavailable. Only CloudWatch metric aggregates available.
To enable: Configure a Vended Logs delivery source via the Logs API
or CloudFormation.
```

### 13. v2 access log field format

v2 access logs use **snake_case** field names, while v1 uses **camelCase**.
When querying, use the correct field names for the version:

| Concept | v1 field | v2 field |
|---|---|---|
| Timestamp | `timestamp` | `event_timestamp` |
| Account | `account` | `account` |
| Channel ID | `channelId` | `channel_id` |
| Channel group | — | `channel_group_id` |
| Endpoint | `endpointId` | `endpoint_id` |
| Client IP | `clientIp` | `client_ip` |
| HTTP method | `method` | `method` |
| Request | `request` | `request` |
| Status code | `statusCode` | `status_code` |
| Sent bytes | `sentBytes` | `sent_bytes` |
| Received bytes | `receivedBytes` | `received_bytes` |
| Time to first byte | — | `time_to_first_byte` |
| Processing time | `processingTime` | — |
| Request ID | `requestId` | `request_id` |
| Domain name | `domainName` | `domain_name` |
| Protocol | `protocol` | `protocol` |
| User agent | `userAgent` | `user_agent` |
| CDN auth status | — | `cdn_authorization_status` |
| CDN auth details | — | `cdn_authorization_status_details` |

See [access-log-analysis.md](access-log-analysis.md) for full schemas and
query templates.

## Summary template

```
MediaPackage v2 Health: [ALL PASS / DEGRADED / CRITICAL FAILURE]
Channel Group: $GROUP | Channel: $CHANNEL
Input Type: [HLS/CMAF]
Container Type: [TS/CMAF/ISM]
Origin Endpoints: [count]

Checks passed: X/Y
First failure: [metric] at [severity]

Critical findings:
  - [list]

High findings:
  - [list]

ForceEndpointError status:
  - [Active/Not configured/Conditions not triggering]

CDN Authorization status (from endpoint policy):
  - [Configured and working / Failures detected / Not configured / No policy]

Reset history:
  - [No recent resets / Channel reset at $TIME / Endpoint reset at $TIME]

Data gaps:
  - [list with reasons]
```
