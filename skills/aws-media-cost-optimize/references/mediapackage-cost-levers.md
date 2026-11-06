# MediaPackage Cost Levers

## Contents

1. Billing model
2. Lever: CDN offload of origination egress
3. Lever: endpoint and channel hygiene
4. Lever: ingest multiplier awareness
5. v1 vs v2 cost posture
6. Harvest and VOD patterns
7. Operator action mapping

## 1. Billing model

**Live**: per-GB **ingest** (us-east-1 illustration ~$0.030/GB) plus
per-GB **origination/packaging egress** (~$0.050/GB) for content served
from the origin. **VOD**: origination/packaging only, no ingest charge.
Take live rates from the pricing snapshot; both families can be tiered.

Two structural facts drive most findings:

1. A MediaLive STANDARD channel ingests **two pipelines**, so MediaPackage
   ingest GB is roughly 2x the program bitrate volume. This is by design
   for redundancy, not waste; report it so the customer's mental model of
   "my channel is 8 Mbps" matches the 16 Mbps-equivalent ingest bill.
2. **Content served from CDN cache does not incur origination egress.**
   MediaPackage egress bills only on origin fetches. CloudFront cache hit
   ratio is therefore a MediaPackage cost lever, not just a CloudFront
   one.

Metrics for volume estimation: `IngressBytes`, `EgressBytes`
(v1 namespace `AWS/MediaPackage`; v2 vends metrics per channel group).
Dimension discovery first.

## 2. Lever: CDN offload of origination egress

Compute origin offload = 1 - (MediaPackage EgressBytes / CloudFront
BytesDownloaded) for the distribution(s) fronting the endpoint, over the
same window. Low offload means the customer pays MediaPackage egress AND
CloudFront origin-facing inefficiency simultaneously. The fix lives on
the CloudFront side (cache policy, TTLs); see cloudfront-cost-levers.md.
Report the MediaPackage dollar impact here: excess origin GB x egress
rate.

If no distribution fronts the endpoint (direct-to-player origination),
every viewer GB bills at the MediaPackage egress rate, which usually
exceeds blended CDN economics at scale. Flag as an architecture question.
A third-party CDN pulling directly from MediaPackage also pays internet
data transfer on the origin leg (only the CloudFront leg is free); note
it when a non-CloudFront CDN is in the topology.

## 3. Lever: endpoint and channel hygiene

Every origin endpoint with traffic bills egress; idle endpoints and
channels cost nothing per hour but are risk surface and can silently
resume billing. More materially: multiple packaging formats (HLS + DASH +
CMAF + MSS) on one channel multiply origination for the same content
across formats. Flag endpoints with zero requests across the lookback
window, and formats whose player population may no longer exist (the MSS
question). Removal is free money only when traffic exists; otherwise it
is hygiene.

## 4. Lever: ingest multiplier awareness

Where a SINGLE_PIPELINE MediaLive channel is recommended (see
medialive-cost-levers.md, gated on customer redundancy confirmation),
MediaPackage ingest also halves. Model the two services together so the
downgrade recommendation carries its full value.

## 5. v1 vs v2 cost posture

Per-GB rates are materially similar between v1 and v2, but the
packaging model differs in a way that can matter: v1 bills egress per
`OriginEndpoint`, one per packaging type (HLS, DASH, CMAF, MSS), each
consumed format billing separately. v2 puts multiple manifests
(`HlsManifests[]`, `LowLatencyHlsManifests[]`, `DashManifests[]`,
`MssManifests[]`) on ONE endpoint over ONE `Segment` configuration
(`ContainerType` TS or CMAF), so segments are packaged once and egress
bills per delivered GB rather than per format. Where a v1 estate runs
several endpoints per channel to serve several formats, v2 consolidation
is a real cost conversation. Otherwise migration is a capability decision
(LL-HLS, CMAF ingest, channel groups, manifest filtering, OAC) with no
automated path; do not present it as rate arbitrage. One indirect cost angle: v2 manifest
filtering can reduce delivered manifest variants and simplify CDN cache
keys, which shows up in delivery efficiency rather than MediaPackage
rates.

## 5a. Non-levers to leave alone

`StartoverWindowSeconds` (v2 up to 1,209,600 seconds) has no separate
storage line item; shortening the DVR window saves nothing. DRM/SPEKE
carries no MediaPackage surcharge (key server and Secrets Manager costs
sit on the customer side). Do not recommend either as a saving.

## 6. Harvest and VOD patterns

Live-to-VOD harvest jobs produce assets whose origination bills on
playback. Audit standing harvest automation that nobody consumes:
harvested-but-unwatched libraries cost S3 storage (out of media scope,
flag only) and pay origination when crawled. Volume commitments
(>= ~10 TB/month) exist via AWS sales; flag eligibility, never price.

## 7. Operator action mapping

| Recommendation | Operator action (NOT EXECUTED by this skill) |
|---|---|
| Remove dead endpoint (v1) | `mediapackage:DeleteOriginEndpoint` |
| Remove dead endpoint (v2) | `mediapackagev2:DeleteOriginEndpoint` |
| Remove dead channel | `mediapackage:DeleteChannel` / `mediapackagev2:DeleteChannel` |
| Drop unused format | endpoint update removing the packaging config |
| Improve offload | CloudFront-side changes; see cloudfront-cost-levers.md |
