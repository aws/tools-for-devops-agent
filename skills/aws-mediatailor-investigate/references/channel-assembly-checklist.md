# MediaTailor Channel Assembly Health Checklist

Mechanical pass/fail checklist for a single Channel Assembly linear channel,
plus the ListAlerts alert-code catalog. Run checks in order; stop at the first
FAIL for isolation, but continue for completeness in the report.

## Prerequisites

- Channel name known.
- Time window established.
- Dimension discovery completed (`list-metrics --namespace AWS/MediaTailor`);
  Channel Assembly metrics are available by channel or by channel output.

## Checklist

### 1. Channel state

```
aws mediatailor describe-channel --channel-name $CHANNEL_NAME \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| `ChannelState` = RUNNING | RUNNING | STOPPED | Critical |
| `PlaybackMode` consistent with config | LINEAR or LOOP | n/a | Context |
| `FillerSlate` set when `PlaybackMode` = LINEAR | Set | Absent on LINEAR | High |
| `Tier` consistent with sources and mode | BASIC: LINEAR or LOOP, VOD sources only; STANDARD: live sources allowed, LINEAR required | Live source on BASIC, or LOOP on STANDARD | High |

A STOPPED channel serves nothing and publishes no metrics; channels are created
stopped, so confirm whether it was ever started before deeper analysis. LOOP
mode does not support a filler slate, so its absence there is not a fault. Ad
breaks are not tier-gated: they are configured on programs that use VOD
sources (the slate VOD source sets the break duration), and live sources pass
DASH and HLS `DATERANGE` ad breaks through automatically. A program's
`AdBreaks[].OffsetMillis` must align with a segment boundary on all tracks of
the VOD source, otherwise that break is skipped. The service model states a
channel must be stopped before schedule changes are made; verify the current
constraint for the specific operation before advising, and present any
stop-then-edit workflow as an operator action.

### 2. Output configuration

For each entry in `Outputs[]`:

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| `SourceGroup` matches a source's `HttpPackageConfigurations.SourceGroup` | Match exists | No matching source | Critical |
| `ManifestName` unique per output | Unique | Collision | High |
| `HlsPlaylistSettings` / `DashPlaylistSettings` present for the packaging type | Present | Missing | High |
| `ManifestWindowSeconds` within the supported range | In range | Out of range | Medium |

A `SourceGroup` on the output with no source advertising that group yields no
playable content for that output. This is the most common structural fault.

### 3. Logging state

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| `LogConfiguration.LogTypes` contains `AS_RUN` | Present | Empty | DATA GAP (not a failure) |

If empty:

```
DATA GAP: As-Run logging is off for this channel. As-played program and
ad-break history is not observable.
To enable: aws mediatailor configure-logs-for-channel --channel-name <name>
--log-types AS_RUN (operator action).
Metrics (4xx/5xx/RequestCount/TotalTime) and ListAlerts remain available.
```

### 4. Schedule health

```
aws mediatailor get-channel-schedule --channel-name $CHANNEL_NAME \
  --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| No gaps between consecutive entries | Contiguous | Gap detected | High |
| No unexpected `ScheduleEntryType = FILLER_SLATE` runs | None | Present | High |
| Upcoming window has sufficient depth | Populated | Empty/short | Medium |

A program that failed to resolve falls back to filler slate, so a run of
FILLER_SLATE entries is a downstream symptom of a source problem (Section 6) or
an alert (Section 7).

### 5. Source contract

