# CloudFront Cost Levers (Media Delivery Scope)

## Contents

1. Billing model
2. Lever: cache hit ratio for segment delivery
3. Lever: compression for manifests
4. Lever: Origin Shield economics
5. Lever: price class
6. Lever: commitment options
7. Lever: segment duration and request fees
8. Secondary: logging and edge-compute costs
9. Operator action mapping

## 1. Billing model

Pay-as-you-go bills per-GB data transfer out to viewers (tiered by
volume and geography; us/eu first tier illustration ~$0.085/GB, falling
with volume; APAC and South America materially higher) plus per-request
fees (US illustration ~$0.010 per 10k HTTPS, Europe ~$0.012; APAC
higher). For live HLS/DASH the request line is not negligible: every
viewer polls a manifest and fetches a segment every segment duration. **Transfer from AWS origins (MediaPackage, MediaLive, S3, ALB) into
CloudFront is free**; the origin-fetch leg costs nothing on the CloudFront
side, though MediaPackage bills its own egress on those fetches.

Perpetual free tier: 1 TB transfer out + 10M requests/month. Since late
2025 CloudFront also offers flat-rate plans per distribution (Free / Pro
/ Business / Premium bundling WAF, DDoS, edge functions) alongside
pay-as-you-go, and the Security Savings Bundle (roughly 30% off in
exchange for a 12-month monthly commitment, with a WAF credit).

CloudFront metrics live in `AWS/CloudFront`, us-east-1 only, dimensions
`DistributionId` + `Region=Global`. Rates are tiered per geography: sum
tier by tier from the pricing snapshot; never multiply total GB by the
first-tier rate.

## 2. Lever: cache hit ratio for segment delivery

In an HLS/DASH pipeline this is normally the largest single lever because
it reduces two bills at once: CloudFront origin-facing inefficiency and
MediaPackage origination egress (see mediapackage-cost-levers.md).

Measure: `CacheHitRate` metric (requires additional-metrics subscription,
`GetMonitoringSubscription`; if absent, estimate offload from
MediaPackage EgressBytes vs CloudFront BytesDownloaded and report the
DATA GAP). Healthy live delivery typically reaches 85-95%.

The structural fix is two cache behaviors: one for manifests (`*.m3u8`,
`*.mpd`; TTL near the segment duration; compression on) and one for
segments (`*.ts`, `*.m4s`, `*.cmf*`; long TTL, immutable; nothing
per-viewer in the cache key). A single default behavior serving both is
the most common finding.

Common cache-hit destroyers to inspect in `GetDistributionConfig` and the
attached cache policy (`CachePolicyConfig.ParametersInCacheKeyAndForwardedToOrigin`):

| Config | Problem |
|---|---|
| Query strings / all headers / cookies in cache key | segment requests fragment into unique cache entries |
| Session-specific tokens in path or query without a matching cache policy | every viewer becomes a cache miss |
| Manifest TTLs | manifests must stay short-TTL (they change per segment duration), segments should be long-TTL and immutable; misconfigured inversions destroy hit ratio or break playback |
| SSAI per-session manifests (MediaTailor) | personalized manifests are inherently uncacheable; segments must still cache; verify the distribution separates the two behaviors |

Modeled saving: (target offload - current offload) x monthly viewer GB x
MediaPackage egress rate, plus any origin-request fee delta. Keep
CloudFront viewer egress out of the saving (viewers download the same
bytes either way).

## 3. Lever: compression for manifests

Manifests are text and highly compressible; segments are already
compressed media and gain nothing. Verify the cache behavior serving
manifests has compression enabled and players send Accept-Encoding.
Saving is per-GB on manifest volume, which for high-concurrency live
(every player polling every few seconds) is larger than intuition
suggests. Model from request counts x average manifest size if byte
split by behavior is unavailable, and say so.

## 4. Lever: Origin Shield economics

