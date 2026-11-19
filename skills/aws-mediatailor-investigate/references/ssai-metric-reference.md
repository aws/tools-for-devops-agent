# MediaTailor SSAI Metric Reference

Complete CloudWatch metric catalog for server-side ad insertion, with what each
metric measures and good-versus-bad guidance for an observational report.
Namespace is `AWS/MediaTailor`. Metrics are always published (no opt-in) and
retained for 15 months.

## Dimension discovery is authoritative

The published dimension table documents only `ConfigurationName` (all metrics)
and, for `Function.*` metrics, `FunctionId`, `FunctionType`, and `HookType`. The
same documentation page's prose and console reference channel/output and an
`originID` dimension that the table omits. This is a known documentation gap.
Always bind to the dimensions returned by `list-metrics`, never to the docs:

```
aws cloudwatch list-metrics --namespace AWS/MediaTailor \
  --dimensions Name=ConfigurationName,Value=$CONFIG_NAME \
  --no-cli-pager --output json
```

In the logs (separate from metrics), `originId` means the configuration name,
not the video content origin URL. Do not interpret it as the content source.

Many SSAI metrics (`AdDecisionServer.Ads`, `AdsBilled`, `Avail.Duration`,
`Avail.FilledDuration`, `Avail.Impression`, `Avail.Complete`, `Requests`, and
the `SkippedReason.*` family) are also published as an **account-level series
with no dimensions**. Use that series in Step 0 to see whether an account-wide
shift exists before drilling into one configuration; a fleet-wide move across
unrelated configurations points away from a per-configuration cause.

Do not alarm on or query a metric name you have not seen in `list-metrics`.
Some troubleshooting pages in the user guide mention metric names and an event
type that do not appear in the CloudWatch metrics table or the ADS log format;
`list-metrics` and the ADS log format page are the authorities.

## Fill-rate math: simple versus weighted

`Avail.FillRate` and `AdDecisionServer.FillRate` are SIMPLE averages of
per-avail percentages. A handful of large unfilled avails and many small filled
ones can read as a healthy simple average while real filled duration is poor.
Compute and report the weighted values alongside, and state which you used:

```
ADS weighted fill   = (AdDecisionServer.Duration * 100) / Avail.Duration
Avail weighted fill = (Avail.FilledDuration * 100)   / Avail.Duration
```

`Avail.FillRate` is bounded above by `AdDecisionServer.FillRate`: MediaTailor
cannot insert more ad time than the ADS supplied.

## Render rate

Render rate estimates how many returned ads actually played (impression seen
during server-side beaconing). Compute with a CloudWatch math expression using
Statistic = Sum on both inputs:

```
render rate = (Avail.Impression / AdDecisionServer.Ads) * 100
```

This is meaningful only with server-side beaconing; client-side reporting modes
do not surface impressions to the server, so a low value there is a DATA GAP,
not a fault.

## Video completion rate

`Avail.Complete` counts ads for which MediaTailor fired complete beacons during
server-side reporting (one count per ad with at least one complete tracking
URI, whether or not the beacon was ultimately delivered); `Avail.Impression`
is the matching impression count. Statistic = Sum on both:

```
video completion rate = Sum(Avail.Complete) / Sum(Avail.Impression)
```

Same caveat as render rate: server-side beaconing only.

## ADS metrics

| Metric | Measures | Good vs investigate |
|---|---|---|
| `AdDecisionServer.Ads` | Count of ads in ADS responses in the period | Baseline for render-rate math |
| `AdDecisionServer.Duration` | Total ms of ads received from the ADS (can exceed Avail.Duration) | Compared to Avail.Duration for weighted ADS fill |
| `AdDecisionServer.Errors` | Non-200, empty, and timed-out ADS responses | ~0; sustained >0 = ADS problem |
| `AdDecisionServer.FillRate` | Simple average of per-avail ADS fill | Low = ADS not returning enough ad time |
| `AdDecisionServer.Latency` | ADS response time (ms) | 100 to 500 ms typical; over ~2 s suggests ADS perf or network latency (guidance, not an SLA) |
| `AdDecisionServer.Timeouts` | Count of timed-out ADS requests | 0 |
| `AdNotReady` | Times the ADS pointed at an ad not yet transcoded | High value drags down Avail.FillRate |
| `AdsBilled` | Ads billed based on insertion | Volume/billing reference |

## Avail metrics

