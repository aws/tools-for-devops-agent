---
name: aws-media-cloudfront-investigate
description: >-
  Use this skill for the Amazon CloudFront edge in front of an AWS Elemental Media Services origin
  (MediaPackage v1/v2; HLS, DASH, CMAF). Use for viewer-side symptoms tied to the CDN: elevated
  edge 4xx/5xx, buffering while origin metrics look healthy, low cache hit ratio or origin
  overload, 502s with no matching origin log entry, geo-restriction 403s, distribution-side origin
  auth (OAC on v2, or a missing CDNIdentifier origin header), and questions about cache behaviors,
  TTLs, cache keys, or Origin Shield. Finds the distribution by ID or MediaPackage egress domain,
  reads AWS/CloudFront metrics in us-east-1, checks origin protocol and SNI, reviews cache
  behaviors and access logs, and attributes each elevated rate as CDN-side or origin-surfaced. Not
  for the origin's auth verdict (CDNAuthorizationStatusDetails, endpoint policy, secret),
  ingest/egress errors, or ForceEndpointError (aws-mediapackage-investigate), ad insertion
  (aws-mediatailor-investigate), or CDN cost (aws-media-cost-optimize).
metadata:
  author: blends
  version: "1.0.0"
  summary: "Read-only investigation of the CloudFront edge in front of a MediaPackage origin: edge error attribution, cache behavior, TTLs, OAC and access logs."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "Amazon CloudFront, AWS Elemental MediaPackage"
  aws-devops-agent-skills.technical-domains: "Operations, Observability"
---
# CloudFront Deep Investigation for Media Delivery

## Purpose

Perform a comprehensive investigation of the CloudFront distribution delivering
a media pipeline to viewers, when either:

1. Evidence from a broader media pipeline investigation points at the CDN /
   delivery layer and the origin (MediaPackage) has been assessed, OR
2. The customer asks specifically about CDN delivery, edge errors, cache
   behavior, or player-side buffering tied to a CloudFront distribution.

CloudFront is the **most-downstream tier** — closest to the viewer, furthest
from the encoder. The cardinal rule of this skill: **most CloudFront-surfaced
errors originate upstream.** A 5xx at the edge is far more often MediaPackage
faithfully forwarded than a CloudFront fault. This skill exists to tell the two
apart, not to assume the CDN is guilty because the symptom appeared there.

This is an observational, read-only investigation. Every finding is reported as
Observed / Expected / Question, every absence as a DATA GAP rather than a
healthy signal, and no account-identifying values (full ARNs, account IDs,
role ARNs) are echoed back to the customer.

## Prerequisites

- A CloudFront distribution ID supplied by the customer, OR the MediaPackage
  egress domain (or endpoint URL) of the origin so the distribution can be
  located in Step 1.
- Time window established (the customer's impact window, or the anomaly window
  observed in CloudWatch).
- Origin (MediaPackage) health assessed with aws-mediapackage-investigate, OR
  the customer scoped the question to the CDN directly.

If the origin has not been assessed, say so and prefer investigating
MediaPackage first — diagnosing the CDN before the origin inverts the
upstream-first methodology and produces false attributions.

## The two interpretation traps (read before querying)

CloudFront has two failure-to-read-the-data traps that are unique to it. Every
conclusion in this skill depends on them.

### Trap 1 — the global namespace (us-east-1 only)

`AWS/CloudFront` metrics publish to **us-east-1 only**, regardless of where the
distribution's viewers or origin are. Querying them in the pipeline's
operational region returns empty arrays *by construction* — not because traffic
is zero. Both `list-metrics` and `get-metric-data` must use `--region us-east-1`
for this namespace. If a prior query used the wrong region, discard those
results and re-query — do not report wrong-region emptiness as zero traffic.
(The same rule applies to CloudFront standard-logging v2 delivery sources: they
are configured and discovered in us-east-1.)

### Trap 2 — error rates are percentages, not counts

