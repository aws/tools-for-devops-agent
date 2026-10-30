# MediaPackage Secondary Checks

Lower-frequency checks relocated from SKILL.md Steps 5, 7, 8, 9, 11 and 12 so the
main procedure stays compact. Run only the section the SKILL.md step points at.
All commands are read-only.

## ForceEndpointError diagnosis (Step 5)

Run when a v2 endpoint shows a high 404 rate.

```
High 404 rate on a v2 endpoint?
  ├─ ForceEndpointErrorConfiguration exists?
  │   ├─ YES → Check which conditions are configured:
  │   │   ├─ STALE_MANIFEST → Is ingest actually stale? (IngressBytes?)
  │   │   │   → If IngressBytes > 0 and stable → investigate packaging lag
  │   │   │   → If IngressBytes = 0 → upstream not delivering (PROPAGATED)
  │   │   │   → If ML just stopped cleanly → expect VOD conversion, not 404
  │   │   ├─ INCOMPLETE_MANIFEST → Is a track missing from ingest?
  │   │   │   → Check source stream for missing audio/video tracks
  │   │   ├─ MISSING_DRM_KEY → Is the DRM key provider reachable?
  │   │   │   → Check SPEKE key provider connectivity and credentials
  │   │   │   → If using SPEKE v2: check EncryptionContractConfiguration
  │   │   │       under Segment.Encryption.SpekeKeyProvider
  │   │   └─ SLATE_INPUT → Is the current input a slate?
  │   │       → Check MediaLive schedule for active slate/input-switch actions
  │   │
  │   └─ NO → Genuine 404 (endpoint path wrong, content not yet available)
```

## ActiveInput interpretation (v1 only)

**IMPORTANT: `ActiveInput` is a v1-only metric.** It does NOT exist in the
v2 metric namespace. For v2 channels, use `IngressMQCS` per ingest endpoint
and the egress response header `x-amzn-mediapackage-active-input` instead.
See Step 8 for v2 MQCS-based quality and active-input diagnostics.

v1's `ActiveInput` metric shows which ingest endpoint is currently active.

**Critical dimension requirement:** `ActiveInput` ONLY works with the specific
combination of `IngestEndpoint` + `OriginEndpoint` dimensions. No other
dimension combination returns data for this metric.

```
aws cloudwatch list-metrics \
  --namespace AWS/MediaPackage \
  --metric-name ActiveInput \
  --dimensions Name=Channel,Value=$CHANNEL_ID \
  --no-cli-pager --output json
```

Use the exact dimensions returned by list-metrics.

| Value | Meaning |
|---|---|
| 1 | This IngestEndpoint is the active source for this OriginEndpoint |
| 0 | This IngestEndpoint is standby |

### Redundancy monitoring

Both ingest endpoints should show traffic (IngressBytes > 0) even though
only one is `ActiveInput=1` at a time. If one endpoint shows zero IngressBytes:
- The corresponding MediaLive pipeline is not pushing
- Redundancy is degraded — a switch would fail

## MQCS quality metrics (v2 CMAF only)