| Metric | Measures | Good vs investigate |
|---|---|---|
| `Avail.Duration` | Planned total ms of avails from the origin manifest | Denominator for fill math |
| `Avail.FilledDuration` | Planned ms filled with ads | Numerator for weighted avail fill |
| `Avail.FillRate` | Simple average of avail fill; bounded by ADS fill | Low + low ADS fill = ADS issue; low + healthy ADS fill = insertion issue |
| `Avail.Impression` | Ads for which MediaTailor fired impression beacons during server-side reporting (one per ad with at least one impression URI, regardless of delivery) | Render-rate numerator; VCR denominator |
| `Avail.Complete` | Ads for which MediaTailor fired complete beacons during server-side reporting | VCR numerator |
| `Avail.ObservedDuration` | Observed avail ms (emitted at avail end, from segment durations) | Reconciles planned vs actual |
| `Avail.ObservedFilledDuration` | Observed filled ms | |
| `Avail.ObservedFillRate` | Observed simple average fill; HLS only, emitted at first CUE-IN | Absent if no CUE-IN; not a fault |
| `Avail.ObservedSlateDuration` | Observed ms of slate inserted | High = unfilled avails padded by slate (check fill) |

In PLAYER_SELECT / HLS interstitials mode the `Observed*` values are estimates,
not measured durations. Detect insertion mode (Step S1) and annotate.

## Origin and manifest metrics

| Metric | Measures | Good vs investigate |
|---|---|---|
| `Origin.Age` | Time the origin held the manifest before the MediaTailor request; direct-origin only, not CDN-cached | Stale-manifest decomposition (origin side) |
| `Origin.Errors` | Non-200 and timed-out origin responses | ~0; >0 usually an UPSTREAM handoff |
| `Origin.Timeouts` | Timed-out origin requests | 0 |
| `Origin.ManifestFileSizeBytes` | Origin manifest size (HLS and DASH) | Context for TooLarge |
| `Origin.ManifestFileSizeTooLarge` | Count of origin responses over the configured size | >0 = oversize manifest |
| `GetManifest.Age` | Total manifest age ms (origin create to personalized send) | Top-level stale-manifest signal |
| `GetManifest.MediaTailorAge` | Time the manifest sat inside MediaTailor | Stale decomposition (MediaTailor side) |
| `GetManifest.Errors` | Errors generating personalized manifests | ~0 |
| `GetManifest.Latency` | MediaTailor personalization response time (ms) | 50 to 200 ms typical; over ~1 s flags creative/origin/internal issues (guidance) |

Stale-manifest decomposition: a high `GetManifest.Age` driven by `Origin.Age`
points upstream of MediaTailor; driven by `GetManifest.MediaTailorAge` plus
`GetManifest.Latency` points at MediaTailor. `Origin.Age` is not emitted for
CDN-cached origin responses, so its absence is not evidence of a fast origin.

## Skipped-reason catalog

Each `SkippedReason.*` metric counts avails where an ad the ADS returned was not
inserted. They explain the gap between `AdDecisionServer.Ads` and inserted ads,
and the gap between ADS fill and avail fill.

| Metric | Meaning | Reading |
|---|---|---|
| `SkippedReason.TranscodeInProgress` | Ad not yet transcoded | Transient; high value drags Avail.FillRate down |
| `SkippedReason.NewCreative` | First request for this asset; transcode pending | Transient; high = many first-seen creatives (new campaign) |
| `SkippedReason.NoVariantMatch` | No variant match between ad and content | Ad encoding does not match content variants; check transcode profile |
| `SkippedReason.ProfileNotFound` | Transcode profile not found | Configuration/profile issue |
| `SkippedReason.TranscodeError` | Transcode failed | Check TranscodeService log |
| `SkippedReason.PersonalizationThresholdExceeded` | Ad duration exceeded the configured threshold | Check `PersonalizationThresholdSeconds` |
| `SkippedReason.DurationExceeded` | ADS returned more duration than the avail | Expected trimming; explains Avail.Ads vs ADS.Ads |
| `SkippedReason.EarlyCueIn` | Early CUE-IN cut the avail short | Upstream ad-marker timing |
| `SkippedReason.ImportError` | Import job error | |
| `SkippedReason.ImportInProgress` | Active import job | Transient |
| `SkippedReason.InternalError` | MediaTailor internal error | Rare; correlate with a support case if sustained |

## Functions metrics (if lifecycle hooks configured)

Always emitted when a function is attached to a hook; no opt-in. Extra
dimensions `FunctionId`, `FunctionType`, `HookType`.