`4xxErrorRate`, `5xxErrorRate`, and `TotalErrorRate` are **percentages of
requests** (use the `Average` statistic), not error counts. `5xxErrorRate=2.5`
means 2.5% of requests returned 5xx — not 2.5 errors. To get absolute error
volume, multiply the rate by `Requests` over the same window. Reporting a rate
as a count (or vice versa) is the most common CloudFront misread; always state
the unit explicitly in the observation.

## Investigation checklist

Copy this list into your working notes and tick each step as you complete it. Run the
steps in order; skip a conditional step only when its condition says so, and say so.

- [ ] Step 1: Locate the distribution
- [ ] Step 2: Confirm the distribution and its origin binding
- [ ] Step 3: Collect delivery health metrics (us-east-1)
- [ ] Step 4: Attribute the error — CDN-layer vs origin-surfaced
- [ ] Step 5: Cache behavior, TTLs, and hit-ratio analysis
- [ ] Step 6: Origin Shield
- [ ] Step 7: Access-log analysis
- [ ] Step 8: Compile findings

## Step 1: Locate the distribution

If the customer supplied a distribution ID, use it and go to Step 2.

Otherwise, discover it by matching origins to the MediaPackage egress domain.
Take the origin domain from the MediaPackage endpoint URL (v1
`describe-origin-endpoint → Url`; v2 `get-origin-endpoint →
HlsManifests[].Url` / `DashManifests[].Url` / `LowLatencyHlsManifests[].Url`)
and match it against every distribution's origins:

```bash
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?contains(to_string(Origins.Items[].DomainName), `'"$ORIGIN_DOMAIN"'`)].{Id:Id,DomainName:DomainName,Status:Status,Aliases:Aliases.Items,Origins:Origins.Items[].DomainName}' \
  --no-cli-pager --output json
```

`list-distributions` is a global call and paginates; the CLI auto-paginates by
default. If the customer knows the viewer-facing hostname instead, match on
`Aliases.Items` or `DomainName` rather than origins.

The origin domain shape also tells you the MediaPackage generation, which
changes what "correct" configuration looks like in Step 2:

| Origin generation | Domain shape |
|---|---|
| MediaPackage **v1** | `…mediapackage.<region>.amazonaws.com` (path typically `/out/v1/…`) |
| MediaPackage **v2** | `…egress.…mediapackagev2.<region>.amazonaws.com` |

If no distribution's origin matches the MediaPackage egress domain, report a
DATA GAP — "CloudFront layer: no distribution found fronting this origin; CDN
unobserved, not absent" — and stop. The pipeline may use a non-CloudFront CDN,
a distribution in another account, or an intermediate (for example a MediaTailor
playback endpoint) between CloudFront and MediaPackage. Do not infer that
viewers reach the origin directly.

## Step 2: Confirm the distribution and its origin binding

Establish that the distribution actually fronts the pipeline under
investigation before reading any delivery metric.

```bash
aws cloudfront get-distribution --id "$DIST_ID" \
  --query 'Distribution.{Status:Status,DomainName:DomainName,
    Aliases:DistributionConfig.Aliases.Items,
    Origins:DistributionConfig.Origins.Items[].{Id:Id,Domain:DomainName,
      OriginPath:OriginPath,Shield:OriginShield,
      Custom:CustomOriginConfig.OriginProtocolPolicy,
      SslProtocols:CustomOriginConfig.OriginSslProtocols.Items,
      OAC:OriginAccessControlId},
    OriginGroups:DistributionConfig.OriginGroups.Items[].{Id:Id,
      Members:Members.Items[].OriginId,
      FailoverCodes:FailoverCriteria.StatusCodes.Items},
    Geo:DistributionConfig.Restrictions.GeoRestriction.RestrictionType,
    CustomErrors:DistributionConfig.CustomErrorResponses.Items[].{Code:ErrorCode,
      Maps:ResponseCode,TTL:ErrorCachingMinTTL},
    LegacyLogging:DistributionConfig.Logging}' \
  --no-cli-pager --output json
```

Read the result against the pipeline:

