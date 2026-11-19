# MediaLive Cost Levers

## Contents

1. Billing model
2. Lever: input specification right-sizing (zero-tradeoff)
3. Lever: reservations (the primary commitment lever)
4. Lever: stop scheduling for non-24/7 channels
5. Lever: channel class downgrade
6. Lever: idle push input cleanup
7. Lever: output ladder right-sizing and framerate provisioning
8. Existing reservation audit
9. Operator action mapping

## 1. Billing model

A running MediaLive channel bills hourly for:

- each **input** (rate varies by input type, codec, bitrate tier, resolution)
- each **output** (rate varies by codec, resolution, frame rate, bitrate
  tier; UHD/HEVC outputs cost an order of magnitude more than HD/AVC)
- **add-on features** charged once per channel (advanced audio, audio
  normalization, motion graphics overlay)

Duration rounds up to the nearest minute with a 10-minute minimum per run.
A RUNNING channel with no content flowing bills exactly like one carrying
content. Data transfer to same-region MediaPackage is not a MediaLive
line item; cross-AZ MediaConnect legs can be (see data-transfer-map.md).

**Per-output billing**: each `Output` in each `OutputGroup` is a billed
encode-hour. Two outputs in different groups referencing the same
`VideoDescription` bill twice; sharing the encode does not share the
charge.

**Class multiplier**: AWS's own STANDARD vs SINGLE_PIPELINE examples put
STANDARD at roughly 1.67x per resource (input, output, and add-on alike).
This is derived from published examples, not a stated multiplier; the
snapshot carries the real pair.

**Idle behavior**: a channel in IDLE state bills a nominal idle charge
(illustration ~$0.01/hr), and attached **push inputs** (`UDP_PUSH`,
`RTP_PUSH`, `RTMP_PUSH`, `MEDIACONNECT`, `MEDIACONNECT_ROUTER`,
`INPUT_DEVICE`, `AWS_CDI`, `SRT_LISTENER`, `MULTICAST`,
`SMPTE_2110_RECEIVER_GROUP`, `SDI`) accrue idle-input charges while the
channel is stopped. **Pull inputs** (`URL_PULL`, `RTMP_PULL`, `MP4_FILE`,
`TS_FILE`, `SRT_CALLER`) do not bill while idle. The offer file carries
distinct idle usage-type SKUs; match rates to observed state.

**Input switching**: with more than one input attached, the channel bills
two active inputs regardless of how many are attached.

Billing-relevant fields from `describe-channel` and `describe-input`:

| Field | Why it matters |
|---|---|
| `ChannelClass` | STANDARD bills two pipelines; SINGLE_PIPELINE bills one |
| `State` | RUNNING bills; IDLE bills only push inputs |
| `EncoderSettings.VideoDescriptions[].CodecSettings` | codec per output (AVC/HEVC/AV1) drives output rate |
| `EncoderSettings.VideoDescriptions[].Width/Height` | resolution tier (SD/HD/UHD) |
| max bitrate and frame rate per output | rate tier; watch the >30fps threshold |
| `InputSpecification.Codec` / `.MaximumBitrate` / `.Resolution` | THE input rate-tier selector (`MPEG2`/`AVC`/`HEVC`, `MAX_10_MBPS`/`MAX_20_MBPS`/`MAX_50_MBPS`, `SD`/`HD`/`UHD`); set once, applies to every attached input, bills every running hour at the declared tier |
| `CdiInputSpecification.Resolution` | CDI input tier (`SD`/`HD`/`FHD`/`UHD`) |
| `InputAttachments[]` -> `describe-input.Type` | push vs pull idle behavior |
| `H264Settings.FramerateControl` | `INITIALIZE_FROM_SOURCE` provisions the 30-60fps tier; `SPECIFIED` with explicit numerator/denominator bills what is configured |

## 2. Lever: input specification right-sizing

The single most common zero-tradeoff finding. `InputSpecification` is set
at channel creation, applies to all inputs, and selects the input SKU for
every running hour. It is routinely left at a generous default
(`MAX_50_MBPS`, `HEVC`, `UHD`) for sources that never approach it.

Procedure:

1. Read `InputSpecification` from `describe-channel`.
2. Establish the actual source: for `MEDIACONNECT` inputs, the feeding
   flow's `Source.Transport.MaxBitrate` is a ceiling and `SourceBitRate`
   over the lookback window is the evidence; for other push/pull inputs,
   the MediaLive `InputVideoFrameRate`, `InputVideoWidth`/`Height` (where
   emitted) and the customer's contribution encoder settings.
3. Map source to the minimum tier that covers it with headroom the
   customer accepts (a source peaking above the declared bitrate tier is
   rejected at ingest, so headroom is not optional, it is just not 5x).
4. Model: running hours x (declared-tier input rate - covering-tier input
   rate) from the snapshot, per pipeline.

Tradeoff: none in quality. The customer gives up headroom for a future
higher-bitrate contribution and must accept a channel update to change
the specification. Confidence HIGH when `SourceBitRate` is measured;
MEDIUM when inferred from configuration alone.

## 3. Lever: reservations

Reservations are 12-month, no-upfront hourly commitments purchased per
input, output, or add-on attribute set, in a specific region. AWS states
savings up to 75% vs on-demand; the AWS worked example prices the same HD
standard channel at $2,414.88/month on-demand vs $564.12/month reserved.

Mechanics that shape recommendations:

- A reservation matches by **attribute set** (`resourceSpecification`:
  channelClass, codec, maximumBitrate, maximumFramerate, resolution,
  resourceType, specialFeature, videoQuality) and region, NOT by channel
  ARN. Delete and recreate a matching channel and the reservation still
  applies.
- Billed monthly for the committed hours whether used or not; **unused
  reserved minutes do not roll over**.
- **Break-even is approximately 180 running hours per month**: at a
  roughly 75% discount, a reservation costs about 25% of 720 on-demand
  hours, i.e. ~180 hours. Above that sustained utilization the
  reservation wins.
- Auto-renewal is configurable; note its state in the audit (section 7).
- The 30fps vs 30-60fps tiers are distinct offerings. A channel set to
  initialize from source provisions >30fps: it needs the higher tier
  reservation to match.

Recommendation procedure:

1. From Step 3 usage estimation, take sustained running hours/month per
   channel, split by pipeline count (STANDARD = 2x pipeline hours for
   inputs/outputs priced per pipeline).
2. Group running inputs/outputs by attribute set.
3. For each attribute set with >= 180 sustained hours/month, find the
   matching offering:

```
aws medialive list-offerings --no-cli-pager --output json \
  --channel-class $CLASS --resolution $RES --codec $CODEC \
  --maximum-bitrate $TIER
aws medialive describe-offering --offering-id $ID \
  --no-cli-pager --output json
```

4. Model: on-demand monthly cost (hours x on-demand rate from the pricing
   snapshot) vs reserved monthly cost (from the offering's
   `FixedPrice`/`UsagePrice` fields, cross-checked against the Reserved
   terms in the pricing snapshot).
5. Gate: sustained across the lookback window, not event-driven or
   seasonal. If usage is bursty, say so and do not recommend.
6. Order of operations: right-size the input specification (section 2)
   BEFORE sizing reservations; a reservation bought at an over-provisioned
   tier locks the waste in for 12 months.

## 4. Lever: stop scheduling

For channels that run 24/7 but carry content only in recurring windows
(regional events, business-hours programming), stopping the channel
outside those windows saves the full channel hourly cost minus idle push
input charges.

Detection: usage estimation (Step 3) shows recurring multi-hour spans of
zero `NetworkOut` datapoints or near-zero `ActiveOutputs`, while the
channel remains RUNNING throughout.

Modeling: stopped hours x (sum of input+output+add-on hourly rates),
minus stopped hours x idle rates for attached push inputs.

Mechanism to recommend (customer-implemented, AWS-native): EventBridge
Scheduler invoking `medialive:StartChannel` / `medialive:StopChannel` on
cron expressions, optionally via the AWS reference architecture (Step
Functions + Lambda). EventBridge Scheduler's free tier makes the
mechanism itself effectively free. The MediaLive in-channel schedule
(`BatchUpdateSchedule`) switches inputs and inserts actions but does NOT
stop billing; do not present it as a cost lever.

