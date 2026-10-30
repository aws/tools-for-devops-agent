# MediaPackage v1 Health Checklist

Mechanical pass/fail checklist for evaluating a MediaPackage v1 channel
and its origin endpoints.

## Prerequisites

- v1 channel ID confirmed (describe-channel succeeded)
- Time window established
- Dimension discovery completed

## Checklist

### 1. Channel and ingest endpoints

```
aws mediapackage describe-channel --id $CHANNEL_ID \
  --no-cli-pager --output json
```

Extract:
- `HlsIngest.IngestEndpoints[]` — URL, Username, Password (Id for reference)
- `IngressAccessLogs.LogGroupName` — if set, ingress logs available
- `EgressAccessLogs.LogGroupName` — if set, egress logs available

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Channel exists and is accessible | ✅ | NotFoundException | Critical |
| IngestEndpoints has 2 entries | ✅ | < 2 | High — reduced redundancy |
| IngressAccessLogs.LogGroupName set | ✅ | Not configured | DATA GAP |
| EgressAccessLogs.LogGroupName set | ✅ | Not configured | DATA GAP |

### 2. Ingest health

Namespace: `AWS/MediaPackage`

**Per-channel (dimensions: Channel):**

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| IngressBytes Sum > 0 | ✅ | = 0 | Critical — no content arriving |
| IngressResponseTime Average < 500ms | ✅ | > 2000ms | High — slow ingest |
| IngressResponseTime Maximum < 5000ms | ✅ | > 5000ms | High — spike |

**Per-endpoint (dimensions: Channel + IngestEndpoint):**

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| IngressBytes > 0 on endpoint A | ✅ | = 0 | High — endpoint A not receiving |
| IngressBytes > 0 on endpoint B | ✅ | = 0 | High — endpoint B not receiving |
| Both endpoints receiving | ✅ | Only one receiving | Medium — redundancy degraded |

If one endpoint has zero IngressBytes:
- Check the corresponding MediaLive pipeline (Pipeline 0 → first endpoint,
  Pipeline 1 → second endpoint)
- Check if credentials were rotated for that endpoint

### 3. Credential verification

v1 uses WebDAV credentials (username + password) per ingest endpoint.

If MediaLive shows Output4xxErrors with 401/403 pattern:
- Credentials on the ML channel destination may not match MP endpoint
- `rotate-ingest-endpoint-credentials` generates new credentials
- If called without updating ML's destination settings → immediate ingest failure

```
aws mediapackage rotate-ingest-endpoint-credentials \
  --id $CHANNEL_ID \
  --ingest-endpoint-id $ENDPOINT_ID \
  --no-cli-pager --output json
```

**WARNING:** This is a WRITE operation. In read-only mode, recommend the
customer perform rotation manually and update ML destination settings
in the same maintenance window.

### 4. Egress health

**Per-endpoint (dimensions: Channel + OriginEndpoint + StatusCodeRange):**

StatusCodeRange values: `2xx`, `3xx`, `4xx`, `5xx`

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| EgressRequestCount (2xx) Sum > 0 | ✅ | = 0 (no successful requests) | Critical |
| EgressRequestCount (4xx) Sum = 0 | ✅ | Sum > 0 | High |
| EgressRequestCount (5xx) Sum = 0 | ✅ | Sum > 0 | Critical |
| EgressBytes Sum > 0 | ✅ | = 0 | Critical — no content delivered |
| EgressResponseTime Average < 1000ms | ✅ | > 2000ms | High — slow packaging |

### 5. ActiveInput (redundancy indicator)

**Dimensions: IngestEndpoint + OriginEndpoint** (this specific combination only)

| Check | PASS | Meaning |
|---|---|---|
| ActiveInput = 1 on one endpoint | ✅ | That endpoint is the active source |
| ActiveInput = 0 on one endpoint | ✅ | Standby (ready for failover) |

Both endpoints showing ActiveInput = 0 would indicate no active ingest —
correlate with IngressBytes.

**Note:** `ActiveInput` is a v1-only metric. It does not exist in the v2
metric namespace. For v2 channels, see the v2 health checklist.

### 6. Origin endpoint configuration

For each origin endpoint:

```
aws mediapackage list-origin-endpoints \
  --channel-id $CHANNEL_ID \
  --no-cli-pager --output json
```

Then describe each:
```
aws mediapackage describe-origin-endpoint --id $ENDPOINT_ID \
  --no-cli-pager --output json
```

Key configuration checks:

| Field | Check | Impact if misconfigured |
|---|---|---|
| `Origination` | ALLOW (normal) vs DENY | DENY blocks all egress requests |
| `Whitelist[]` | Contains expected CIDR blocks | Missing CIDRs → requests blocked |
| `Authorization.CdnIdentifierSecret` | If set, CDN must send auth header with matching value | Missing/wrong header → 403 |
| `Authorization.SecretsRoleArn` | If Authorization set, role must be assumable by MP | Broken role → auth check fails |
| `StartoverWindowSeconds` | > 0 for DVR/timeshift | = 0 means no rewind capability |
| `TimeDelaySeconds` | Intentional delay | Non-zero adds latency (by design) |

**Note on `Whitelist`:** The API returns `Whitelist` as a flat array of
CIDR strings (e.g., `["0.0.0.0/0"]`), not a nested object. Access it
directly as `Whitelist[]`, not `Whitelist.AllowedOrigins`.

Package-specific layout settings (e.g., `ManifestLayout`) are nested
under the package type object (`DashPackage.ManifestLayout`,
`HlsPackage.PlaylistType`, etc.), not at the top level of the endpoint.

### 7. Access log availability

If IngressAccessLogs or EgressAccessLogs are configured:

```
aws logs describe-log-groups \
  --log-group-name-prefix $LOG_GROUP_NAME \
  --limit 1 --no-cli-pager --output json
```

Verify the log group exists and contains recent data:
```
aws logs filter-log-events \
  --log-group-name $LOG_GROUP_NAME \
  --start-time $START_MS --end-time $END_MS \
  --limit 5 --no-cli-pager --output json
```

If configured but log group empty or missing:
```
DATA GAP: Access logs configured (LogGroupName=$NAME) but log group
is empty or does not exist. Logs may have been deleted or logging
may have been recently enabled with no traffic yet.
```

If not configured:
```
DATA GAP: Access logs not configured for this channel.
Per-request detail (client IPs, paths, response codes, latencies)
unavailable. Only CloudWatch metric aggregates available.
To enable: update channel with IngressAccessLogs/EgressAccessLogs
log group configuration.
```

## Summary template

```
MediaPackage v1 Health: [ALL PASS / DEGRADED / CRITICAL FAILURE]
Channel: $CHANNEL_ID
Ingest endpoints: [X/2 receiving]
Origin endpoints: [count]

Checks passed: X/Y
First failure: [metric] at [severity]

Critical findings:
  - [list]

High findings:
  - [list]

Data gaps:
  - [list with reasons]
```