Table: [Step 2: Confirm the distribution and its origin binding](references/lookup-tables.md#step-2-confirm-the-distribution-and-its-origin-binding). Load it when you run this step.

If `get-distribution` is denied, report a DATA GAP (config not readable) and
continue with metrics only — do not infer config from the metric shape.

### MediaPackage-origin specifics (v1 vs v2)

| Origin generation | Required CloudFront config |
|---|---|
| MediaPackage **v1** | If CDN authorization is enabled, a custom origin header `X-MediaPackage-CDNIdentifier` whose static value must equal the `MediaPackageCDNIdentifier` key in the endpoint's Secrets Manager secret (CloudFront does not read the secret; rotation means updating both). OAC is not supported for v1; OriginPath typically `/out/v1/…` |
| MediaPackage **v2** | Origin protocol **HTTPS-only**, TLS 1.2+, **SNI required**; the AWS-managed MediaPackage origin request policy (or equivalent header forwarding); either OAC (`OriginAccessControlId` on the origin, with an endpoint policy granting `cloudfront.amazonaws.com` `mediapackagev2:GetObject` for this distribution's ARN) or a custom origin header `X-MediaPackageV2-CDNIdentifier` matching the endpoint policy's secret |

A v2 origin reached over `http-only` or without SNI fails TLS and surfaces as a
**502 at the edge with zero origin log entries** — a CloudFront-config fault, not
an origin fault. This is one of the few genuinely CloudFront-side root causes, so
verify the origin protocol policy explicitly when 502s appear without
corresponding MediaPackage egress errors.

## Step 3: Collect delivery health metrics (us-east-1)

Discover which metrics the distribution emits, then collect over the impact
window. Both calls must target us-east-1.

```bash
aws cloudwatch list-metrics \
  --namespace "AWS/CloudFront" \
  --dimensions Name=DistributionId,Value="$DIST_ID" Name=Region,Value=Global \
  --region us-east-1 --recently-active PT3H \
  --no-cli-pager --output json \
  --query 'Metrics[].MetricName'
```

Then collect the standard set (extend with any additional metrics
`list-metrics` returned):

```bash
cat > /tmp/cf-queries.json <<EOF
[
  {"Id":"req","MetricStat":{"Metric":{"Namespace":"AWS/CloudFront","MetricName":"Requests",
    "Dimensions":[{"Name":"DistributionId","Value":"$DIST_ID"},{"Name":"Region","Value":"Global"}]},
    "Period":60,"Stat":"Sum"},"ReturnData":true},
  {"Id":"bytes","MetricStat":{"Metric":{"Namespace":"AWS/CloudFront","MetricName":"BytesDownloaded",
    "Dimensions":[{"Name":"DistributionId","Value":"$DIST_ID"},{"Name":"Region","Value":"Global"}]},
    "Period":60,"Stat":"Sum"},"ReturnData":true},
  {"Id":"total_err","MetricStat":{"Metric":{"Namespace":"AWS/CloudFront","MetricName":"TotalErrorRate",
    "Dimensions":[{"Name":"DistributionId","Value":"$DIST_ID"},{"Name":"Region","Value":"Global"}]},
    "Period":60,"Stat":"Average"},"ReturnData":true},
  {"Id":"err4xx","MetricStat":{"Metric":{"Namespace":"AWS/CloudFront","MetricName":"4xxErrorRate",
    "Dimensions":[{"Name":"DistributionId","Value":"$DIST_ID"},{"Name":"Region","Value":"Global"}]},
    "Period":60,"Stat":"Average"},"ReturnData":true},
  {"Id":"err5xx","MetricStat":{"Metric":{"Namespace":"AWS/CloudFront","MetricName":"5xxErrorRate",
    "Dimensions":[{"Name":"DistributionId","Value":"$DIST_ID"},{"Name":"Region","Value":"Global"}]},
    "Period":60,"Stat":"Average"},"ReturnData":true}
]
EOF

aws cloudwatch get-metric-data \
  --region us-east-1 \
  --start-time "$START" --end-time "$END" \
  --metric-data-queries file:///tmp/cf-queries.json \
  --no-cli-pager --output json
```

Interpret the standard (always-on) metrics:

Table: [Step 3: Collect delivery health metrics (us-east-1)](references/lookup-tables.md#step-3-collect-delivery-health-metrics-us-east-1). Load it when you run this step.

`OriginLatency` and `CacheHitRate` are **additional metrics** that exist only if
the distribution has additional CloudWatch metrics enabled. If `list-metrics`
does not return them, that is a DATA GAP, not a healthy zero — note "OriginLatency
/ CacheHitRate not emitted (additional metrics not enabled on this distribution)"
and rely on access logs (Step 7) for cache and latency insight instead.

Per-status-code rate metrics (`401ErrorRate`, `403ErrorRate`, `404ErrorRate`,
`502ErrorRate`, `503ErrorRate`, `504ErrorRate`) are likewise additional metrics —
useful for splitting a 4xx/5xx spike by exact code when present. Confirm
availability with `list-metrics`; do not assume they exist.

Empty `Values[]` on any query is a signal to re-check the region and the
dimension pair (`DistributionId` + `Region=Global`) before concluding anything.

## Step 4: Attribute the error — CDN-layer vs origin-surfaced

This is the core of the skill. For every elevated rate, determine whether
CloudFront caused it or merely forwarded it, by reconciling against the
MediaPackage egress metrics for the same window (v1: `EgressRequestCount` by
`StatusCodeRange`; v2: `EgressRequestCount` by `StatusCode`; both:
`EgressResponseTime`).

### 5xx attribution

Table: [Step 4: Attribute the error — CDN-layer vs origin-surfaced: 5xx attribution](references/lookup-tables.md#step-4-attribute-the-error-cdn-layer-vs-origin-surfaced-5xx-attribution). Load it when you run this step.

### 4xx attribution

Table: [Step 4: Attribute the error — CDN-layer vs origin-surfaced: 4xx attribution](references/lookup-tables.md#step-4-attribute-the-error-cdn-layer-vs-origin-surfaced-4xx-attribution). Load it when you run this step.

Whenever attribution lands "CDN-side," phrase it as a candidate to verify, not a
verdict — the investigation observes; it does not assert a fix.

## Step 5: Cache behavior, TTLs, and hit-ratio analysis

A correct-looking distribution can still deliver badly if its cache behaviors are
wrong for streaming. This is where CloudFront-specific depth lives.

### Inspect the ordered cache behaviors

```bash
aws cloudfront get-distribution-config --id "$DIST_ID" \
  --query 'DistributionConfig.{
    Default:DefaultCacheBehavior.{Origin:TargetOriginId,Proto:ViewerProtocolPolicy,
      CachePolicy:CachePolicyId,OriginReqPolicy:OriginRequestPolicyId,
      Compress:Compress,MinTTL:MinTTL,RealtimeLog:RealtimeLogConfigArn},
    Ordered:CacheBehaviors.Items[].{Path:PathPattern,Origin:TargetOriginId,
      CachePolicy:CachePolicyId,OriginReqPolicy:OriginRequestPolicyId,
      RealtimeLog:RealtimeLogConfigArn}}' \
  --no-cli-pager --output json
```

Cache behaviors are an **ordered list**; the first `PathPattern` that matches a
request wins, and `DefaultCacheBehavior` is the fallback. For HLS/DASH the
correct shape is split by content type:

| Content | Example path pattern | Correct caching | Why |
|---|---|---|---|
| Manifests / playlists | `*.m3u8`, `*.mpd` | Short TTL or no-store | Players must see fresh manifests to discover new live segments; a long-cached manifest stalls playback |
| Media segments | `*.ts`, `*.m4s`, `*.cmfv`, `*.cmfa`, `*.mp4` | Long TTL | Segments are immutable once published; long caching is what makes the CDN effective |

A distribution that caches manifests too long produces **stall/rebuffer**
symptoms with *no* error-rate elevation — the classic "everything looks healthy
but playback is stuck" case. A distribution that fails to cache segments
(short/zero TTL, or a cache key that varies per request) produces **origin
hammering**: high MediaPackage `EgressRequestCount` relative to viewer
`Requests`, and a low cache hit ratio.

To read the TTLs and cache key behind a `CachePolicyId`:

```bash
aws cloudfront get-cache-policy --id "$CACHE_POLICY_ID" \
  --query 'CachePolicy.CachePolicyConfig.{Name:Name,MinTTL:MinTTL,DefaultTTL:DefaultTTL,MaxTTL:MaxTTL,
    Query:ParametersInCacheKeyAndForwardedToOrigin.QueryStringsConfig.QueryStringBehavior,
    Headers:ParametersInCacheKeyAndForwardedToOrigin.HeadersConfig.HeaderBehavior,
    Cookies:ParametersInCacheKeyAndForwardedToOrigin.CookiesConfig.CookieBehavior}' \
  --no-cli-pager --output json
```

### Cache-key hygiene

If the cache policy (or legacy `ForwardedValues`) includes per-viewer query
strings, cookies, or headers in the **cache key**, otherwise identical segment
requests fragment into separate cache entries and hit ratio collapses. For live
media the segment cache key should be the path alone. Flag query-string or
cookie inclusion in a segment behavior as a hit-ratio risk.

### Reading hit ratio

If `CacheHitRate` (additional metric) is available, read it directly. Otherwise
derive it from access logs (Step 7) via `x-edge-result-type`:
hit ratio ≈ (`Hit` + `RefreshHit`) ÷ total requests. For live streaming, segment
hit ratio should be high; a low segment hit ratio with healthy error rates points
at cache-key fragmentation, TTL misconfiguration, or Origin Shield being off
(next step) — not at the origin.

See [references/cache-behavior-patterns.md](references/cache-behavior-patterns.md)
for managed-policy guidance, the full TTL-vs-content matrix, and the common
misconfiguration catalogue.

## Step 6: Origin Shield

Origin Shield is an optional regional caching layer between CloudFront's regional
edge caches and the origin. It is configured **per origin** and was returned by
the Step 2 query as `Origins[].Shield` (`{Enabled: true|false,
OriginShieldRegion: "<region>"}`).

What it does and why it matters for media:

- **Request collapsing** — simultaneous cache-miss requests for the same segment
  from many edge locations are deduplicated into a single origin fetch. For a
  live event with many viewers, this is the single biggest reducer of
  MediaPackage origin load.
- **Higher cache hit ratio** — the shield is a shared mid-tier cache, so a
  segment fetched for one region is served from the shield to others.
- **Region placement** — `OriginShieldRegion` should be the AWS region **closest
  to the MediaPackage origin**, not to the viewers. A shield in the wrong region
  adds a latency hop without the locality benefit.

Diagnostic reading:

Table: [Step 6: Origin Shield](references/lookup-tables.md#step-6-origin-shield). Load it when you run this step.

Origin Shield trades a small per-request cost and one extra hop on a miss for
sharply lower origin load — relevant only as an observation here, since the
investigation recommends, it does not reconfigure.

## Step 7: Access-log analysis

CloudFront access logs are **opt-in**. There are three delivery modes, and
which one is in place decides what the agent can query:

Table: [Step 7: Access-log analysis](references/lookup-tables.md#step-7-access-log-analysis). Load it when you run this step.

Detect standard-logging v2:

```bash
aws logs describe-delivery-sources --region us-east-1 \
  --query 'deliverySources[?contains(to_string(resourceArns), `cloudfront`)].{Name:name,Arns:resourceArns,LogType:logType}' \
  --no-cli-pager --output json

aws logs describe-deliveries --region us-east-1 \
  --query 'deliveries[].{Source:deliverySourceName,Destination:deliveryDestinationArn,Type:deliveryDestinationType}' \
  --no-cli-pager --output json
```

If the delivery destination type is `CWL`, resolve the log group from the
destination (`describe-delivery-destinations`) or from the customer, and query
it with Logs Insights in us-east-1. If none of the three modes is enabled,
report a DATA GAP — "CloudFront access logs not enabled; edge-level request
detail unobserved" — and rely on metrics. Do **not** infer that absence of logs
means absence of errors.

The fields that carry diagnostic weight for media delivery:

Table: [Step 7: Access-log analysis (2)](references/lookup-tables.md#step-7-access-log-analysis-1). Load it when you run this step.

See [references/access-log-fields.md](references/access-log-fields.md) for the
full field reference, the result-type decode table, and ready Logs Insights
queries for splitting manifest vs segment behavior and computing hit ratio.

## Step 8: Compile findings

Structure each finding as Observed (the value plus the API or metric it came
from), Expected (the threshold or benchmark plus its source), and Question:
why? Do not declare a definitive root cause; surface evidence and the precise
question that follows from it. Report sections:

1. **Distribution identity** — ID, viewer domain/aliases, Status, origin
   generation (MediaPackage v1/v2), how it was located (customer-supplied or
   origin match)
2. **Origin binding** — origin domain/path correctness, protocol/SNI, OAC or
   CDN-auth header, origin groups, geo restriction, custom error responses
3. **Delivery metrics** — rates stated *as percentages* with the region noted
   (`us-east-1`), absolute error volume derived where `Requests` is known
4. **Attribution** — for each elevated rate, CDN-side candidate vs
   origin-surfaced, with the MediaPackage correlation that decided it
5. **Cache health** — manifest/segment TTL correctness, cache-key hygiene, hit
   ratio with its source (metric vs log-derived)
6. **Origin Shield** — enabled/region/effect on origin load
7. **Access logs** — mode in place, per-request findings, or DATA GAP
8. **DATA GAPS** — config not readable, additional metrics not enabled, logs
   off or not agent-queryable, wrong-region prior queries — each named explicitly
9. **Open questions** — ranked by severity

Carry the upstream-first verdict through: if the CloudFront-surfaced symptom was
origin-propagated, the headline is the origin, and CloudFront is reported as
"faithfully forwarding," not as the fault. Never echo full account-ID ARNs,
distribution-owner account IDs, or role ARNs back to the customer.

### Before presenting

Check the compiled findings and fix anything that fails before presenting them:

- Every Observed value names the API field or metric it came from, with its dimensions and time window.
- Every Expected value names its source: a threshold, a documented limit, or the resource's own configuration.
- No section asserts a definitive root cause; each finding ends in a question or a named handoff.
- Every signal that was not observable is reported as a DATA GAP with its reason, never as a healthy zero.
- No account IDs, ARNs, secrets or passphrases are reproduced; resources are named by type and name.
- Every CDN-side attribution was reconciled against the MediaPackage egress metrics for the same window, and every rate is stated as a percentage read in us-east-1.

## Common mistakes to avoid

1. **Querying `AWS/CloudFront` outside us-east-1** — returns empty by
   construction; never read as zero traffic.
2. **Reading error *rates* as error *counts*** — they are percentages; multiply
   by `Requests` for volume.
3. **Blaming the CDN for an origin-surfaced 5xx** — reconcile against MediaPackage
   egress before attributing; upstream-first still governs the last hop.
4. **Treating absent additional metrics (`OriginLatency`, `CacheHitRate`) as
   healthy zeros** — they are DATA GAPS unless enabled on the distribution.
5. **Missing a rewritten error** — `CustomErrorResponses` can map an origin 5xx to
   a 200; trust origin metrics over edge status when they disagree.
6. **Ignoring manifest-vs-segment TTL** — long-cached manifests stall playback with
   no error-rate signal at all.
7. **Counting an Origin Shield hit as an edge cache hit** — `x-edge-result-type`
   reports it as a `Miss` at the edge even though the origin was spared; use the
   detailed result type for true origin-load.
8. **Forgetting v2 origins need HTTPS-only + SNI** — a protocol mismatch surfaces
   as a 502 with no origin log entry.
9. **Diagnosing CloudFront before the origin** — inverts the methodology; assess
   MediaPackage first unless the customer scoped the question to the CDN.
10. **Assuming standard logs are always in S3** — standard logging v2 can deliver
    to CloudWatch Logs; check the delivery source before declaring logs
    un-queryable.
