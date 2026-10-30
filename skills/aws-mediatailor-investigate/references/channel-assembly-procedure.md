# MediaTailor Channel Assembly Procedure

Steps C1 to C4 of the investigation, relocated verbatim from SKILL.md. Run them
in order when Step 0 routes a Channel Assembly symptom, then return to Step F in
SKILL.md to compile findings. All commands are read-only.

## Step C1: Channel and output state

```
aws mediatailor describe-channel --channel-name $CHANNEL_NAME \
  --no-cli-pager --output json
```

| Field | Healthy | Investigate |
|---|---|---|
| `ChannelState` | RUNNING | STOPPED (channels are created stopped; a never-started channel emits no metrics) |
| `PlaybackMode` | LINEAR or LOOP | LINEAR requires a `FillerSlate`; LOOP does not support one |
| `Tier` | BASIC or STANDARD | BASIC supports LINEAR or LOOP and **no live sources**; STANDARD supports live sources and **requires LINEAR**. A live source on a BASIC channel, or LOOP on STANDARD, is a structural fault. Ad breaks are not tier-gated: they are configurable on programs that use VOD sources; live sources pass DASH and HLS `DATERANGE` ad breaks through |
| `Outputs[].SourceGroup` | Matches sources' `HttpPackageConfigurations.SourceGroup` | Mismatch = no playable output for that group |
| `FillerSlate` (LINEAR) | Set to a valid VOD source | Absent on LINEAR = schedule gaps cannot be filled |
| `LogConfiguration.LogTypes` | Contains `AS_RUN` | Empty = As-Run log off (DATA GAP for as-played history) |

If `ChannelState = STOPPED`, that is very often the whole answer: a stopped
channel serves nothing and publishes no metrics. Confirm whether it was ever
started before deeper analysis.

## Step C2: Schedule, programs, and sources

```
aws mediatailor get-channel-schedule --channel-name $CHANNEL_NAME \
  --no-cli-pager --output json
```

Inspect `Items[]` for: gaps between `ApproximateStartTime + ApproximateDurationSeconds`
and the next entry; `ScheduleEntryType = FILLER_SLATE` runs (a program failed to
resolve and fell back to slate; on LINEAR the slate loops for the whole gap, so
a long slate window is a symptom of a source that could not be placed, not the
cause); and an empty or short upcoming window (the schedule is running out).

For a suspect program:

```
aws mediatailor describe-program --channel-name $CHANNEL_NAME --program-name $PROGRAM \
  --no-cli-pager --output json
```

An `AdBreaks[].OffsetMillis` that does not align with a segment boundary on all
tracks of the program's VOD source is skipped (the documented rule); a program
scheduled with a source whose `HttpPackageConfigurations` do not include the
output's `SourceGroup` cannot be placed and falls to slate.

For source resolution, walk the source location and its sources, and confirm the
SourceGroup contract with the channel output:

```
aws mediatailor list-source-locations --no-cli-pager --output json
aws mediatailor describe-source-location --source-location-name $SL --no-cli-pager --output json
aws mediatailor list-vod-sources --source-location-name $SL --no-cli-pager --output json
aws mediatailor describe-vod-source --source-location-name $SL --vod-source-name $V --no-cli-pager --output json
aws mediatailor list-live-sources --source-location-name $SL --no-cli-pager --output json
```

`DescribeSourceLocation` gives `HttpConfiguration.BaseUrl` and
`AccessConfiguration` (`S3_SIGV4`, `AUTODETECT_SIGV4`,
`SECRETS_MANAGER_ACCESS_TOKEN`); an unreachable or unauthorized base URL is the
usual cause of source-resolution alerts in Step C3, and the S3 SigV4 access
type has three documented requirements (checklist §5). `DescribeVodSource`
gives `HttpPackageConfigurations[]` (Path, SourceGroup, Type); a `SourceGroup`
that no channel output references is a structural failure. Live sources have
their own requirements (`EXT-X-PROGRAM-DATE-TIME` on the first segment and
every discontinuity, `DATERANGE` ad markers, source window at least as long as
the channel window; checklist §5).

If SSAI is layered on the channel, also check the channel policy, since SSAI
on a Channel Assembly channel requires it, and note that the SSAI
configuration's content source should be the channel output `PlaybackUrl`
minus the manifest filename:

```
aws mediatailor get-channel-policy --channel-name $CHANNEL_NAME --no-cli-pager --output json
```

## Step C3: ListAlerts

ListAlerts is the richest Channel Assembly diagnostic surface. It requires a
resource ARN (take it from the Describe call in C1/C2). Alerts on a channel or
program roll up the alerts of the resources they contain, so a channel-level
`PROGRAM_ALERT` usually resolves to a `VOD_SOURCE_ALERT` and then to the
underlying source code (`UNAUTHORIZED`, `UNREACHABLE`, a `*_MISMATCH`).

```
aws mediatailor list-alerts --resource-arn $RESOURCE_ARN --no-cli-pager --output json
```

ListAlerts paginates DynamoDB-style: a page can return 0 items while more exist
behind a `NextToken`. This is exactly why the house rule (omit caps, never
`--no-paginate`) matters here; relying on SDK auto-pagination prevents a false
"no alerts" read. Do not pass `--no-paginate` or `--max-results`.

The alert-code catalog (VOD source / source location, program, and channel
codes) with the meaning and next step for each is in
[references/channel-assembly-checklist.md](references/channel-assembly-checklist.md).
Note alerts only exist for resources created on or after 2021-07-14; an empty
result on an older resource is a DATA GAP, not a clean bill of health.

## Step C4: Metrics and As-Run log

Discover dimensions live (same authoritative-discovery rule as S2):

```
aws cloudwatch list-metrics --namespace AWS/MediaTailor \
  --no-cli-pager --output json
```

Channel Assembly metrics are available by channel or by channel output:

| Metric | Healthy | Investigate |
|---|---|---|
| `5xxErrorCount` | 0 | Any sustained value = server-side fault |
| `4xxErrorCount` | ~0 | Sustained = client/config/auth (cross-check channel policy, request paths, unknown audience IDs return 404) |
| `RequestCount` | >0 while RUNNING and watched | Drop to 0 on a RUNNING channel is suspicious |
| `TotalTime` | Low and stable | Rising = latency growth |

If `LogConfiguration.LogTypes` from C1 contains `AS_RUN`, query
`MediaTailor/Channel/AsRunLog` for as-played programs and ad breaks (note: As-Run
currently covers only the default program, not alternateMedia from program
rules). If As-Run is off, emit the DATA GAP and name
`configure-logs-for-channel --log-types AS_RUN` as the operator fix.

---