| Metric | Meaning |
|---|---|
| `PreSessionInitHook.Invocations` / `.Errors` / `.Latency` | Pre-session-init hook activity |
| `PreAdsRequestHook.Invocations` / `.Errors` / `.Latency` | Pre-ads-request hook activity |
| `Function.Invocations` / `.Errors` / `.Latency` | Per-function activity |

## HLS interstitials (late-binding) metrics

| Metric | Meaning |
|---|---|
| `GetAssets.Requests` | Asset List requests for HLS interstitials sessions |
| `GetAssets.Latency` | Asset List response time (ms) |

These two names are not on the CloudWatch metrics page of the user guide as of
2026-08-17; treat them as unverified until `list-metrics` returns them for the
configuration in hand. In PLAYER_SELECT sessions the documented behavior is
that `Avail.ObservedFilledDuration` equals `Avail.FilledDuration`,
`Avail.ObservedSlateDuration` reports planned slate from Asset List responses,
and all `Observed*` values are estimates.

`Requests` (no prefix) is the overall concurrent TPS baseline across request
types.

## Baseline and correlation (is it actually anomalous?)

MediaTailor traffic is diurnal and event-driven, so judge a value against the
configuration's own pattern, never in isolation.

**Baseline comparison.** Pull the suspect window and an equivalent baseline
window with the same statistic and `Period`: same clock hours 24 h earlier
(day-over-day), same weekday last week (week-over-week), or before/after a
known change. Flag a metric when it moves materially against baseline (fill
down by more than about ten points, latency p90 up by half, error share up
several-fold), not because it "looks high". A shift that persists for several
consecutive periods is a regression; a single spike on a low-volume
configuration usually is not.

**Denominators.** Counts scale with `Period` and with traffic. Pair every
error or timeout count with `Requests` over the same window (metric math
`100 * e / r` in `get-metric-data`, with the component queries `ReturnData:
false`) so a rate is never reported without its volume. A 100 percent error
rate over four requests is not an incident.

**Read-only anomaly band.** `get-metric-data` accepts the expression
`ANOMALY_DETECTION_BAND(m, 2)` alongside the metric query `m`; it returns an
upper and lower expected band with no detector resource persisted. It needs
roughly two weeks of history, so cross-check with the baseline comparison for
new configurations.

**Correlation map.** When one metric moves, pull its neighbours to localize:

| Primary signal | Pull next | Tells you |
|---|---|---|
| `Avail.FillRate` or `AdDecisionServer.FillRate` down | `AdDecisionServer.Errors`, `AdDecisionServer.Timeouts`, `SkippedReason.*` | ADS-side failure vs creative/variant skip vs (if all flat) suppression/threshold |
| `AdDecisionServer.Latency` up | `AdDecisionServer.Timeouts`, fill rate | Slow ADS approaching the 3 s timeout -> dropped fill |
| `GetManifest.Errors` up | `Origin.Errors`, `Origin.Timeouts`, `Origin.Age` | Origin problem (upstream handoff) vs MediaTailor-side |
| `Origin.Timeouts` up | `Origin.Age`, `GetManifest.Latency` | Origin slow or stale (2 s origin timeout) |
| `SkippedReason.NoVariantMatch` up | `SkippedReason.TranscodeError`, transcode profile / ad conditioning settings | Variant or profile mismatch |
| `SkippedReason.TranscodeInProgress` / `NewCreative` up | Time since the break or campaign started | Normal early in a break's life vs persistent transcode lag |
| `Requests` spike | Fill rate, latency, `GetManifest.Errors` | Load-driven regression vs healthy growth |

If the correlation localizes to the origin or the ADS, that is an external
dependency: hand off to the owning layer rather than calling it a MediaTailor
fault.

## CDN and performance benchmarks (context, not pass/fail)

AWS publishes target benchmarks for CDN-plus-MediaTailor integrations. Treat as
report context, and let workflow-specific tolerance override.

| Target | Value |
|---|---|
| Cache hit ratio, content segments | >95% |
| Cache hit ratio, ad segments | >90% |
| Cache hit ratio, manifests | Not applicable for SSAI (must not be cached); 85%+ for channel assembly |
| Manifest request latency (P95) | <100 ms |
| Content segment delivery (P95) | <50 ms |
| Ad segment delivery (P95) | <75 ms |
| End-to-end startup (P95) | <2 s |
| Manifest error rate | <0.1% |
| Segment error rate | <0.01% |
| Player-reported rebuffering | <1% |

Event-flow timing flags from the troubleshooting guidance: total flow over 5 s
is a problem; ADS response over 2 s suggests ADS/network; manifest
personalization over 1 s suggests creative/origin/internal.
