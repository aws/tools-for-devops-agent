---
name: aws-media-cost-optimize
description: >-
  Cost analysis and savings recommendations for AWS Elemental Media Services. Use when a
  customer asks about cost, spend, pricing, billing, savings, reservations, right-sizing, idle
  resources, start/stop scheduling, over-provisioned input specifications, channel class, or
  whether MediaConnect Router would be cheaper than flows. Also use when an investigation
  surfaces idle or oversized media resources. Covers MediaConnect (flows, Router, reserved
  outbound bandwidth), MediaLive (input/output/add-on rates, reservations, channel class, stop
  scheduling), MediaPackage v1/v2, MediaTailor (ad insertion, Channel Assembly, log sampling),
  and CloudFront delivery economics. Models run rates and savings from live AWS Price List
  data. Recommendations only: never mutates resources or purchases anything. Not for fault or
  outage investigation (use the aws-*-investigate skills) and not for general AWS cost review
  outside Media Services.
metadata:
  author: blends
  version: "1.0.0"
  summary: "Cost review and modeled savings for MediaConnect, MediaLive, MediaPackage, MediaTailor and CloudFront from live Price List data; recommendations only."
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.aws-services: "AWS Elemental MediaConnect, AWS Elemental MediaLive, AWS Elemental MediaPackage, AWS Elemental MediaTailor, Amazon CloudFront"
  aws-devops-agent-skills.technical-domains: "Cost Optimization"
---
# Media Services Cost Optimization

## Purpose

Analyze the cost posture of a customer's AWS Elemental Media Services
pipeline and produce evidence-based savings recommendations. This skill is
scoped to Media Services cost levers (MediaConnect, MediaLive, MediaPackage,
MediaTailor, CloudFront delivery). It is not a general AWS cost review.

Unlike the investigate skills in this set, this skill's findings map to
mutating actions (purchasing reservations, stopping channels, deleting
flows). It produces RECOMMENDATIONS ONLY. Every recommendation states the
operator action it would become, marked NOT EXECUTED. Executing that action
is the customer's decision and is out of scope for this skill, even when the
agent's role would permit it.

## Position relative to the observational methodology

The same observational rules as the investigate skills govern here: report
what is observed, mark what cannot be observed as a DATA GAP, and never
present a model as a bill. Cost work adds one new output type on top of
observation: the modeled recommendation. A recommendation is a hypothesis
about money, built from three inputs, each with different trust levels:

1. **Rates**: authoritative, taken from a validated AWS Price List snapshot
   (see Step 1). Always record the snapshot version and publication date.
2. **Configuration**: authoritative, taken from describe/list API calls.
3. **Usage**: estimated. Without Cost Explorer or CUR access, running hours
   and data volumes are approximated from CloudWatch metrics. Always state
   the estimation method and mark the result as modeled, not billed.

Never use Cost Explorer (`ce:*`) by default. Each GetCostAndUsage request
costs the customer $0.01 per paginated page, requires permissions many
agent roles lack, and cannot be un-enabled once enabled on an account.
Only mention Cost Explorer as an option the customer can pursue themselves
for billing-grade numbers.

## Prerequisites

- Region(s) known. If unknown, ask the customer or enumerate with the
  Step 2 list calls across the regions they name.
- Pipeline topology known or discoverable. If the customer asks about a
  specific pipeline, build its topology from the Step 2 inventory (or
  reuse the resource map from a prior aws-*-investigate run) so that
  recommendations attach to real resource ARNs.
- Price List access as described in Step 1.

## Review checklist

Copy this list into your working notes and tick each step as you complete it. Run
the steps in order; each one builds on the output of the step before it.

- [ ] Step 1: Acquire and validate pricing data
- [ ] Step 2: Inventory billable resources
- [ ] Step 3: Estimate usage
- [ ] Step 4: Configuration coherence check
- [ ] Step 5: Evaluate cost levers per service
- [ ] Step 6: Threshold gates
- [ ] Step 7: Compile the Cost Recommendation Report
- [ ] Step 8: Misestimation check (mandatory before every report)

## Step 1: Acquire and validate pricing data

Acquire rates before any cost math. Never quote a rate from memory: rates
change, and a stale or guessed rate poisons every number downstream.

### Price List Query API via the AWS CLI

Requires the read-only `pricing:DescribeServices` and `pricing:GetProducts`
actions granted for this skill in the shared IAM template. The
API is free and its endpoints live in us-east-1, eu-central-1,
ap-southeast-1, and ap-south-1; always pass `--region us-east-1` (or
another endpoint region) regardless of the pipeline's region.

