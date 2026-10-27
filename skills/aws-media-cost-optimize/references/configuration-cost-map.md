# Configuration-to-Cost Map

How each configuration attribute on a Media Services resource selects a
billing tier or family, what the cheaper setting gives up, and what a
misconfiguration looks like in a describe response. Field names verified
against botocore service models (medialive 2017-10-14, mediaconnect
2018-11-14) at authoring time; rates are us-east-1 illustrations from AWS
pricing page examples and CUR usage-type catalogs, to be replaced by the
live pricing snapshot at run time.

## Contents

1. How to use this map
2. MediaLive: inputs
3. MediaLive: outputs and add-ons
4. MediaConnect: flows
5. MediaConnect: Router
6. MediaPackage
7. CloudFront
8. MediaTailor
9. Cross-service coherence checks
10. us-east-1 sanity-check rate table
11. Verification status

## 1. How to use this map

For every resource in the inventory, read the listed fields from the
describe response and map them to a tier. Then ask two questions:

1. Does the tier match what the source or audience actually needs?
   (over-provisioning: paying for a tier the content never uses)
2. If the customer moved to the cheaper tier, what would they lose?
   (the tradeoff column; never recommend a downgrade without naming it)

Findings from this map feed the "configuration coherence" section of the
report as questions, in the Observed/Expected/Question form.

## 2. MediaLive: inputs

The channel-level `InputSpecification` is THE input rate-tier selector.
It is set once and applies to every input attached to the channel; every
running hour bills at the tier it declares, regardless of what the source
actually delivers.

| Field (describe-channel) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `InputSpecification.Codec` | `MPEG2`, `AVC`, `HEVC` | selects input codec tier (HEVC > AVC > MPEG2) | ability to ingest a source in that codec | codec tier higher than the actual source codec (from the feeding flow or the customer) |
| `InputSpecification.MaximumBitrate` | `MAX_10_MBPS`, `MAX_20_MBPS`, `MAX_50_MBPS` | selects input bitrate tier (CUR usage types end in `-L10`, `-L20`, `-L50`) | headroom for a higher-bitrate source | tier is one or two steps above the observed source bitrate; a 10 Mbps HD contribution on `MAX_50_MBPS` over-bills every hour |
| `InputSpecification.Resolution` | `SD`, `HD`, `UHD` | selects input resolution tier | ability to ingest higher resolution | `UHD` declared for a 1080p source |
| `CdiInputSpecification.Resolution` | `SD`, `HD`, `FHD`, `UHD` | CDI input tier | same | tier above the actual CDI stream size |
| `ChannelClass` | `STANDARD`, `SINGLE_PIPELINE` | STANDARD bills both pipelines; AWS examples put STANDARD at ~1.67x the single-pipeline rate per resource (derived, not a stated multiplier) | STANDARD gives two AZs and automatic pipeline failover | STANDARD channel whose downstream consumes only one pipeline (see coherence checks) |
| `InputAttachments[].InputId` -> `describe-input.Type` | push: `UDP_PUSH`, `RTP_PUSH`, `RTMP_PUSH`, `MEDIACONNECT`, `MEDIACONNECT_ROUTER`, `INPUT_DEVICE`, `AWS_CDI`, `SRT_LISTENER`, `MULTICAST`, `SMPTE_2110_RECEIVER_GROUP`, `SDI`; pull: `RTMP_PULL`, `URL_PULL`, `MP4_FILE`, `TS_FILE`, `SRT_CALLER` | push inputs accrue an idle-input charge (~$0.01/hr illustration) while the channel is IDLE; pull inputs do not | none directly; input type is dictated by the contribution path | push inputs attached to long-idle channels, or orphaned push inputs |
| number of attached inputs | n | with input switching (>1 input) the channel bills two active inputs regardless of how many are attached | fewer attached inputs means fewer switch targets | more than two attached inputs is not extra cost, but confirm the customer expects two input-hours billed |
| `LogLevel` | `ERROR`, `WARNING`, `INFO`, `DEBUG`, `DISABLED` | no MediaLive charge; CloudWatch Logs ingestion scales with verbosity | diagnostic depth (aws-medialive-investigate needs at least WARNING for alert detail) | `DEBUG` left on in steady state on busy channels |