Gate: customer confirms the channel is not required as hot standby and
that startup latency (typically a couple of minutes to RUNNING) is
acceptable for their operation.

## 5. Lever: channel class downgrade

STANDARD runs two pipelines in two AZs and bills both. SINGLE_PIPELINE
bills one. Where redundancy is genuinely not required, downgrading cuts
per-resource cost by roughly 40% (STANDARD is ~1.67x single, per AWS
examples). Evidence that redundancy is not consumed: MediaPackage
`IngressBytes` on only one of the channel's two ingest endpoints, or a
downstream that has no second-pipeline path at all. The Well-Architected Streaming Media Lens
explicitly endorses single-pipeline for workloads without redundancy
requirements.

Never recommend from modeling alone: this trades resilience for money.
Present the saving, name the tradeoff (loss of automatic pipeline
failover), and gate on explicit customer confirmation. Note
`UpdateChannelClass` exists for the operator path, and that downstream
consumers (MediaPackage ingest expecting two pipelines) must be checked
before any such change.

## 6. Lever: idle push input cleanup

Inputs attached to long-idle channels, or orphaned push inputs attached
to nothing, accrue idle charges indefinitely. List inputs, join against
channel attachments and states, and flag push inputs that have been idle
for the full lookback window. Modeled saving: idle hours x idle input
rate. Operator mapping: `DeleteInput` (or detach), after customer
confirms the input is not being kept warm deliberately.

## 7. Lever: output ladder right-sizing and framerate provisioning

Output cost scales steeply with codec, resolution, and frame rate. Flag,
as questions rather than directives:

- UHD or >30fps outputs whose downstream packaging or player population
  may not use them
- duplicate renditions across output groups
- AVC ladders where HEVC/QVBR consolidation could cut delivery bytes
  (note: HEVC output hours cost more than AVC; the saving shows up in
  MediaPackage egress and CloudFront delivery, so model end to end, not
  per service)

Two zero-tradeoff checks belong here as well:

- **Framerate provisioning**: any H.264 output with
  `FramerateControl=INITIALIZE_FROM_SOURCE` is provisioned and billed at
  the 30-60fps tier even for 30fps content. Recommend `SPECIFIED` with the
  actual frame rate. (HEVC, AV1, and MPEG-2 settings require explicit
  numerator/denominator, so the trap is H.264-specific.)
- **Duplicate ladders**: count `Outputs[]` across all `OutputGroups[]`. A
  full ladder repeated in an HLS group, a MediaPackage group, and an RTMP
  group is billed three times. Ask which groups still have consumers.

Rate control (`RateControlMode` QVBR vs CBR) does not change the MediaLive
rate but QVBR reduces delivered bytes downstream; model that saving in the
MediaPackage and CloudFront references, not here.

These are architecture conversations. Present the per-output hourly rates
from the snapshot and let the customer weigh them.

## 8. Existing reservation audit

```
aws medialive list-reservations --no-cli-pager --output json
aws medialive describe-reservation --reservation-id $ID \
  --no-cli-pager --output json
```

For each ACTIVE reservation, verify some running resource's attribute set
matches it. An unmatched reservation is committed spend with zero
utilization: report it prominently. Check `RenewalSettings`: an
auto-renewing reservation for a decommissioned workload silently renews
the waste for another year. Also flag EXPIRED reservations whose workload
still runs >= 180 hours/month (a repurchase recommendation).

## 9. Operator action mapping

| Recommendation | Operator action (NOT EXECUTED by this skill) |
|---|---|
| Purchase reservation | `medialive:PurchaseOffering` with offering ID, count, name |
| Stop schedule | customer-deployed EventBridge Scheduler calling `medialive:StopChannel`/`StartChannel` |
| Class downgrade | `medialive:UpdateChannelClass` (channel must be IDLE; verify downstream ingest) |
| Idle input cleanup | `medialive:DeleteInput` |
| Input specification downgrade | `medialive:UpdateChannel` with new `InputSpecification` (channel must be IDLE) |
| Framerate SPECIFIED | `medialive:UpdateChannel` EncoderSettings change (channel must be IDLE) |
| Cancel auto-renewal | `medialive:UpdateReservation` renewal settings |