```
aws mediatailor list-source-locations --no-cli-pager --output json
aws mediatailor describe-source-location --source-location-name $SL --no-cli-pager --output json
aws mediatailor list-vod-sources --source-location-name $SL --no-cli-pager --output json
aws mediatailor describe-vod-source --source-location-name $SL --vod-source-name $V --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| `HttpConfiguration.BaseUrl` reachable | Reachable | Unreachable (see alerts) | Critical |
| `AccessConfiguration` valid for the source | Valid | Auth misconfigured | Critical |
| Source `HttpPackageConfigurations.SourceGroup` referenced by an output | Referenced | Orphan group | Critical |
| Source `Type` (HLS/DASH) matches the output packaging | Match | Mismatch | High |
| Live source (STANDARD) meets the live-source requirements | Met | PDT missing, non-DATERANGE markers, short window | High |

**S3 SigV4 access (`AccessType = S3_SIGV4`).** MediaTailor signs S3 origin
requests with SigV4 and the docs list three requirements, all of which must
hold: the source location `BaseUrl` is in S3 virtual-hosted-style form
(`https://<bucket>.s3.<region>.amazonaws.com/<key>`); the
`mediatailor.amazonaws.com` service principal is granted access (bucket policy
/ IAM) to read every multivariant playlist referenced by the VOD source package
configurations; and the API caller who created or updated the VOD source has
`s3:GetObject` on those same manifests. The most common regression behind a
sudden `UNAUTHORIZED` is a bucket-policy edit that dropped the service
principal or narrowed the prefix. `AUTODETECT_SIGV4` behaves the same for S3
and, for a MediaPackage v2 endpoint, requires the principal in the endpoint's
origin access policy plus `mediapackagev2:GetObject` for the caller.
`SECRETS_MANAGER_ACCESS_TOKEN` depends on the secret and its KMS key remaining
readable by MediaTailor. Reading these policies is read-only; fixing them is an
operator action.

**Live-source requirements (STANDARD tier).** From the working-with-live-sources
page: HLS live sources must carry `#EXT-X-PROGRAM-DATE-TIME` on the first
segment in the manifest window and on every discontinuity; HLS ad markers must
be `DATERANGE`; the source manifest window should be at least as long as the
channel's (best practice 30 s longer); target duration and child-playlist count
must match the existing sources. A missing PDT or a too-short source window is
a frequent live-channel stall or gap cause; confirm by fetching the origin
manifest (read-only). Live, VOD, and slate sources feeding one output must be
conditioned identically (rendition count, target duration, codecs, resolution,
frame rate, segmentation), or the `*_MISMATCH` alerts below fire; the fix is
upstream re-conditioning, not a Channel Assembly change.

### 6. Public policy (only if SSAI is layered on the channel)

```
aws mediatailor get-channel-policy --channel-name $CHANNEL_NAME --no-cli-pager --output json
```

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| Public access policy attached | Present | Absent | High (for SSAI-on-CA) |

SSAI on a Channel Assembly channel requires the public policy; its absence
explains playback access failures even when everything else is healthy. When
wiring SSAI on top, the SSAI playback configuration's `VideoContentSourceUrl`
should be the channel output `PlaybackUrl` minus the manifest filename and
extension, and a CDN belongs between the channel output and ad insertion (ad
insertion multiplies origin requests). Playback endpoints look like
`https://<prefix>.channel-assembly.mediatailor.<region>.amazonaws.com/v1/channel/<name>/<manifest>`;
an unknown audience ID on an audience-specific manifest returns 404.

### 7. Alerts

See the catalog below. Any non-Info alert is at least High severity until
triaged.

### 8. Output metrics

| Check | PASS | FAIL | Severity |
|---|---|---|---|
| `5xxErrorCount` Sum = 0 | 0 | >0 | Critical |
| `4xxErrorCount` Sum ~0 | ~0 | Sustained >0 | High |
| `RequestCount` > 0 while RUNNING and watched | >0 | 0 on a RUNNING channel | High |
| `TotalTime` low and stable | Stable | Rising | Medium |

## ListAlerts alert-code catalog

```
aws mediatailor list-alerts --resource-arn $RESOURCE_ARN --no-cli-pager --output json
```

ListAlerts paginates DynamoDB-style: a page can return 0 items while more exist
behind a `NextToken`. Rely on SDK auto-pagination (omit caps, never
`--no-paginate`) so a partial page does not read as "no alerts." Alerts exist
only for resources created on or after 2021-07-14; an empty result on an older
resource is a DATA GAP, not a clean result.