Resolution boundaries AWS uses for tiering: SD below 720 lines, HD 720
to 1080, UHD above 1080 to 2160 (CDI adds FHD for exactly 1080).

## 3. MediaLive: outputs and add-ons

Outputs bill per output, per running hour, by codec x resolution x
frame-rate tier x bitrate tier. Two outputs referencing the same
`VideoDescription` in different output groups bill twice; the encode
being shared does not reduce the charge.

| Field (describe-channel EncoderSettings) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `VideoDescriptions[].CodecSettings` (which of `H264Settings`, `H265Settings`, `Av1Settings`, `Mpeg2Settings`) | AVC, HEVC, AV1, MPEG-2 | HEVC HD output ~4x AVC HD (illustration $2.808 vs $0.702/hr STANDARD); UHD HEVC ~$11.23/hr | HEVC/AV1 give lower delivery bytes at the same quality, so the saving may reappear downstream in MediaPackage/CloudFront; model end to end | HEVC outputs feeding players that only decode AVC |
| `VideoDescriptions[].Width` / `Height` | pixels | resolution tier (SD/HD/UHD boundaries above) | top-of-ladder quality | UHD rendition where no downstream path delivers UHD |
| `H264Settings.FramerateControl` | `INITIALIZE_FROM_SOURCE`, `SPECIFIED` | `INITIALIZE_FROM_SOURCE` makes MediaLive provision for >30fps and bill the 30-60fps tier even when actual is 30fps (H.264 only; HEVC/AV1/MPEG-2 require explicit numerator/denominator) | nothing: set `SPECIFIED` with explicit `FramerateNumerator`/`FramerateDenominator` | any H.264 output on `INITIALIZE_FROM_SOURCE` |
| `H264Settings`/`H265Settings` `FramerateNumerator`/`Denominator` | e.g. 30/1, 60/1 | >30fps selects the higher frame-rate tier | motion smoothness for sports | 60fps ladders for talking-head or slate content |
| `*Settings.Bitrate` / `MaxBitrate` | bps | bitrate tier per output (CUR `-L10`/`-L20`/`-L50` bands) | headroom | rendition max bitrate sitting just over a band boundary |
| `*Settings.RateControlMode` | `CBR`, `VBR`, `QVBR`, `MULTIPLEX` | no MediaLive rate change; QVBR reduces average bytes delivered downstream (AWS cites 10-50%) | CBR gives predictable bandwidth for some contribution paths | CBR ladders feeding OTT delivery where QVBR would cut MediaPackage/CloudFront bytes |
| `OutputGroups[].Outputs[]` count | n | each output is a billed encode-hour | rendition granularity | duplicate ladders across output groups (HLS + MediaPackage + RTMP each carrying the full ladder) |
| `EncoderSettings.AudioDescriptions[]` codec | AAC vs Dolby (DD/DD+/Atmos), DTS | Dolby/DTS trigger the advanced-audio add-on (once per channel, ~$0.30/hr STANDARD illustration) | surround/premium audio | advanced audio codecs on channels whose players consume stereo AAC |
| audio normalization settings | ITU-R BS.1770 loudness | audio-normalization add-on once per channel | CALM Act / loudness compliance | enabled where not a compliance requirement |
| `EncoderSettings.MotionGraphicsConfiguration.MotionGraphicsInsertion` | ENABLED/DISABLED | motion graphics add-on, billed at the largest resolution in the channel (reservation SpecialFeature `MGHD` / `MGUHD`) | dynamic overlays | enabled but no overlays ever inserted |
| `EncoderSettings.NielsenConfiguration`, `ThumbnailConfiguration.State`, KLV passthrough | present/enabled | per-channel line items exist for some (Nielsen watermarking); thumbnails and KLV should be verified against the live snapshot | measurement / preview / metadata | UNVERIFIED individually; check the snapshot before quantifying |
| reservation `ResourceSpecification.VideoQuality` | `STANDARD`, `ENHANCED`, `PREMIUM` | enhanced/premium VQ output tiers price higher | encoder quality mode | premium VQ on renditions where standard is visually sufficient |