First confirm the service code exists in the live catalog rather than
assuming it. MediaConnect in particular does not carry the `Elemental`
prefix:

```
aws pricing describe-services --region us-east-1 \
  --service-code AWSElementalMediaLive --no-cli-pager --output json
```

Service codes: `AWSElementalMediaLive`, `AWSElementalMediaPackage`,
`AWSElementalMediaTailor`, `AmazonCloudFront`, and `AWSMediaConnect`
(candidate; if `describe-services` returns nothing for it, page through
`aws pricing describe-services --region us-east-1 --max-results 100` and
match any code containing `mediaconnect`).

Then pull the region-scoped products with their terms:

```
aws pricing get-products --region us-east-1 \
  --service-code AWSElementalMediaLive \
  --filters Type=TERM_MATCH,Field=regionCode,Value=$REGION \
  --max-results 100 --no-cli-pager --output json
```

Paginate with `NextToken` until exhausted. Each `PriceList` entry is a JSON
string carrying `product.attributes`, `terms.OnDemand` and `terms.Reserved`
with `priceDimensions` (unit, `beginRange`/`endRange`, `pricePerUnit.USD`),
plus `publicationDate` and `version`. CloudFront is global: filter on
`Field=location,Value=Global` or omit the region filter and match SKUs by
`productFamily` and `usagetype`. Apply the validation rules in
section 5 of
[references/pricing-data-acquisition.md](references/pricing-data-acquisition.md):
USD only, non-negative decimals, tier ranges preserved, publication date
captured.

### If the Query API is unavailable

If the `pricing:` actions are not granted, do not estimate rates from memory.
The same data is published without credentials by the Price List Bulk API
(plain HTTPS files under `pricing.us-east-1.amazonaws.com`). Ask the operator
to download the region-scoped price file for each service and paste back the
SKUs and rates the review needs, or to grant the two `pricing:` actions.
Endpoints, offer codes, file structure and the validation rules are in
[references/pricing-data-acquisition.md](references/pricing-data-acquisition.md).
This is an operator action, NOT EXECUTED by the agent.

### On any failure

If a service's rates cannot be acquired or validated, report
the gap and exclude that service from dollar figures:

```
DATA GAP: Pricing data for <service> could not be acquired or validated
(reason). Cost figures for this service are omitted rather than estimated
from memory.
```

Record in the final report, for every service priced:
`Pricing snapshot: <serviceCode> version <version>, published <date>`.

## Step 2: Inventory billable resources

Enumerate what exists and what state it is in. State determines whether a
resource bills at all (a STANDBY flow and an IDLE channel with pull inputs
cost nothing; an IDLE channel with push inputs still bills for the inputs).

```
aws medialive list-channels --no-cli-pager --output json
aws medialive list-inputs --no-cli-pager --output json
aws medialive list-reservations --no-cli-pager --output json
aws mediaconnect list-flows --no-cli-pager --output json
aws mediaconnect list-reservations --no-cli-pager --output json
aws mediapackage list-channels --no-cli-pager --output json
aws mediapackage list-origin-endpoints --no-cli-pager --output json
aws mediapackagev2 list-channel-groups --no-cli-pager --output json
aws mediatailor list-playback-configurations --no-cli-pager --output json
aws mediatailor list-channels --no-cli-pager --output json
aws cloudfront list-distributions --no-cli-pager --output json
```

Follow up with `describe-*` on each resource that will appear in a
recommendation. Capture the tier-selecting fields listed in
[references/configuration-cost-map.md](references/configuration-cost-map.md):
for MediaLive `InputSpecification`, `ChannelClass`, per-output codec,
resolution, frame rate and rate control; for MediaConnect
`Source.Transport.Protocol`, `FlowSize`, output destinations and AZ, Router
`Tier`; for MediaPackage endpoint formats and ingest endpoints; for
CloudFront cache behaviors and policies. These fields decide which SKU a
resource bills at, so a recommendation cannot be priced without them.

MediaConnect Router note: router inputs and outputs are independent
billable resources. If `list-router-inputs` or `list-router-outputs`
return resources, inventory them alongside flows.

## Step 3: Estimate usage

Usage estimation is the weakest input, so be explicit about method.

**Running hours**: estimate from CloudWatch metric datapoint presence over
a lookback window (default 30 days, period 3600). Run dimension discovery
with `list-metrics` first, then `get-metric-data`. Count the hours with
datapoints. Suitable presence metrics:

