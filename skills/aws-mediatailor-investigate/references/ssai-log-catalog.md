# MediaTailor SSAI Log Catalog

Event-type taxonomy, log fields, and ready-to-run Logs Insights queries for the
SSAI log groups. Read this only after confirming logs are enabled
(`LogConfiguration.PercentEnabled > 0`) in Step S1; otherwise the step is a
DATA GAP.

## Observability preconditions (recap)

- `PercentEnabled = 0` -> no session logs at all.
- `PercentEnabled` between 1 and 99 -> MediaTailor logs a random subset of
  sessions. A specific session's absence proves nothing.
- `EnabledLoggingStrategies` selects the delivery path. `LEGACY_CLOUDWATCH`
  needs the MediaTailor-to-CloudWatch IAM role or logs go nowhere despite a
  non-zero percentage. `VENDED_LOGS` needs the CloudWatch Logs delivery chain
  (delivery source, delivery destination, destination policy for a cross-account
  destination, and the delivery itself); switching from legacy to vended stops
  logs immediately until that chain is complete. Verify read-only with
  `aws logs describe-delivery-sources`, `describe-delivery-destinations`,
  `describe-deliveries`.
- `AdsInteractionLog.ExcludeEventTypes` and
  `ManifestServiceInteractionLog.ExcludeEventTypes` suppress named events. If a
  family of events "never appears", check these lists before blaming sampling.
- `RAW_ADS_RESPONSE` (raw ADS body) is opt-in via
  `AdsInteractionLog.PublishOptInEventTypes` on the configuration (a
  `RAW_ADS_REQUEST` opt-in also exists on newer API versions). Without it the
  unparsed ADS payload is not visible.
- Manifest-service detail beyond errors, and generated-manifest comparison,
  require DEBUG mode: `?aws.logMode=DEBUG` on the playback GET (server-side
  reporting) or `"logMode": "DEBUG"` in the `/v1/session` POST body
  (client-side reporting); `DEBUG` is case-sensitive. Max 10 active debug
  sessions; a slot frees only when a session is stale (10 minutes live, 30
  minutes VOD); over the cap, debug logs are silently not written. Confirm
  activation by finding a `SESSION_INITIALIZED` event for the session ID before
  reading anything into its absence.

## Log groups

| Log group | Contents |
|---|---|
| `MediaTailor/AdDecisionServerInteractions` | ADS request/response, VAST/VMAP parsing, avail fill, beaconing, redirects, skipped ads |
| `MediaTailor/ManifestService` | Origin manifest retrieval and processing; usually only errors unless DEBUG |
| `MediaTailor/TranscodeService` | Ad transcode status (not-ready, transcode errors) |

Log streams are prefixed with the configuration name. The event-type list and
field names below follow the user guide's ADS log format and manifest log
pages; when in doubt, that page (not this file) is the authority.

## Running queries

Use the async Logs Insights pattern (start-query uses epoch SECONDS;
filter-log-events uses epoch MILLISECONDS, a 1000x difference):

```bash
QID=$(aws logs start-query \
  --log-group-name "MediaTailor/AdDecisionServerInteractions" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string '<QUERY>' \
  --no-cli-pager --output text --query queryId)

aws logs get-query-results --query-id "$QID" --no-cli-pager
```

## ADS interaction log: event-type catalog

Grouped by phase. The `eventType` field carries these values.

**Request and fill**
`MAKING_ADS_REQUEST`, `VAST_RESPONSE`, `RAW_ADS_RESPONSE` (opt-in),
`FILLED_AVAIL`, `FILLED_OVERLAY_AVAIL`, `AD_MARKER_FOUND`, `NON_AD_MARKER_FOUND`,
`VOD_TIME_BASED_AVAIL_PLAN_SUCCESS` / `_VAST_TIMEOUT` / `_ERROR`,
`INTERSTITIAL_VOD_SUCCESS` / `_FAILURE`.

**Empty or no-ad responses**
`EMPTY_VAST_RESPONSE`, `EMPTY_VMAP_RESPONSE`, `WARNING_NO_ADVERTISEMENTS`.

**ADS transport errors**
`ERROR_ADS_TIMEOUT`, `ERROR_ADS_IO`, `ERROR_ADS_INVALID_RESPONSE`,
`ERROR_ADS_RESPONSE_PARSE`, `ERROR_ADS_RESPONSE_UNKNOWN_ROOT_ELEMENT`,
`ERROR_UNKNOWN_HOST`, `ERROR_DISALLOWED_HOST`, `ERROR_PERSONALIZATION_DISABLED`,
`ERROR_UNKNOWN`.