## 4. MediaConnect: flows

Protocol selects the billing FAMILY; bitrate mostly does not.

| Field (describe-flow) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `Source.Transport.Protocol` | TS family: `zixi-push`, `zixi-pull`, `srt-caller`, `srt-listener`, `rist`, `rtp`, `rtp-fec`, `udp`; uncompressed: `cdi`, `st2110-jpegxs`; `ndi-speed-hq`; deprecated `fujitsu-qos` | TS family = flat flow hourly + per-GB transfer; CDI/JPEG XS = flow hourly tiered by video size + per-output hourly; NDI = flow hourly (needs LARGE flow), NDI outputs free in-VPC | family is dictated by the workflow, not chosen for price | protocol with ARQ/FEC (Zixi, SRT, RIST, RTP-FEC) on per-GB internet outputs: retransmission overhead is billable bytes; report it, do not "fix" it |
| `Source.Transport.MaxBitrate` | bps | NO effect on the TS flow hourly rate (AWS bills 10, 30, and 50 Mbps TS flows identically); only actual GB transferred costs more | nothing | far above the observed source bitrate: misconfiguration signal, zero cost impact for TS |
| `FlowSize` | `MEDIUM`, `LARGE`, `LARGE_4X` | does not change the TS hourly rate; gates capabilities (LARGE required for NDI and higher aggregate output bandwidth; LARGE_4X for uncompressed up to UHD 2160p60) | MEDIUM caps output count and aggregate throughput, no NDI | LARGE without NDI outputs and with modest output counts (harmless to cost today, but confirm intent) |
| max video size (CDI/JPEG XS) via `MediaStreams[]` attributes | SD, 1080i, 1080p, UHD | sets the uncompressed flow tier (illustrations: 1080i $3.00/hr, 1080p $6.00/hr) and per-output rate ($0.13 to $0.30/hr) | resolution | tier above what the production actually switches |
| `Outputs[].Protocol` + destination | TS to in-region AWS / cross-region / internet; CDI outputs; NDI outputs | TS: per-GB by destination (~$0.01 / $0.02 / $0.09); CDI: per-output-hour; NDI: no transfer charge | destination is a workflow fact | internet-destined TS outputs on 24x7 flows without reserved outbound bandwidth; CDI outputs left configured on idle production paths |
| `Outputs[].Destination` AZ vs MediaLive channel AZ | same/different | different AZ adds cross-AZ transfer on every hour, always for statmux | co-location constraints | flow AZ != channel input AZ |
| `SourceFailoverConfig.FailoverMode` + `Sources[]` count | `FAILOVER`, `MERGE`; 1 or 2 sources | a second source on one flow does not double the flow hourly rate (two flows would); MERGE requires two aligned sources | FAILOVER = brief switch; MERGE = hitless but two full ingress paths | two separate flows doing what one two-source flow could |
| `Entitlements[].DataTransferSubscriberFeePercent` | 0-100 | percentage of the entitlement transfer fee billed to the subscriber; originator pays the rest | commercial allocation, not a saving | split inconsistent with the commercial agreement |
| `SourceMonitoringConfig`, `VpcInterfaces[]` | configured/absent | no separate published MediaConnect line item for content quality analysis; VPC interfaces create ENIs (standard VPC cost) | monitoring signal aws-mediaconnect-investigate uses | not a cost lever; do not recommend disabling monitoring to save money |
| `Status` | `ACTIVE`, `STANDBY`, others | STANDBY bills nothing | warm path availability | ACTIVE with no source bitrate across the window |

Reserved outbound bandwidth offerings (`list-offerings`,
`ResourceSpecification.ResourceType=Mbps_Outbound_Bandwidth`, `PriceUnits=HOURLY`,
`DurationUnits=MONTHS`) are sold at fixed tiers (50/150/500/1500 Mbps in
AWS materials); one active reservation per account per region.

## 5. MediaConnect: Router