| Service | Presence metric |
|---|---|
| MediaLive channel | `NetworkOut` (per pipeline) |
| MediaConnect flow | `SourceBitRate` |
| MediaTailor Channel Assembly | channel state history is not metric-visible: use describe state now plus customer confirmation |

Citation integrity applies: a metric name appearing in `list-metrics` is
never evidence of a value. Only `get-metric-data` responses may be cited.

**Data volumes**: estimate from bitrate integration (`SourceBitRate`
average x active hours for MediaConnect) or byte metrics where they exist
(CloudFront `BytesDownloaded`, MediaPackage `EgressBytes`,
`IngressBytes`). State the conversion arithmetic in the report.

**Always report the estimation caveat**:

```
Usage figures are modeled from CloudWatch metrics over <window>, not from
billing records. For billing-grade numbers the customer can consult Cost
Explorer or CUR (not accessed by this agent; per-request charges apply to
Cost Explorer API use).
```

## Step 4: Configuration coherence check

Before pricing anything, compare what each resource is configured to bill
for against what its source and audience actually use. This is where the
cheapest savings live: no quality change, no commitment, just tiers that
were set higher than the content ever needed. Work through section 9 of
[references/configuration-cost-map.md](references/configuration-cost-map.md)
for every hop in the topology. The four highest-value checks:

1. MediaLive `InputSpecification` (Codec, MaximumBitrate, Resolution)
   versus the feeding source's actual codec, bitrate, and resolution. The
   specification is set once per channel and bills every running hour at
   the declared tier.
2. `ChannelClass=STANDARD` where downstream consumes only one pipeline
   (one MediaPackage ingest endpoint receiving bytes).
3. H.264 outputs on `FramerateControl=INITIALIZE_FROM_SOURCE`, which
   provisions and bills the 30-60fps tier for 30fps content.
4. CloudFront distributions without separate cache behaviors for manifests
   and segments, or with session tokens in the segment cache key.

Report each mismatch as an observation with a question:

```
Observed: channel <ARN> InputSpecification MAX_50_MBPS/HD/HEVC; feeding
flow <ARN> SourceBitRate averaged 9.2 Mbps over 30 days, source codec AVC.
Expected: MAX_10_MBPS/HD/AVC would cover the observed source.
Question: Is the headroom deliberate (planned higher-bitrate contribution)
or is the specification over-provisioned?
```

Downgrades that trade resilience or quality (channel class, ladder top
rendition, advanced audio) still go through the Step 6 gates. Downgrades
that trade nothing (input tier above source, framerate provisioning,
duplicate ladders) are the first recommendations to surface.

## Step 5: Evaluate cost levers per service

Work through each service present in the inventory. Each reference file
owns one service's levers, the exact fields to inspect, and the arithmetic:

- [references/medialive-cost-levers.md](references/medialive-cost-levers.md):
  reservations and break-even math, stop scheduling, channel class
  downgrade, idle push inputs, output ladder right-sizing.
- [references/mediaconnect-cost-levers.md](references/mediaconnect-cost-levers.md):
  idle and standby flows, reserved outbound bandwidth, Flows vs Router
  migration modeling, cross-AZ placement.
- [references/mediapackage-cost-levers.md](references/mediapackage-cost-levers.md):
  endpoint hygiene, ingest multiplier awareness, CDN offload of egress.
- [references/mediatailor-cost-levers.md](references/mediatailor-cost-levers.md):
  log sampling, Channel Assembly tier and idle channels, transcode
  overage, unused playback configurations.
- [references/cloudfront-cost-levers.md](references/cloudfront-cost-levers.md):
  cache hit ratio, compression, Origin Shield economics, price class,
  commitment options.
- [references/data-transfer-map.md](references/data-transfer-map.md):
  which inter-service legs are free and which are charged; check every
  hop in the discovered topology against this map.
- [references/configuration-cost-map.md](references/configuration-cost-map.md):
  field-by-field map from describe responses to billing tiers, with the
  tradeoff of each cheaper setting and cross-service coherence checks.

Evaluate reservations wherever `list-reservations` returned existing
commitments: an unused or mismatched reservation is itself a finding
(money already spent that no running resource is consuming).

## Step 6: Threshold gates

Do not emit a recommendation that fails its gate. These gates encode where
the math stops favoring the change; below them, the recommendation would
cost the customer money or resilience.