Media Quality Confidence Score (MQCS) is available for v2 channels with
CMAF input type. MQCS serves two purposes in v2: quality monitoring AND
active-input determination (replacing v1's `ActiveInput` metric).

### Quality metrics

Dimensions: `ChannelGroup` + `Channel` + `TrackType`

`TrackType` values: `Video`, `Audio`, `Subtitle`

| Metric | Statistic | Meaning |
|---|---|---|
| ChannelMQCS | Average | Quality confidence score (0–100) |
| IngressMQCS | Average | Per-ingest-endpoint quality (add `IngestEndpoint` dim) |

**Dimension note:** The `*Sequence` variants (`ChannelMQCSSequence`,
`IngressMQCSSequence`) do NOT support the `TrackType` dimension. Only
the non-Sequence `ChannelMQCS` and `IngressMQCS` support per-track breakdown.

A declining MQCS indicates content quality issues detected at the
packaging layer. Correlate with upstream encoding metrics (ML DroppedFrames,
SvqTime) to determine if quality degradation originates upstream.

### Active-input determination (v2)

For v2 channels, active-input status is derived from MQCS rather than
a dedicated `ActiveInput` metric:
- Query `IngressMQCS` with dimensions `ChannelGroup` + `Channel` +
  `IngestEndpoint` to see quality scores per ingest pipeline
- The pipeline with the higher MQCS is typically the active source
- `InputSwitchConfiguration.MQCSInputSwitching` controls whether
  automatic switching is enabled
- `InputSwitchConfiguration.PreferredInput` (1 or 2) is the tie-breaker

If MQCS metrics don't exist in list-metrics:
- Channel may not be CMAF input type
- Or channel has not received enough content for quality scoring
```
DATA GAP: MQCS metrics not available. Channel InputType may not be CMAF,
or insufficient content has been processed for quality scoring.
For v2 HLS-input channels, per-ingest-endpoint IngressBytes is the only
indicator of which pipeline is actively receiving.
```

## Harvest job status (VOD extraction)

### v1 harvest jobs

If the customer mentions VOD clips or harvest jobs on a v1 channel:

```
aws mediapackage list-harvest-jobs \
  --include-channel-id $CHANNEL_ID \
  --no-cli-pager --output json
```

Check job `Status`: `SUCCEEDED`, `FAILED`, `IN_PROGRESS`

For failed jobs:
```
aws mediapackage describe-harvest-job --id $JOB_ID \
  --no-cli-pager --output json
```

Common failure reasons:
- S3 bucket permissions (MP needs write access)
- Content not available in the startover window
- Invalid time range (start >= end, or outside StartoverWindowSeconds)

### v2 harvest jobs (Live-to-VOD Harvester)

v2 has its own harvest job API with a richer status model:

```
aws mediapackagev2 list-harvest-jobs \
  --channel-group-name $GROUP \
  --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --no-cli-pager --output json
```

Optionally filter by status: `--status QUEUED|IN_PROGRESS|CANCELLED|COMPLETED|FAILED`

For details on a specific job:
```
aws mediapackagev2 get-harvest-job \
  --channel-group-name $GROUP \
  --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --harvest-job-name $JOB_NAME \
  --no-cli-pager --output json
```

v2 harvest job `Status` values: `QUEUED`, `IN_PROGRESS`, `CANCELLED`,
`COMPLETED`, `FAILED`

For failed v2 jobs, check `ErrorMessage` in the response. Common reasons:
- S3 bucket permissions (MP needs write access)
- Content not available in the startover window
- Invalid time range or endpoint configuration
- DRM key unavailable during the harvest window

## Origin endpoint configuration verification

### v2 ContainerType

v2 origin endpoints support three container types:

| ContainerType | Protocols | DRM notes |
|---|---|---|
| `TS` | HLS only | AES-128, SAMPLE-AES |
| `CMAF` | HLS, DASH, LL-HLS | CENC (Widevine, FairPlay, PlayReady) |
| `ISM` | MSS (Smooth Streaming) | CENC + PlayReady only; no key rotation; no SCTE-35 filtering; lookahead count fixed at 2; manifest URLs end in `.isml/Manifest` |

```
aws mediapackagev2 get-origin-endpoint \
  --channel-group-name $GROUP --channel-name $CHANNEL \
  --origin-endpoint-name $ENDPOINT \
  --query 'ContainerType' \
  --no-cli-pager --output json
```

### v2 manifest URLs

Manifest URLs are on the endpoint object:
- `HlsManifests[].Url` — HLS playlists
- `LowLatencyHlsManifests[].Url` — LL-HLS playlists
- `DashManifests[].Url` — DASH manifests
- `MssManifests[].Url` — MSS manifests (ISM container only)

### v2 DRM / SPEKE

DRM configuration is at `Segment.Encryption.SpekeKeyProvider`. For SPEKE v2
endpoints, also check `EncryptionContractConfiguration.{PresetSpeke20Audio,
PresetSpeke20Video}`. A SPEKE v2 key-fetch failure will trigger the
`MISSING_DRM_KEY` ForceEndpointError condition if configured.

### LL-HLS with CloudFront OAC

If the endpoint uses LL-HLS with CloudFront Origin Access Control (OAC),
check `HlsManifests` or `LowLatencyHlsManifests` for `UrlEncodeChildManifest`.
When CloudFront signs requests with SigV4, child manifest URLs must be
URL-encoded to preserve the signature. Missing this setting causes
child-manifest 403s from CloudFront.

## Access log analysis

If access logs are configured, they provide per-request detail that
CloudWatch metrics aggregate away.

### v1 access log check

```
aws mediapackage describe-channel --id $CHANNEL_ID \
  --query '{IngressLogs:IngressAccessLogs,EgressLogs:EgressAccessLogs}' \
  --no-cli-pager --output json
```

If `LogGroupName` values are present → logs are configured.

### v2 access log check (Vended Logs)

```
aws logs describe-delivery-sources \
  --no-cli-pager --output json
```

Filter for `resourceArn` containing `mediapackagev2`.

### Log analysis

See [references/access-log-analysis.md](references/access-log-analysis.md) for:
- v1 and v2 log schemas
- CloudWatch Logs Insights query templates
- Field name differences between v1 and v2