| Field (get-router-input / -output) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `Tier` | inputs `INPUT_20`, `INPUT_50`, `INPUT_100`; outputs `OUTPUT_20`, `OUTPUT_50`, `OUTPUT_100` | hourly rate per active input/output by tier (100 Mbps illustration: input $0.14/hr, output $0.10/hr; 20/50 tiers UNVERIFIED, take from snapshot) | headroom; an output's max bitrate must be >= the input routed to it | tier above the observed stream bitrate |
| `MaximumBitrate` | bps | must fit the tier; does not itself set the rate | | |
| `State` | `STANDBY`, `ACTIVE`, others | only ACTIVE bills; stopped/standby I/O bill nothing | | ACTIVE outputs with `RoutedState` unrouted or `RoutedInputArn` empty |
| `RoutingScope` | `REGIONAL`, `GLOBAL` | GLOBAL enables cross-region outputs, which carry a per-hour cross-region add-on (illustration ~$0.28/hr running + data-in) | cross-region reach | GLOBAL scope on inputs whose outputs are all in-region |
| output destination internet vs AWS | | internet egress add-on per output-hour (100 Mbps illustration +$1.79/hr) | | internet outputs left ACTIVE between events |
| protocol support (`RouterInputProtocol` / `RouterOutputProtocol`) | `RTP`, `RIST`, `SRT_CALLER`, `SRT_LISTENER` only | not a rate, a feasibility gate: Zixi, UDP, CDI, JPEG XS, NDI, and Fujitsu flows have no direct Router equivalent | | Flows-to-Router migration recommended for a flow using an unsupported protocol |
| `InputType` / `OutputType` | inputs `STANDARD`, `FAILOVER`, `MERGE`, `MEDIACONNECT_FLOW`, `MEDIALIVE_CHANNEL`; outputs `STANDARD`, `MEDIACONNECT_FLOW`, `MEDIALIVE_INPUT` | Router can front a MediaLive input directly (MediaLive input type `MEDIACONNECT_ROUTER`), removing a flow hop | | flow-then-router chains where the router could feed MediaLive directly |

## 6. MediaPackage

| Field | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| v1: one `OriginEndpoint` per packaging type | HLS, DASH, CMAF, MSS | each endpoint's egress bills separately when consumed | format coverage | four packaging types where one is consumed |
| v2: `OriginEndpoint` with `HlsManifests[]`, `LowLatencyHlsManifests[]`, `DashManifests[]`, `MssManifests[]` over one `Segment` config, `ContainerType` `TS`/`CMAF` | multiple manifests, one segment set | segments packaged once and shared by all manifest types; you pay egress per delivered GB, not per format | nothing at the format level; migration effort | v1 endpoint-per-format estates that could consolidate on v2 |
| `StartoverWindowSeconds` (v1, v2 up to 1,209,600) | seconds | no separate storage line item; longer window is not a rate change | | not a lever; do not recommend shortening for cost |
| DRM / SPEKE encryption | configured | no MediaPackage per-request surcharge; SPEKE key server and Secrets Manager cost sit on the customer side | | not a lever |
| ingest pipelines (`Channel.IngestEndpoints`, two per channel) | one or two MediaLive pipelines pushing | STANDARD MediaLive feeding both = ~2x ingest GB (by design for redundancy) | ingest redundancy | STANDARD MediaLive channel where only one ingest endpoint receives data (see coherence) |
| egress destination | CloudFront vs internet/other CDN | to CloudFront: transfer free (origination still bills); to internet or a non-CloudFront CDN: internet data transfer applies | | third-party CDN pulling from MediaPackage without an intermediate CloudFront |
| segment duration at endpoint vs MediaLive | seconds | mismatch causes repackaging | | different values at encoder and packager |

## 7. CloudFront