| Recommendation | Gate |
|---|---|
| MediaLive reservation purchase | Matched attributes run >= 180 hours/month, sustained across the lookback window, and usage is not one-off/seasonal (unused reserved minutes are forfeited monthly) |
| MediaConnect reserved outbound bandwidth | Sustained internet egress approximating 24x7, projected utilization >= 40% of the committed tier, and no existing active reservation in the region (one per account per region) |
| Channel stop scheduling | Channel shows recurring multi-hour windows with zero activity, and the customer confirms the channel is not required hot-standby |
| STANDARD to SINGLE_PIPELINE downgrade | Customer explicitly confirms redundancy is not required for this channel; never recommend on modeling alone |
| Output ladder trim, advanced audio removal, price class restriction | Customer confirms the rendition, audio format, or geography is not consumed; delivery-side evidence (manifest requests, player population) supports it |
| Input specification downgrade | Observed source bitrate, codec, and resolution over the full lookback window sit at or below the proposed tier, with headroom the customer accepts; a source that peaks above the tier will be rejected at ingest |
| Flows to Router migration | Multiple flows kept ACTIVE primarily to preserve routing paths, with material idle time; model both architectures side by side before recommending |
| Origin Shield | Behavior cache hit ratio > 50% (below that it is a surcharge) |
| CloudFront commitment (Savings Bundle / flat-rate plan) | 12-month spend is stable and predictable from the lookback window |

## Step 7: Compile the Cost Recommendation Report

Extend the observation-report conventions with this per-recommendation
block. ALWAYS use this exact structure for each recommendation:

```
RECOMMENDATION <n>: <one-line summary>
  Observed: <configuration and usage evidence, with resource ARNs>
  Modeled current cost: <amount>/month (rate source: pricing snapshot <version>)
  Modeled cost after change: <amount>/month
  Modeled saving: <amount>/month (<percent>)
  Assumptions: <usage estimation method, window, anything the model presumes>
  Confidence: HIGH | MEDIUM | LOW
  Tradeoff: <what the customer gives up: redundancy, flexibility, commitment>
  Operator action (NOT EXECUTED): <exact API operation and parameters>
  Question: <what only the customer can answer before acting>
```

Confidence rubric: HIGH means rates validated and usage directly measured;
MEDIUM means usage estimated from metric presence; LOW means a material
assumption is unconfirmed (mark what). Rank recommendations by modeled
saving, then confidence.

Open the report with scope, pricing snapshot identifiers, the usage
estimation caveat from Step 3, and any DATA GAPs. Close it with the
standing disclaimer:

```
All figures are modeled estimates from public pricing and observed
configuration, not billing statements. Reservation purchases are 12-month
commitments; confirm figures against the AWS console before purchasing.
```

## Step 8: Misestimation check (mandatory before every report)

- [ ] Every rate traced to a validated pricing snapshot, none from memory
- [ ] Tiered rates summed tier by tier, never multiplied at the first-tier
      marginal rate
- [ ] Resource state checked before assuming a resource bills (STANDBY,
      IDLE, stopped router I/O)
- [ ] Idle push inputs distinguished from idle pull inputs on MediaLive
- [ ] Existing reservations netted out of modeled current cost
- [ ] Every recommendation passed its Step 6 gate
- [ ] Every inter-service hop checked against data-transfer-map.md
- [ ] InputSpecification compared against the actual source for every
      running MediaLive channel
- [ ] H.264 outputs checked for INITIALIZE_FROM_SOURCE framerate control
- [ ] Duplicate ladders across output groups counted as separate outputs
- [ ] MediaConnect MaxBitrate NOT presented as a TS cost lever (flat rate)
- [ ] Router migration only recommended for flows on Router-supported
      protocols (RTP, RIST, SRT)
- [ ] Dimension discovery performed before every metric query
- [ ] No Cost Explorer calls made

## Out of scope

- Executing any mutation or purchase. This skill is read-only by design;
  do not perform the operator actions it maps to even if asked, and even
  if the agent's role would allow them. Present the action and let the
  customer execute it through their own change process.
- General (non-media) AWS cost review. EC2, S3 storage classes, and
  similar belong to other tooling; mention only where a media workload
  directly drives them (e.g., CloudWatch Logs from encoders).
- Sales-negotiated pricing (multi-year MediaLive terms, MediaPackage and
  CloudFront volume commitments). Flag eligibility; never price them.
- The cost of running the DevOps Agent itself. This is a real operational
  cost of the agent, but it is not part of the customer's media pipeline
  spend and is not modeled here.
