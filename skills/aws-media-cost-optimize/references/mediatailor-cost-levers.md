# MediaTailor Cost Levers

## Contents

1. Billing model
2. Lever: log sampling and filtering
3. Lever: Channel Assembly tier and idle channels
4. Lever: transcode overage
5. Lever: unused playback configurations
6. Prefetch cost posture
7. Operator action mapping

## 1. Billing model

**SSAI ad insertion**: per 1,000 ad insertions, where one insertion = one
ad rendered to one viewer (ads x viewers). Since the April 2025 pricing
change there is a single self-service tier: illustration $0.50 per 1,000
live insertions and $0.25 per 1,000 VOD insertions (VOD priced at half of
live). Volume commitments begin above ~60M insertions/month via sales.
Take live rates from the pricing snapshot; the offer distinguishes live
and VOD usage types.

**Ad transcode**: 10 transcodes free per 1,000 insertions; additional
transcodes bill per transcode. Transcode demand is driven by unique
creatives x rendition formats, not by viewers.

**Channel Assembly**: per running channel hour. Illustrations: basic
(VOD-only sources) $0.10/hr; standard (VOD + live sources) $0.35/hr.
Stopped channels bill nothing.

**Logging**: each insertion includes a 50 KB log delivery allowance;
overage bills per GB into CloudWatch Logs. At scale this line item is
real money.

## 2. Lever: log sampling and filtering

`GetPlaybackConfiguration` exposes `LogConfiguration.PercentEnabled`
(0-100 session sampling). Configurations running at 100% in steady-state
production usually exceed the diagnostic value of the logs; a sampled
percentage preserves troubleshooting signal at a fraction of log volume.
Vended-log filtering can additionally exclude the heaviest event payloads
(for example raw ads response bodies) from delivery.

Detection: `PercentEnabled` = 100 plus material insertion volume.
Modeled saving: current log GB overage x CloudWatch vended log rate x
(1 - proposed sample rate). Estimate log volume from CloudWatch Logs
`IncomingBytes` on the MediaTailor log groups (dimension discovery
first).

Tradeoff to state plainly: sampled logs mean some individual sessions
become uninvestigable. aws-mediatailor-investigate consumes these logs;
recommend a sample rate consistent with the customer's support
expectations (commonly 10-25% steady state, 100% during incident
windows), and note the setting can be raised temporarily during
investigations.

## 3. Lever: Channel Assembly tier and idle channels

`ListChannels` + `DescribeChannel`: a RUNNING channel bills every hour.

- Channels RUNNING with no playback demand across the lookback window are
  stop candidates (stopped = $0).
- Channels on the standard (live-capable) tier whose program lineup is
  entirely VOD sources may fit the basic tier; tier is a channel
  property, so this is a recreate-or-reconfigure conversation with a
  ~70% rate difference in the illustrations. Verify current tier
  semantics from the pricing snapshot and service docs before
  recommending.

## 4. Lever: transcode overage

Transcode charges beyond the included allowance usually trace to creative
churn (many unique ads) or unnecessarily wide rendition sets. Check
`TranscodeProfileName` on the playback configuration: a custom transcode
profile matched to the origin's actual renditions avoids overage
transcodes, while a mismatched profile produces `NO_VARIANT_MATCH` (ads
fail rather than cost more). Unset means dynamic transcoding against the
main content's ladder; CMAF dynamic transcoding carries no additional
charge. If overage
appears in the customer's own billing review, the levers are ADS-side
creative reuse and aligning the origin's rendition ladder with actual
player needs (fewer formats = fewer transcodes per creative). This skill
can quantify the exposure (unique creatives x formats vs allowance) but
the fix is workflow-side; frame as questions.

## 5. Lever: unused playback configurations

Playback configurations bill nothing at rest, but stale configurations
pointing at dead origins or old ADS endpoints generate error-path ad
requests and log volume when players still hit them, and they widen the
audit surface. Flag configurations with zero requests in the lookback
window for deletion as hygiene.

## 6. Prefetch cost posture

Prefetch shifts ADS calls earlier; the insertions themselves bill
identically. The cost angle is indirect: prefetch can increase ADS call
volume (and therefore partner-side cost and log volume) for avails that
never air. If prefetch is configured, note it and ask whether prefetch
scope matches actual break patterns. No dollar model without ADS-side
data; mark LOW confidence.

## 7. Operator action mapping

| Recommendation | Operator action (NOT EXECUTED by this skill) |
|---|---|
| Reduce log sampling | `mediatailor:ConfigureLogsForPlaybackConfiguration` with PercentEnabled |
| Stop idle CA channel | `mediatailor:StopChannel` |
| Delete stale playback config | `mediatailor:DeletePlaybackConfiguration` |
| Delete dead CA channel | `mediatailor:DeleteChannel` |