| Field (get-distribution-config / cache policy) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `CacheBehaviors[]` split by path pattern | manifests (`*.m3u8`, `*.mpd`) vs segments (`*.ts`, `*.m4s`, `*.cmf*`) | separate behaviors let manifests stay short-TTL and compressed while segments cache long/immutable; one behavior collapses hit ratio and drives MediaPackage egress + origin-request fees | nothing | single default behavior serving both |
| `CachePolicyConfig.ParametersInCacheKeyAndForwardedToOrigin.QueryStringsConfig` / `HeadersConfig` / `CookiesConfig` | which keys included | session tokens or per-viewer headers in the SEGMENT cache key make every viewer a miss | | tokens in query strings on segment behaviors; whole-header forwarding |
| `EnableAcceptEncodingGzip` / `Brotli` | on/off on the manifest behavior | manifests compress well; segments do not | | compression off on manifest behavior |
| `MinTTL`/`DefaultTTL`/`MaxTTL` per behavior | seconds | manifests need TTL near the segment duration; segments should be long | | inverted TTLs (long manifests, short segments) |
| `Origins[].OriginShield` | enabled + region | incremental per-request fee (~$0.009 per 10k US/EU illustration); pays above ~50% behavior hit ratio | origin protection during peaks | enabled at low hit ratio; region not the origin's |
| `PriceClass` | `PriceClass_100`, `_200`, `_All` | excluding expensive geographies cuts blended egress; audience outside the class served from farther edges | latency/first-byte for excluded regions | global-class distribution with a regional audience |
| segment duration (pipeline-wide) | 2s vs 4-6s | each viewer fetches ~1 manifest + 1 segment per segment duration: 2s = ~30 GET/min/viewer, 6s = ~10; request fees (~$0.010 per 10k HTTPS US illustration) scale 3x, plus more origin fetches on misses | latency (shorter = lower) | 2s segments where low latency is not a requirement |
| real-time logs, standard logs, `GetMonitoringSubscription` additional metrics | configured | real-time logs bill per million lines to Kinesis; additional metrics bill per metric | observability aws-media-cloudfront-investigate uses (`CacheHitRate` needs additional metrics) | real-time logs outliving an investigation; do NOT recommend removing additional metrics |
| edge auth: CloudFront Functions vs Lambda@Edge | per-invocation | Functions ~$0.10/1M invocations vs Lambda@Edge ~$0.60/1M plus duration (illustrations) | Lambda@Edge capabilities (network calls, longer logic) | Lambda@Edge doing simple token checks at live scale |

Request arithmetic example: 10,000 concurrent viewers on 2s segments =
10,000 x 30 x 60 = 18M requests/hour, ~$18/hour in US HTTPS request
fees at the illustration rate; ~$6/hour at 6s. Present alongside egress,
never instead of it.

## 8. MediaTailor

| Field (get-playback-configuration) | Values | Cost effect | Cheaper option gives up | Flag when |
|---|---|---|---|---|
| `TranscodeProfileName` | custom transcode profile or unset (dynamic) | matching creatives to the origin profile avoids overage transcodes beyond the 10-per-1000 allowance; a mismatched CTP causes `NO_VARIANT_MATCH` errors (ads fail, not cost) | flexibility of dynamic transcoding | frequent transcode overage with a static creative pool |
| `LogConfiguration.PercentEnabled` | 0-100 | log volume scales linearly; 50 KB per insertion included | per-session investigability | 100% in steady state at scale |
| `PersonalizationThresholdSeconds`, prefetch schedules, ADS timeouts | seconds | affect ADS call volume and log volume, not the per-insertion rate | ad fill behavior | prefetch scope wider than actual break patterns |
| manifest vs segment cache behaviors at CloudFront | | personalized manifests are per-session and uncacheable; segments remain cacheable and must live on a separate behavior | | one behavior in front of a MediaTailor session endpoint |

## 9. Cross-service coherence checks

Run these against the discovered topology. Each is a question for the
report, phrased Observed/Expected/Question, never a directive.