**VAST content errors**
`ERROR_VAST_MISSING_IMPRESSION`, `ERROR_VAST_MISSING_CREATIVES`,
`ERROR_VAST_MISSING_MEDIAFILES`, `ERROR_VAST_MISSING_OVERLAYS`,
`ERROR_VAST_INVALID_MEDIA_FILE`, `ERROR_VAST_INVALID_VAST_AD_TAG_URI`,
`ERROR_VAST_MULTIPLE_LINEAR`, plus VAST redirect failures.

**Redirects and substitution**
`VAST_REDIRECT`, `REDIRECTED_VAST_RESPONSE`, `MODIFIED_TARGET_URL`,
`WARNING_URL_VARIABLE_SUBSTITUTION_FAILED`, `WARNING_VPAID_AD_DROPPED`.

**Beaconing**
`BEACON_FIRED`, `ERROR_FIRING_BEACON_FAILED`.

**Functions**
`PRE_ADS_REQUEST_HOOK_SUMMARY` / `_ERROR`,
`PRE_ADS_REQUEST_FUNCTION_COMPLETED` / `_ERROR`.

## ADS interaction log: key fields

Top level: `eventType`, `eventTimestamp`, `sessionId`, `requestId`, `originId`
(= configuration name), `customerId` (hashed account), `adsRequestUrl`,
`requestHeaders[]`.

`avail` object: `availId`, `originAvailDuration`, `filledDuration`, `fillRate`,
`numAds`, `creativeAds[]`, `slateAd`, `driftMillisecondsAtAvailStart`, and
`skippedAds[]` with `skippedReason`, `creativeUniqueId`, `vastDuration`,
`transcodedAdDuration`, `targetVariant`.

`vastResponse` object: `version`, `vastAds[]`, `errors[]`, `nonLinearAdsList[]`.
Also `vastAd`, and `rawAdsResponse` when opted in.

The skipped-ad reasons live inside the `FILLED_AVAIL` event's `skippedAds[]`, not
in a separate event.

**Casing trap.** The log field `skippedReason` carries the log-side enum in
upper snake case (for example `TRANSCODE_IN_PROGRESS`, `TRANSCODE_ERROR`),
which is not the same string as the metric name (`SkippedReason.TranscodeInProgress`).
A Logs Insights `filter skippedAds.0.skippedReason = "TranscodeInProgress"`
silently returns zero rows. Read the actual values with the histogram query
below before filtering on one.

`MAKING_ADS_REQUEST` and `FILLED_AVAIL` carry an optional
`prefetchScheduleName`: present means the ad decision came from a prefetch
retrieval, absent means a just-in-time ADS call. This is the only place
prefetch consumption is visible.

## Known ADS log schema bugs

- On an empty ADS response MediaTailor emits BOTH `EMPTY_VAST_RESPONSE` and
  `VAST_RESPONSE`, and `vastResponse` is not marked required on `VAST_RESPONSE`.
  Do not assume a `VAST_RESPONSE` event always carries a `vastResponse` object.
- `ERROR_UNKNOWN`, `ERROR_ADS_RESPONSE_PARSE`, and `WARNING_NO_ADVERTISEMENTS`
  lack structured error-detail fields in the schema, so the specific cause may
  be absent from the log line.

## Manifest-service log: event types

Errors (default): `CONFIG_SECURITY_ERROR`, `CONFIG_SYNTAX_ERROR`,
`CONNECTION_ERROR`, `IO_ERROR`, `TIMEOUT_ERROR`, `MANIFEST_ERROR`,
`HOST_DISALLOWED`, `UNKNOWN_HOST`, `INCOMPATIBLE_HLS_VERSION`,
`NO_MASTER_PLAYLIST`, `NO_MEDIA_PLAYLIST`, `NO_MASTER_OR_MEDIA_PLAYLIST`,
`PARSING_ERROR`, `SCTE35_PARSING_ERROR`, `INVALID_SINGLE_PERIOD_DASH_MANIFEST`,
`UNSUPPORTED_SINGLE_PERIOD_DASH_MANIFEST`, `LAST_PERIOD_MISSING_AUDIO` and its
`_WARNING` variant.

DEBUG only: `ORIGIN_MANIFEST`, `GENERATED_MANIFEST`, `SESSION_INITIALIZED`,
`TRACKING_RESPONSE`.

Manifest log fields include `responseBody`, `mediaTailorPath`,
`originRequestUrl`, `httpCode`, `errorMessage`, `cause`.

Connection, timeout, host, and no-playlist errors against a MediaPackage origin
URL are usually an UPSTREAM handoff (see SKILL.md scope boundary), not a
MediaTailor fault.

## Ready-to-run queries

**Shape of the problem (run this first)**

```
fields @timestamp, eventType
| stats count(*) as n by eventType
| sort n desc
```

**All ADS requests with user agent**

```
fields @timestamp, adsRequestUrl, requestHeaders.0.value as userAgent, sessionId, requestId
| filter eventType = "MAKING_ADS_REQUEST"
| sort @timestamp asc
| limit 200
```

**Skipped-ad reasons**