Origin Shield adds a per-request fee (~$0.0075-$0.0150 per 10k, region
dependent) in exchange for collapsing duplicate origin fetches across
edge locations. It pays when cache hit ratio at the behavior is already
decent (>50%) and origin fetch reduction is valuable (protecting
MediaPackage during high-concurrency events, multi-CDN architectures).
Below ~50% hit ratio it is a surcharge on misses. Gate accordingly.
If enabled already, verify it is in the origin's region.

## 5. Lever: price class

If viewer geography (from geographic metrics or the customer's own
knowledge) concentrates in North America and Europe, PriceClass_100
excludes the most expensive edge regions. Tradeoff: viewers outside the
class are served from farther edges (worse latency, occasionally higher
first-byte); for a global audience this is a quality regression, so gate
on the customer's audience map.

## 6. Lever: commitment options

- **Security Savings Bundle**: ~30% off pay-as-you-go for a 12-month
  monthly commitment; sensible when the lookback window shows stable
  spend and WAF is in use (the bundle includes a WAF credit).
- **Flat-rate plans**: per-distribution monthly plans; compare the
  bundled allowance against observed GB/requests. Predictable mid-size
  workloads sometimes beat pay-as-you-go; spiky event traffic usually
  does not.

Both are commitments: apply the same "stable and predictable over 12
months" gate as reservations, and mark confidence by the variance in the
lookback window.

## 7. Lever: segment duration and request fees

Segment duration is set upstream (MediaLive output group, MediaPackage
endpoint) but bills here. Each viewer issues roughly one manifest GET and
one segment GET per segment duration:

```
2s segments: ~30 GET/min/viewer    6s segments: ~10 GET/min/viewer
10,000 concurrent viewers, 2s: 10,000 x 30 x 60 = 18M requests/hour
  at ~$0.010 per 10k HTTPS (US illustration) = ~$18/hour in request fees
same audience, 6s: ~$6/hour
```

Shorter segments also raise origin fetches on every miss. The tradeoff
is latency: 2s segments exist for a reason. Recommend 4-6s only where
the customer confirms low latency is not a requirement, and present the
request-fee delta alongside egress, never instead of it. Segment duration
must also match between MediaLive and MediaPackage or content is
repackaged (see configuration-cost-map.md coherence checks).

## 8. Secondary: logging and edge-compute costs

Standard access logs (to S3) and real-time logs (to Kinesis, billed per
million lines) both cost money downstream of CloudFront. Real-time logs
on a high-request live distribution generate cost every hour they run;
flag real-time log configs that outlived their investigation. Additional
metrics (`GetMonitoringSubscription`) bill per metric but supply
`CacheHitRate`; do NOT recommend removing them.

Edge auth for tokenized playback: CloudFront Functions (~$0.10 per 1M
invocations, illustration) versus Lambda@Edge (~$0.60 per 1M plus
duration). At live request scale, simple token checks on Lambda@Edge are
a candidate for CloudFront Functions; the tradeoff is Lambda@Edge's
richer capabilities (network calls, longer logic).

Origin Shield's incremental fee (~$0.009 per 10k requests US/EU
illustration) belongs in the section 4 model.

## 9. Operator action mapping

| Recommendation | Operator action (NOT EXECUTED by this skill) |
|---|---|
| Fix cache policy / TTLs / compression | `cloudfront:UpdateDistribution` (or cache policy updates) |
| Enable/disable Origin Shield | `cloudfront:UpdateDistribution` origin config |
| Restrict price class | `cloudfront:UpdateDistribution` PriceClass |
| Commitment purchase | console/sales workflow; no simple API purchase; present numbers only |
| Remove stale real-time logs | `cloudfront:DeleteRealtimeLogConfig` after detach |
| Split manifest/segment behaviors | `cloudfront:UpdateDistribution` adding cache behaviors + `cloudfront:CreateCachePolicy` |
| Segment duration change | upstream: `medialive:UpdateChannel` and MediaPackage endpoint update (channel IDLE) |