Each alert carries `AlertCode`, `AlertMessage`, `LastModifiedTime`,
`RelatedResourceArns[]` (the other resources implicated, for example the two
programs whose manifests mismatch), `ResourceArn`, and an optional `Category`
whose enum is `SCHEDULING_ERROR`, `PLAYBACK_WARNING`, `INFO`. The docs do not
publish which category each code carries; read `Category` off the actual alert
and report it as observed, never as a documented per-code fact. Alerts on a
channel or program roll up the alerts of the resources they contain, so a
channel-level `PROGRAM_ALERT` typically resolves to a `VOD_SOURCE_ALERT` and
then to the underlying source code; drill down rather than reporting the
roll-up.

**VOD source and source location codes**

| AlertCode | Meaning | Next step |
|---|---|---|
| `NOT_PROCESSED` | Source not yet processed | Wait and re-check; persistent = ingest problem |
| `UNREACHABLE` | Source base URL unreachable | Verify `HttpConfiguration.BaseUrl` and network path |
| `UNAUTHORIZED` | Access denied to the source | Check `AccessConfiguration`: for `S3_SIGV4` the three requirements in §5 (virtual-hosted BaseUrl, service principal grant, caller `s3:GetObject`); for Secrets Manager token, the secret and KMS access. Re-run ListAlerts after the fix to confirm it clears |
| `TIMEOUT` | Source fetch timed out | Origin slow or unreachable |
| `UNPARSABLE_MANIFEST` | Source manifest could not be parsed | Validate the source manifest format |
| `VARIANT_DURATION_MISMATCH` | Variant durations disagree | Re-package the source consistently |
| `SEGMENT_DURATION_TOO_LONG` | A segment exceeds 30 s | Re-segment the source |
| `TARGET_DURATION_MISMATCH` | Target duration mismatch | Align target durations across variants |

**Program codes**

| AlertCode | Meaning | Next step |
|---|---|---|
| `VOD_SOURCE_ALERT` | Underlying VOD source has an alert | Resolve the VOD source code above |
| `SOURCE_LOCATION_ALERT` | Underlying source location has an alert | Resolve the source location |
| `CODEC_MISMATCH` | Codec differs across programs in the group | Conform encodes; mismatch risks stalling |
| `RESOLUTION_MISMATCH` | Resolution differs across programs | Conform encodes |
| `BANDWIDTH_MISMATCH` | Bandwidth ladders differ | Conform encodes |
| `FRAMERATE_MISMATCH` | Frame rate differs across programs | Conform encodes |
| `TARGET_DURATION_MISMATCH` | Target duration differs | Conform segmenting |
| `SEGMENT_DURATION_MISMATCH` | Segment durations differ | Conform segmenting |
| `NO_COMMON_SEGMENT_BOUNDARY_FOR_AD_SLATE` | No shared boundary for slate insertion | Adjust slate or segment boundaries |
| `NOT_PROCESSED` | Program not processed | Wait/re-check |
| `TOO_MANY_ALERTS` | Alert volume capped | Resolve the highest-severity codes first |

**Channel code**

| AlertCode | Meaning | Next step |
|---|---|---|
| `PROGRAM_ALERT` | One or more programs on the channel have alerts | Drill into the program codes above |

The cross-program mismatch codes (codec/resolution/bandwidth/framerate) matter
because Channel Assembly stitches sources back to back; a mismatch at a boundary
is a common cause of player stalls at program transitions.

## Summary template

```
Channel Health: [ALL PASS / DEGRADED / CRITICAL FAILURE]

Channel state: [RUNNING/STOPPED], mode [LINEAR/LOOP], tier [BASIC/STANDARD]
Checks passed: X/Y
First failure: [check] at [severity]

Critical findings:
  - [list]
High findings:
  - [list]
Alerts (non-Info):
  - [AlertCode: AlertMessage]
Data gaps:
  - [As-Run off | pre-2021-07-14 resource | etc.]
```