```
fields @timestamp, avail.availId, skippedAds.0.skippedReason, skippedAds.0.creativeUniqueId
| filter eventType = "FILLED_AVAIL" and ispresent(skippedAds.0.skippedReason)
| sort @timestamp desc
| limit 200
```

**Skipped-reason histogram (read the real enum values first)**

```
fields skippedAds.0.skippedReason as reason
| filter eventType = "FILLED_AVAIL" and ispresent(skippedAds.0.skippedReason)
| stats count(*) as n by reason
| sort n desc
```

**Prefetch versus just-in-time**

```
fields @timestamp
| filter eventType = "MAKING_ADS_REQUEST"
| stats count(*) as total,
        sum(ispresent(prefetchScheduleName)) as prefetch,
        sum(not ispresent(prefetchScheduleName)) as jit
  by bin(5m)
```

**Fill-rate summary from the log (cross-check the metric)**

```
fields avail.fillRate, avail.numAds
| filter eventType = "FILLED_AVAIL"
| stats avg(avail.fillRate) as avgFill, min(avail.fillRate) as minFill,
        avg(avail.numAds) as avgAds, count(*) as avails
```

Because suppressed and abandoned breaks emit no `FILLED_AVAIL`, this average is
over personalized breaks only; a healthy log average with a low
`Avail.FillRate` metric points at suppression or the personalization threshold
(see `ssai-fill-behavior.md`).

**ADS errors and timeouts only**

```
fields @timestamp, eventType, sessionId, adsRequestUrl
| filter eventType like /ERROR_ADS|ERROR_UNKNOWN_HOST|ERROR_DISALLOWED_HOST/
| sort @timestamp desc
| limit 200
```

**Empty and no-ad responses**

```
fields @timestamp, eventType, sessionId, adsRequestUrl
| filter eventType in ["EMPTY_VAST_RESPONSE", "EMPTY_VMAP_RESPONSE", "WARNING_NO_ADVERTISEMENTS"]
| sort @timestamp desc
| limit 200
```

**Beacons fired vs filled avails (tracking gap)**

```
fields @timestamp, eventType, beaconInfo.trackingEvent, beaconInfo.beaconUri
| filter eventType in ["BEACON_FIRED", "ERROR_FIRING_BEACON_FAILED"]
| sort @timestamp desc
| limit 200
```

**Single session trace** (substitute the id)

```
fields @timestamp, eventType, avail.availId, avail.fillRate
| filter sessionId = "<SESSION_ID>"
| sort @timestamp asc
```

**Generated vs origin manifest (DEBUG sessions only)**

```
fields @timestamp, eventType, mediaTailorPath
| filter eventType in ["ORIGIN_MANIFEST", "GENERATED_MANIFEST"]
| filter sessionId = "<SESSION_ID>"
| sort @timestamp asc
```

## Output interpretation

| Signal | Likely meaning | Next step |
|---|---|---|
| Many `EMPTY_VAST_RESPONSE` / `WARNING_NO_ADVERTISEMENTS` | ADS returning no ads | Check ADS targeting and inventory; correlate with low ADS fill |
| `ERROR_ADS_TIMEOUT` cluster | ADS slow or unreachable | Correlate `AdDecisionServer.Latency` / `.Timeouts`; check ADS endpoint |
| `WARNING_URL_VARIABLE_SUBSTITUTION_FAILED` | ADS URL macro unresolved (a `[player_params.*]` sent without the `ads.` prefix, or a session variable absent) | Compare `AdDecisionServerUrl` template with `MAKING_ADS_REQUEST.adsRequestUrl` (what was actually sent); parameter and alias rules in `playback-errors-and-limits.md` |
| `prefetchScheduleName` absent on every `MAKING_ADS_REQUEST` although a schedule exists | Prefetch not consumed | Check the schedule's retrieval/consumption windows and `AvailMatchingCriteria` against the break; confirm the schedule targets this configuration |
| No `FILLED_AVAIL` at all for a break the customer says was skipped | Suppressed or abandoned break (never personalized) | `AvailSuppression` and `PersonalizationThresholdSeconds` from S1; see `ssai-fill-behavior.md` |
| `skippedReason` transcode-related (`TRANSCODE_IN_PROGRESS`, `NEW_CREATIVE`-class) dominant | First-seen creatives | Transient; expected on new campaigns; watch it recover |
| `skippedReason` variant/profile-related | Ad encoding mismatch | Check transcode profile / `AdConditioningConfiguration` vs content variants |
| Manifest `CONNECTION_ERROR` / `TIMEOUT_ERROR` to MediaPackage URL | Origin unreachable | UPSTREAM handoff to the origin-layer investigation (aws-mediapackage-investigate) |
| Few or no log lines at low `PercentEnabled` | Sampling, not health | Report DATA GAP; recommend raising PercentEnabled |