| Check | Fields compared | Waste pattern |
|---|---|---|
| Input tier vs source | MediaLive `InputSpecification.{Codec,MaximumBitrate,Resolution}` vs feeding flow `Source.Transport.MaxBitrate` and observed `SourceBitRate`, source codec/resolution | tier one or more steps above the source: over-bills every running hour |
| Pipeline count vs consumption | MediaLive `ChannelClass=STANDARD`, `PipelinesRunningCount`; MediaPackage per-ingest-endpoint `IngressBytes` | STANDARD paid, one pipeline consumed |
| Ladder vs delivery | MediaLive top rendition resolution/frame rate vs MediaPackage manifest renditions actually requested (access logs or `EgressRequestCount` by rendition where available) vs player population | UHD/60fps outputs nobody fetches |
| Duplicate ladders | MediaLive `OutputGroups[]` referencing the same `VideoDescriptions` | full ladder billed N times |
| Framerate provisioning | H.264 `FramerateControl=INITIALIZE_FROM_SOURCE` | 30-60fps tier for 30fps content |
| Flow AZ vs channel AZ | flow `AvailabilityZone` vs MediaLive input attachment / pipeline AZ | cross-AZ transfer every hour, always for statmux |
| Segment duration alignment | MediaLive output group segment length vs MediaPackage endpoint segment duration | repackaging |
| Format sprawl | MediaPackage v1 endpoints per channel vs consumed formats | egress on unconsumed formats |
| Cache behavior split | CloudFront behaviors vs manifest/segment path patterns | hit-ratio collapse |
| Router protocol feasibility | flow `Source.Transport.Protocol` vs Router protocol set | migration recommended for an unsupported protocol |
| Advanced audio vs consumption | Dolby/DTS audio descriptions vs player audio capability | add-on paid for stereo audiences |

## 10. us-east-1 sanity-check rate table

Illustrations only, for verifying that Price List parsing landed on the
right SKU family. Never quote these in a report; quote the snapshot.

| Resource | Illustration |
|---|---|
| MediaLive input HD HEVC 20 Mbps, STANDARD / single | $0.588 / $0.3528 per hour |
| MediaLive output AVC 1080p 5 Mbps 30fps, STANDARD / single | $0.702 / $0.4212 per hour |
| MediaLive output AVC SD 30fps STANDARD | $0.354 per hour |
| MediaLive output HEVC 720p / 1080p / 2160p 30fps STANDARD | $1.41 / $2.808 / $11.232 per hour |
| MediaLive advanced audio add-on STANDARD / single | $0.30 / $0.18 per hour |
| MediaLive idle channel, idle push input | ~$0.01 per hour each |
| MediaLive Link input HD / UHD | $0.50 / $4.583 per hour |
| MediaConnect TS flow | $0.16 per hour, flat |
| MediaConnect NDI flow (LARGE) | $1.50 per hour |
| MediaConnect CDI/JPEG XS 1080p flow / per output | $6.00 / $0.30 per hour |
| MediaConnect TS transfer in-region / cross-region / internet | $0.01 / $0.02 / $0.09 per GB |
| MediaConnect reserved outbound 50 Mbps | $1.161 per hour (~$0.052/GB) |
| MediaConnect Router 100 Mbps input / output / internet add-on | $0.14 / $0.10 / +$1.79 per hour |
| MediaPackage live ingest / origination | ~$0.03 / ~$0.05 per GB |
| MediaTailor live / VOD insertions | $0.50 / $0.25 per 1,000 |
| MediaTailor Channel Assembly basic / standard | $0.10 / $0.35 per hour |
| CloudFront US egress first tier / HTTPS requests | ~$0.085 per GB / ~$0.010 per 10k |
| CloudFront Origin Shield US/EU | ~$0.009 per 10k requests |

## 11. Verification status

Verified against botocore models at authoring: every enum and member
name in sections 2 to 5 (`InputSpecification`, `CdiInputSpecification`,
`InputType` including `MEDIACONNECT_ROUTER`/`SDI`/`SRT_LISTENER`,
`H264FramerateControl`, `ReservationResourceSpecification` fields and
enums including `MGHD`/`MGUHD`/`AV1`/`FHD`, `FlowSize` including
`LARGE_4X`, `Protocol` including `ndi-speed-hq`, `RouterInputTier`,
`RouterOutputTier`, `RoutingScope`, Router protocol and type enums,
`Offering` fields).

Derived, not stated by AWS: the ~1.67x STANDARD multiplier (ratio of
AWS's own STANDARD vs single-pipeline example prices).

UNVERIFIED against a primary rate table: Router 20/50 Mbps tier prices;
Nielsen/thumbnail/KLV per-channel charges; current MediaPackage per-GB
live-page rates (solution-guide figures used); Origin Shield fee for
non-US/EU regions. The live snapshot resolves all of these at run time.
