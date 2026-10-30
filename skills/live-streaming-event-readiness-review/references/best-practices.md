# LSE Readiness — best-practice checklist (canonical checks)

Single source of truth for check membership. Grade every applicable row
**PASS / FAIL / N/A** with evidence and severity. N/A requires an explicit
applicability or evidence reason. Use
[`remediations.md`](remediations.md) only after FAIL IDs are known. Sources:
`[P1]` = "Preparing for large-scale live streaming events on AWS" blog Part 1,
`[P2]` = same series Part 2, `[SML]` = Streaming Media Lens

Severity: 🔴 Critical · 🟠 High · 🟡 Medium · 🔵 Low.

## Highest-signal checks (load and surface first)

Before full grading, raise these headline discriminators for the relevant pillar so
the top risks appear even in a quick or one-shot review:

- **Capacity:** instance diversification across families/sizes/AZs; future-dated
  ODCRs; EKS control-plane provisioned mode; Lambda provisioned concurrency; LCU
  reservation; pre-provisioned minimums — never reactive autoscaling alone. For
  **EKS Auto Mode**, provisioning/diversification are AWS-handled but it still
  scales reactively, so require pre-scaled workloads + resource requests. A
  resource that exists but is not prepared for the peak (idle, default throughput,
  no pre-warm) is a finding, not a pass.
- **Quotas:** EC2 vCPU, NAT, Lambda, ELB headroom vs load-tested peak; raise early
  (some increases need AWS-team coordination).
- **Resilience:** multi-Region active-active critical path; Route 53 failover;
  service isolation; graceful-degradation hierarchy; no maintenance in the window;
  **no version at end-of-standard-support that could auto-upgrade or force-maintain
  in the window** (EKS / RDS / OpenSearch / ElastiCache / MSK / Lambda) — upgrade
  before the freeze or defer past the event.
- **Content delivery:** single consistent origin; Origin Shield on; cache-key
  normalization / strip query-string variation for a high cache-hit ratio on 2–6s
  segments; **CloudFront Functions** for lightweight high-frequency logic vs
  **Lambda@Edge** for heavier runtime work; origin failover; **MediaTailor (SSAI)**
  playback configurations prefetched for scheduled ad breaks with slate / graceful
  fallback when the ADS is slow or unavailable; **multi-CDN with client-side
  switching** for tier-1 events; **LL-HLS / CMAF** latency-vs-cache tradeoff
  understood where sub-5s latency is promised.
- **Networking:** NAT — PeakPacketsPerSecond (leading indicator, ~10M pps),
  ActiveConnectionCount (~55k/destination), ErrorPortAllocation (non-zero = at a
  ceiling), PacketsDropCount; TGW — BytesIn/Out as sustained bits/sec vs ~100 Gbps
  per attachment, PacketDropCountNoRoute/Blackhole for routing health. Pre-warm via
  Support only when projected peak reaches a large fraction of a ceiling faster than
  NAT's ~5-min reactive ramp (scheduled hard-start spike); organic growth needs none.
- **Data & state:** pre-warm DynamoDB/Keyspaces partitions and ElastiCache
  (Serverless ≥60 min before ramp); RDS read replicas / Aurora Serverless v2; cache
  session tokens; **DRM license-server capacity** confirmed with the key provider at
  projected peak and license-renewal windows staggered so renewals don't cluster at
  the spike. A table whose **warm throughput is below the event peak** (e.g. a
  new on-demand table at the 12,000 RCU / 4,000 WCU floor) is unprepared — flag it;
  an on-demand table already warmed to ≥ peak (previously provisioned high) is fine.
  Serverless/
  auto-scaling (ElastiCache Serverless, DynamoDB on-demand, Aurora Serverless v2,
  Lambda) scales incrementally over minutes — a steep step (e.g. >4× in <5 min)
  outpaces it, so pre-warm / pre-scale / raise the floor ahead of the event.
- **Testing & chaos:** staged gates — component → integration → full-scale
  production rehearsal at **1.3–1.5× peak** → spike+failure; a concrete ramp shape
  (≈60-min ramp, 2–3h sustain with 20–40% spikes, then decline) built from realistic
  viewer patterns (codec/protocol mix, join/leave rates, and load spread across
  multiple origin endpoints — not just single-origin concurrency); identity/signup
  surge and ad-decisioning tests; external dependencies (CDN, ad/ADS, origin vendors)
  and AWS service teams coordinated and signed off before the test; **AWS FIS with
  stop conditions** and steady state in viewer terms (VST < 3s, rebuffer < 0.5%,
  error < 0.1%) — dependency-latency injection and compute termination.
- **Observability:** viewer SLIs (VST, VSF, VPF, rebuffer ratio, error rate),
  correlated with CDN performance via CMCD in CloudFront real-time logs; measurable
  glass-to-glass success criteria with a warning/critical/failure threshold matrix
  signed off by stakeholders; **every critical-path service has an actionable alarm
  (CloudWatch or a declared third-party tool) — missing CloudWatch alarms is a gap
  only if no third-party tool covers it**; alarms onboarded and proven weeks ahead;
  the **telemetry / analytics backbone** (Kinesis / Firehose / MSK carrying CMCD,
  QoE beacons, and session heartbeats) has shard/throughput headroom for peak
  viewer volume so the signal doesn't degrade when it's most needed.
- **Support:** AWS account team + WAFR early; Unified Operations for Media (which
  includes IDR monitoring) / Countdown Premium; a documented, rehearsed event-day
  communication plan (Comms Manager, per-team designated reporters, fixed update
  cadence, bridge etiquette); change freeze ~1 week out, monitor-don't-deploy on
  event day; business-driven demand shaping; **live-captions / accessibility path**
  tested end-to-end (ingest → encode → packager → player; third-party captioning
  provider capacity confirmed) where captions are a regulatory or editorial
  requirement.

---

## Pillar CAP — Capacity & Scaling Readiness

Auto scaling reacts *after* thresholds are breached, so there is always a lag
between demand arriving and capacity appearing. For an LSE, that gap is closed by
pre-provisioning and layered capacity defenses, not by reactive scaling alone. `[P1]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| CAP1 | Instance diversification (primary defense) | ASG mixed-instances policy / Karpenter NodePool / ECS capacity providers | Provisioner accepts multiple instance families **and** sizes across multiple AZs — not a single type | 🟠 High |
| CAP2 | On-Demand Capacity Reservations as fallback | `ec2 describe-capacity-reservations`; future-dated reservations | Assured capacity reserved for the critical path; future-dated ODCRs (up to 120 days ahead) created for the event where diversification alone is insufficient | 🟠 High |
| CAP3 | EKS control plane pre-provisioned | EKS cluster scaling tier / provisioned mode | Control plane switched to provisioned mode ahead of the event so API server / controller / etcd are pre-allocated for mass pod scheduling at ramp | 🟠 High |
| CAP4 | Warm capacity & fast pod starts | pause pods / image size / SOCI / pre-pull DaemonSet | Low-priority pause pods hold spare capacity; images small; SOCI lazy-loading or pre-pull in place so new nodes serve traffic fast | 🟡 Medium |
| CAP5 | Lambda provisioned concurrency | `lambda get-provisioned-concurrency-config` | Latency-sensitive critical-path functions (token validation, authz, session create) have provisioned concurrency to remove cold starts in the event window | 🟠 High |
| CAP6 | Load Balancer LCU reservation | ELB capacity-unit reservation | Minimum LCU capacity reserved on load-tested peak **plus margin**; auto scaling continues above the reservation | 🟠 High |
| CAP7 | Pre-provisioned minimum capacity | ASG/Karpenter min size vs baseline | Critical-path min capacity raised ahead of the ramp rather than relying on reactive scaling to absorb the spike | 🟠 High |
| CAP8 | Capacity-planning timeline followed | S0 weeks-to-event + evidence of milestones | Milestones from `references/timeline` tracked with owners (see §timeline in report) | 🟡 Medium |
| CAP9 | EBS volume performance & initialization | `ec2 describe-volumes` (VolumeType/Iops/Throughput) + `ec2 describe-fast-snapshot-restores` | Event-critical EBS volumes are sized for peak IOPS/throughput (e.g. gp3 provisioned IOPS/throughput, not left at defaults), and any volume created from a snapshot for the event is **initialized** — Fast Snapshot Restore enabled, or blocks pre-read — so it does not hit first-access (lazy-load) I/O latency at the spike | 🟡 Medium |

**EKS Auto Mode branch (affects CAP1, CAP3, CAP4, CAP7).** If the cluster is EKS
Auto Mode (`cluster.computeConfig.enabled = true`), AWS manages node provisioning,
instance diversification, and lifecycle — so CAP1 and CAP4 are largely AWS-handled
and CAP3 (self-managed control-plane pre-provisioning) is N/A. Do **not** read that
as "capacity is ready." Auto Mode still provisions **reactively** with node-launch
latency, so grade these LSE residuals instead:
- Critical-path workloads must be **pre-scaled** before the ramp (raised replica
  minimums or scheduled scaling) — reactive Auto Mode provisioning alone lags a
  multi-x spike. An idle Auto Mode cluster with no pre-scaled workloads is a
  **FAIL (High)**, not N/A.
- Workloads must set **resource requests** so Auto Mode sizes and scales them.
- Image pull / pod startup time still gates how fast new capacity serves traffic.

**Readiness grading rule — applies to CAP and DAT: "present but unprepared" is a
FAIL, not N/A.** An event-critical compute pool or datastore that exists but is not
configured for the event peak (idle, default/minimum throughput, on-demand with no
pre-warm plan, no pre-scaled minimums) is a capacity **risk** for the spike, not a
blank. Grade it FAIL with the pre-event action. Reserve N/A for resources that are
genuinely absent or unreadable. Where the event peak is unknown, state the
assumption (S0) and grade against it rather than defaulting to N/A.

---

## Pillar QTA — Service Quotas & Limits

Review and raise quotas across the critical path **weeks** in advance — some
require coordination between internal AWS teams and cannot be fulfilled
overnight. `[P1]` **Delegate to `service-quota-check` for actual values.**

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| QTA1 | EC2 On-Demand vCPU headroom | `service-quota-check` | Applied vCPU quota ≥ load-tested peak vCPUs + margin in every event Region | 🟠 High |
| QTA2 | NAT / networking quotas | `service-quota-check` + NET pillar | NAT connections, EIPs, and related network quotas have headroom vs peak | 🟠 High |
| QTA3 | Lambda concurrent executions | `service-quota-check` | Concurrent-execution quota ≥ peak concurrency + provisioned concurrency | 🟡 Medium |
| QTA4 | ELB quotas (LCU / targets / listeners) | `service-quota-check` | Load-balancer quotas support reserved LCUs and peak target count | 🟡 Medium |
| QTA5 | Critical-path quotas raised early | quota increase request history | Increases submitted 8–12 wk out; any needing AWS-team coordination confirmed granted, not pending | 🟠 High |

---

## Pillar RES — Resilience & Fault Isolation

The probability of failure rises with the number of components; event-ready
platforms isolate failure and degrade gracefully. `[P1]` `[SML]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| RES1 | Multi-Region active-active for the critical viewer path | Region deployment of auth / manifest / ad decisioning | Critical viewer path deployed in ≥ 2 Regions for proximity and fault isolation | 🟠 High |
| RES2 | DNS-based failover | Route 53 health checks + failover/latency routing; Route 53 ARC routing controls | Health-checked Route 53 failover can shift traffic to a healthy Region — budget ~60s (typical failover TTL), not instant, and note resolvers can serve cached answers beyond TTL (e.g. VPC Resolver on origin SERVFAIL). Where **Route 53 Application Recovery Controller (ARC)** routing controls are in use, the sub-TTL shed is faster (operator-initiated `UpdateRoutingControlState`). Pair with **CDN5** (CloudFront origin failover) and **CDN8** (multi-CDN client-side switching) as the faster viewer-side shed | 🟠 High |
| RES3 | Service isolation | compute/db/network sharing between critical and non-critical | Event-critical services do not share compute, database, or networking with batch/analytics/transcode workloads | 🟠 High |
| RES4 | Graceful degradation hierarchy | circuit breakers + documented priorities | Explicit priority order enforced under load (personalization degrades before playback; analytics before ad serving) via circuit breakers | 🟠 High |
| RES5 | Stateless compute, persistent state | app tier statelessness; session store | Playback/critical services stateless & horizontally scalable; session/preference/entitlement state in purpose-built stores (DynamoDB / ElastiCache / Keyspaces) | 🟡 Medium |
| RES6 | No maintenance overlapping the event | **`aws-health-events`** / Health Dashboard | No scheduled maintenance overlaps the event window for any event-critical service; anything that does is deferred | 🟠 High |
| RES7 | Version lifecycle & auto-upgrade exposure | EKS version; RDS/Aurora `EngineVersion` + `AutoMinorVersionUpgrade` + pending-maintenance-actions; OpenSearch engine + service-software; ElastiCache/MSK versions; Lambda runtimes — vs end-of-standard-support dates, cross-checked against AWS Health end-of-support notifications (authoritative; EKS `upgradePolicy.supportType`; reuse `eks-upgrade-readiness` for EKS depth) | No event-critical managed service runs a version at/near end of standard support that AWS could auto-upgrade or force-maintain in the event window. Any such version is upgraded well **before** the change freeze (SUP3) or its maintenance deferred past the event (RES6); `AutoMinorVersionUpgrade` and maintenance windows reviewed so no upgrade can land during the window | 🟠 High |

**Why RES7 matters.** At end of standard support AWS can automatically upgrade or
force maintenance — e.g. RDS auto-applies minor upgrades in the maintenance window
and moves end-of-support majors onto (billed) extended support; EKS auto-upgrades the
control plane into extended support; OpenSearch applies service-software updates.
Any of these can execute **inside the change freeze or the live event window**. The
pre-event action is binary: finish the upgrade well before the freeze, or defer the
maintenance past the event — never let it ride into the window. The authoritative
signal is **AWS Health**, which emits an end-of-support notification for the affected
cluster/instance ahead of the deadline — rely on that (via RES6) plus the version /
`upgradePolicy.supportType` check, not on recalling EOL dates from memory. Lifecycle
dates change; confirm current end-of-standard-support dates in AWS documentation.

---

## Pillar CDN — Content Delivery / Edge

Content delivery is where viewer experience is won or lost. CloudFront provides
the multi-layer edge/regional-cache/private-network architecture; your job is to
let it work and keep origin load predictable. `[P2]` `[SML]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| CDN1 | Delivery via CloudFront, single consistent origin | `cloudfront get-distribution-config` | Live delivery through CloudFront with a single consistent origin (not fragmented origins for identical content) | 🟠 High |
| CDN2 | Origin Shield enabled | distribution origin config | Origin Shield on as the centralized caching layer between regional edge caches and origin — the primary control for predictable origin load at peak | 🟠 High |
| CDN3 | High cache-hit ratio / cache-key hygiene | cache policy + CloudWatch cache-hit metric | Cache keys normalized and query-string variations stripped so short-TTL (2–6 s) live segments are not fragmented; cache-hit ratio measured and high | 🟠 High |
| CDN4 | Edge compute placed correctly | CloudFront Functions / Lambda@Edge associations | High-frequency light ops (cache-key normalization, URL rewrite, header/token work) on CloudFront Functions; heavy runtime ops (manifest manipulation, rendition filtering, ad-marker processing) on Lambda@Edge | 🟡 Medium |
| CDN5 | Origin redundancy / CDN failover | origin groups / multi-CDN | Multi-tier distribution with origin redundancy and CDN failover so a single origin or peering issue doesn't black out delivery (`SML` SMREL03-BP01) | 🟡 Medium |
| CDN6 | S3 origin request-rate scaling (origin = S3) | distribution origin config (origin is S3) + object key/prefix layout | When the manifest/segment origin is an S3 bucket, object keys are distributed across prefixes so cache-miss GETs at peak stay within S3's ~5,500 GET/s per partitioned prefix (no limit on the number of prefixes); Origin Shield (CDN2) absorbs most misses, but a thundering-herd cache fill concentrated on one prefix can still return HTTP 503 slowdowns | 🟡 Medium |
| CDN7 | MediaTailor (SSAI) playback configuration & prefetch | `mediatailor list-playback-configurations` / `get-playback-configuration` + prefetch schedules | When ads are inserted server-side with MediaTailor, each playback configuration points at a validated content segment prefix (CDN) and ADS; for events with **scheduled ad breaks** (sports halftime/timeouts, programming windows) a `PrefetchSchedule` is defined so the ADS is called ahead of the break rather than at the viewer surge; the player degrades to **slate / content** when the ADS is slow or unavailable so a timed-out ad decision does not stall playback. The MediaTailor side itself scales — the risk is the backing ADS/VAST endpoint and the player fallback behavior (cross-ref TST4) | 🟠 High |
| CDN8 | Multi-CDN with client-side switching (tier-1 events) | player SDK / client-side manifest handling; CDN account posture | For tier-1 live events (finals, Olympics-scale, major sports), two or more CDNs are configured with **client-side switching** (QoE-based: rebuffer / error / VST, or active-passive) so a single-CDN peering or performance issue is shed by the player, not by DNS. CloudFront origin groups (CDN5) protect against origin failure but do not shed a *CDN-level* issue; multi-CDN switching does. For single-CDN by design (lower-tier event or deliberate choice), grade this as a risk observation, not a FAIL | 🟡 Medium |
| CDN9 | Low-latency HLS / CMAF cache-TTL tradeoff | playback-config / packager settings; distribution behavior; S0 latency target | Where sub-5s glass-to-glass latency is promised (LL-HLS / CMAF chunked encoding), the player uses chunked transfer encoding end-to-end, the CDN behavior supports it, and the operator has planned for the cache-TTL tradeoff: shorter TTLs on partial segments mean more cache misses and higher origin pressure, so Origin Shield (CDN2) and origin capacity are sized for the increased cache-fill rate. If normal latency (≥10s) is acceptable, CDN9 is N/A | 🟡 Medium |

---

## Pillar NET — Networking Capacity

East-west and egress paths have hard ceilings that load testing must probe; where
you approach them, pre-warm through AWS Support ahead of the event. `[P1]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| NET1 | NAT gateway headroom | `ec2 describe-nat-gateways` + CloudWatch `AWS/NATGateway` vs load test | Peak stays within NAT limits — track **PeakPacketsPerSecond** (leading indicator, ceiling ~10,000,000 pps), **ActiveConnectionCount** (~55,000 per unique destination), **ErrorPortAllocation** (any non-zero = at a connection ceiling for a destination), plus BytesIn/OutToDestination (bandwidth) and PacketsDropCount; hot destinations identified | 🟠 High |
| NET2 | Transit gateway throughput | CloudWatch `AWS/TransitGateway` per attachment vs peak | Per-attachment **BytesIn/BytesOut** converted to a sustained bits/sec rate stays well under the ~100 Gbps burst ceiling; **PacketDropCountNoRoute** / **PacketDropCountBlackhole** flat (a rise correlated with the event window = routing review) | 🟡 Medium |
| NET3 | VPC endpoint / connectivity capacity | endpoint usage vs peak | Interface/gateway endpoints on the critical path won't throttle service traffic at peak | 🟡 Medium |
| NET4 | Support pre-warm requests submitted | AWS Support case history | Where load tests approach NAT/TGW/ELB limits, pre-warm requested through AWS Support ahead of the event (not left to event day) | 🟠 High |

**Pre-warm decision rule (NET1 / NET2 / NET4).** A NAT gateway scales throughput
automatically but *incrementally* — roughly a 5-minute step-up. Request a Support
pre-warm when the projected peak **packets/sec** (NAT) or **per-attachment bits/sec**
(TGW) will reach a large fraction of the ceilings above within a window **shorter
than that ~5-minute reactive ramp** — i.e. a scheduled tent-pole event with a hard
start (kickoff, halftime), not organic growth. The clearest combined NAT trigger is
a rising **PacketsDropCount** alongside a steep **PeakPacketsPerSecond** ramp. Grade
NET4 against the *shape* of the projected ramp, not raw size: for business-as-usual
scale, reactive scaling suffices and pre-warm is **not** required. Ceilings are
approximate — confirm current NAT/TGW quotas in AWS documentation.

---

## Pillar DAT — Data & State Stores

Databases and caches must absorb the read/write pattern at peak without hot-key or
throttling issues; pre-warm forces the partitions/shards before demand arrives. `[P1]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| DAT1 | DynamoDB warm throughput vs peak | `DescribeTable.WarmThroughput` (ReadUnitsPerSecond / WriteUnitsPerSecond) + BillingMode; CloudWatch ConsumedRead/WriteCapacityUnits for historical peak | The table's **warm throughput** (what it can serve instantly, reflecting historical / previously-provisioned peak) meets or exceeds the projected event peak — in **either** billing mode. On-demand is fine when warm throughput already covers the peak (e.g. the table was previously provisioned high; the level carries over). If warm throughput is below peak (e.g. a new on-demand table's 12,000 RCU / 4,000 WCU floor, or a never-scaled table), **FAIL** → pre-warm (raise warm throughput via UpdateTable) or provision sized to peak. Access must be well-distributed — a hot partition (~3,000 RCU / 1,000 WCU) can still throttle below the table's warm throughput | 🟠 High |
| DAT2 | ElastiCache sizing & pre-warm | cluster node/shard config | Provisioned clusters sized for peak connections/throughput with validated shard distribution (no hot keys); Serverless pre-warmed ≥ 60 min before the ramp. An event-critical cache left at baseline size with no pre-warm plan is a **FAIL**, not N/A | 🟠 High |
| DAT3 | RDS / Aurora read scaling | `rds describe-db-instances` / cluster members (**`rds-operation-review`**) | Read replicas scaled to peak count beforehand, or Aurora Serverless v2 where the profile is uncertain | 🟡 Medium |
| DAT4 | Session-token caching | identity/session design evidence | Session tokens cached so the login surge does not bottleneck on the identity database | 🟠 High |
| DAT5 | Identity/auth login-rate validation | load-test evidence (cross-ref TST3) | Identity platform validated to sustain the pre-event login/signup rate — including upstream rate limits where authentication is federated through a third-party IdP (social OAuth: Google / Facebook / Apple ID) or an external identity vendor, since those providers have **their own per-tenant request-rate limits** that cannot be raised event-day | 🟠 High |
| DAT6 | Amazon Keyspaces warm throughput vs peak | `keyspaces get-table` warmThroughput (read/write units) + capacitySpecification.throughputMode; CloudWatch ConsumedRead/WriteCapacityUnits for historical peak | The table's **warm throughput** (what Keyspaces can serve instantly, reflecting prior on-demand peak or previously-provisioned capacity) meets or exceeds the projected event peak — in **either** capacity mode. On-demand is fine when warm throughput already covers the peak (previously-provisioned-high capacity carries over). If warm throughput is below peak (e.g. a new on-demand table's 12,000 RCU / 4,000 WCU floor), **FAIL** → pre-warm (raise warm throughput) or switch to PROVISIONED sized to peak. Keep access well-distributed: each partition caps at 3,000 RCU / 1,000 WCU, so a hot partition can throttle below the table's warm throughput | 🟠 High |
| DAT7 | DRM license-server capacity & token caching | S1 vendor confirmation (Widevine / PlayReady / FairPlay license-server owner); SPEKE key-provider configuration (`mediapackage` / `elemental-mediapackage-v2`); player token caching | For DRM-protected delivery, the license server (usually a third-party service via **SPEKE** — Verimatrix, EZDRM, Irdeto, Axinom, or self-hosted) has **capacity confirmed with the provider at the projected peak license-request rate** (viewers × key rotations/session), and **license-renewal windows are staggered** (not all expiring at the same moment) so renewals don't cluster into a secondary spike mid-event. Short-lived DRM tokens are cached and refreshed in the player SDK so each key request doesn't round-trip to the identity service. For non-DRM content (open streams, test events), DAT7 is N/A | 🟠 High |

**Serverless / auto-scaling pre-scaling rule (DAT, with CAP and NET).** Serverless
and auto-scaling components scale **reactively and incrementally** — in minutes, not
seconds. When the projected step-up is large and fast — for example a **>4× rise
within a window shorter than the service's scaling step (~5 minutes)** — reactive
scaling cannot catch up and viewers hit throttling/latency during the ramp. For any
such component on the critical path facing a steep, hard-start spike, **pre-warm or
pre-scale ahead of the event**, and grade "present but relying on live scale-out for
the spike" as a **FAIL**, not a PASS:
- **ElastiCache Serverless** — pre-warm by ramping synthetic traffic **≥ 60 min**
  ahead so it scales out before the real spike (DAT2); do not rely on live scale-out
  for a sudden multiple-× step.
- **DynamoDB on-demand** — check `WarmThroughput` against the peak (DAT1): if it
  already covers the peak (e.g. the table was previously provisioned high), on-demand
  serves it instantly; if not, raise warm throughput (pre-warm) ahead of the event.
- **Amazon Keyspaces on-demand** — check `warmThroughput` against the peak (DAT6): if
  it already covers the peak (previously-provisioned-high capacity carries over),
  on-demand serves it; if not, pre-warm (raise warm throughput) or switch to
  PROVISIONED sized to peak ahead of the event.
- **Aurora Serverless v2** — raise the **minimum ACU** so the floor already covers the
  peak rather than scaling up into it (DAT3).
- **Lambda** — **provisioned concurrency** on the latency-sensitive critical path (CAP5).

Same reasoning as the NAT ~5-minute reactive-ramp pre-warm rule (NET), applied to
data/state and compute. For organic/BAU growth, reactive scaling is sufficient and
pre-scaling is not required — grade on the ramp's *shape*, not raw size.

---

## Pillar TST — Testing & Chaos Readiness

Readiness is proven in stages under realistic traffic with failures injected —
proof, not hope. The highest-value application tests are the ones the media
pipeline scale test won't catch. `[P2]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| TST1 | Staged testing gates | load-test plan + results | Four gates run in sequence: component (≈ 2× component peak) → integration (platform peak) → full-scale production rehearsal (1.3–1.5× peak) → spike & failure | 🟠 High |
| TST2 | Realistic load profile & viewer patterns | load-test profile | Ramp over ~60 min to peak, sustain 2–3 h with periodic 20–40% spikes, then decline — not an unrealistic zero-to-peak ramp — and modeled on real viewer patterns: codec/protocol mix (HLS/DASH, H.264/H.265), join/leave rates, baseline traffic, and load spread across **multiple origin endpoints** (a single-origin high-concurrency test can pass while lower concurrency across many endpoints fails) | 🟡 Medium |
| TST3 | Identity & signup surge tested | test evidence | Full signup-to-first-play journey tested at peak signup rate; watched for token-service throttling, account-creation write contention, payment rate limits | 🟠 High |
| TST4 | Ad-decisioning path tested | test evidence | Ad-decisioning tested at event concurrency — ADS/VAST endpoint capacity confirmed with the vendor at projected QPS, timeout budget held, and the player degrades gracefully (skips to content / shows slate) when the ad service is slow/unavailable; ad-tracking beacon volume (impression / quartile / completion pixels) load-tested so the tracking pipeline doesn't bottleneck during the ad window (cross-ref CDN7, OBS6) | 🟡 Medium |
| TST5 | Chaos / fault-injection experiments | AWS FIS experiment templates / results | FIS experiments with stop conditions: dependency-latency injection (circuit breakers trip before playback) and compute termination (EKS pods / EC2) with recovery inside steady-state thresholds | 🟠 High |
| TST6 | Steady state in viewer terms + blast-radius order | experiment definitions | Steady state defined as viewer metrics (e.g. VST < 3 s, rebuffer < 0.5%, error < 0.1%); experiments ordered nonprod → prod low → moderate → full-scale | 🟡 Medium |
| TST7 | External dependencies & cross-team sign-off before the test | S1 engagement evidence; vendor/service-team confirmations | CDN, ad/ADS, origin, and other backend vendors — plus the relevant AWS service teams — are engaged and have signed off that they can sustain the test; each participating team has agreed success criteria so the rehearsal is not throttled by an unprepared dependency | 🟠 High |

---

## Pillar OBS — Observability & Steady State

You can only defend what you can see; monitoring must be proven before the event,
not stood up during it. `[P2]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| OBS1 | Viewer-experience SLIs instrumented | dashboards / metrics; CMCD in CloudFront real-time logs | Video start time (VST), video start failures (VSF), video playback failures (VPF), rebuffering ratio, and playback error rate measured as first-class metrics; client-side QoE correlated with CDN performance via CMCD in CloudFront real-time logs | 🟠 High |
| OBS2 | Critical workloads & alarms onboarded early | alarm config / monitoring onboarding | Critical workloads and alarms onboarded weeks ahead so monitoring is proven for event day | 🟠 High |
| OBS3 | Capacity-headroom dashboards | dashboards | Critical path + capacity headroom (quota utilization, NAT, DB, cache) visible on event-day dashboards | 🟡 Medium |
| OBS4 | Alarm coverage on critical-path services (tool-agnostic) | `cloudwatch describe-alarms` mapped to critical-path resources; third-party coverage declared in S1 | Every critical-path service has ≥1 **actionable** alarm (bound to a notification or auto-action, `ActionsEnabled`) on a failure/saturation signal — in CloudWatch **or** a declared third-party platform (Datadog / New Relic / Grafana / Splunk / Dynatrace). A critical-path service with no alarm in any tool = FAIL `[SML]` `[P2]` | 🟠 High |
| OBS5 | Measurable success criteria & KPI threshold matrix | S1 success-criteria doc; KPI definitions | Glass-to-glass KPIs with a warning/critical/failure threshold matrix and explicit stakeholder sign-off define what "success" means before the event (e.g. VPF < 0.05%, a VST target, a rebuffer ceiling, event-window uptime); thresholds map to the alarm/severity model `[SML]` | 🟠 High |
| OBS6 | Telemetry / analytics pipeline headroom | `kinesis describe-stream-summary` (shard count, `OnDemand` mode, `IteratorAge`) / `firehose describe-delivery-stream` / MSK broker metrics; CloudWatch per-shard `WriteProvisionedThroughputExceeded` / `GetRecords.IteratorAgeMilliseconds` | The pipeline carrying viewer QoE beacons, CMCD, ad-tracking, and session heartbeats (**Kinesis Data Streams** / **Firehose** / **MSK**) is sized for the projected peak event volume: Kinesis in on-demand mode or shard count × 1,000 records/s and 1 MB/s per shard covers peak writes; `WriteProvisionedThroughputExceeded` and `IteratorAge` stay flat under rehearsal load (TST1); Firehose delivery-stream throughput quotas have headroom. A throttling telemetry pipeline at peak **blinds the OBS pillar** exactly when SLIs matter most. For CloudWatch-only telemetry (no streaming/batch pipeline), OBS6 is N/A | 🟡 Medium |

**OBS4 third-party rule.** The DevOps Agent reads AWS-account state only — it
**cannot** read Datadog / New Relic / Grafana / Splunk / Dynatrace. So empty
`describe-alarms` output is **not** a FAIL on its own: check S1 for a declared
third-party platform and grade OBS2/OBS4 on that. If third-party coverage is
asserted but not machine-verifiable, mark the affected rows **N/A** with the reason
"third-party alarms declared, not verifiable via read-only AWS access — confirm
manually", never an automatic PASS. Absence of an actionable alarm in **both**
CloudWatch and any declared tool is a **FAIL**. An alarm with no action
(`ActionsEnabled=false` or empty `AlarmActions`) does not count as coverage.

---

## Pillar SUP — Operational Readiness & Support

Flawless events are a multi-month, cross-functional program with milestones and
owners; event support engagement responds to risks live. `[P1]` `[P2]`

| ID | Check | Evidence source | PASS criteria | Severity |
|----|-------|-----------------|---------------|----------|
| SUP1 | AWS account team engaged + WAFR run | engagement evidence / WAFR report | AWS account team engaged early (12–16 wk); Well-Architected Review run with focus on Reliability and Performance Efficiency | 🟠 High |
| SUP2 | Event support engaged | engagement evidence | AWS Unified Operations for Media (preferred; includes IDR — Incident Detection and Response — monitoring with an incident-manager bridge on threshold breach) or AWS Countdown Premium engaged and onboarded weeks ahead (2–3 wk minimum, 8–12 wk for complex events) | 🟠 High |
| SUP3 | Change freeze & event-day discipline | change-management evidence | Change freeze ~1 week before; event day is "monitor, don't deploy" — all capacity in place hours before start | 🟠 High |
| SUP4 | Cross-functional runbooks | runbooks | Platform engineering, operations, and security have jointly documented expected behavior and runbooks for the critical path and its failure modes; runbooks include KPI-breach SOPs with explicit ownership, resolution steps, escalation paths and SLAs, validated in a dress rehearsal | 🟡 Medium |
| SUP5 | Business-driven demand shaping | programming / product plan | Demand shaped: pre-event programming (2–3 h before) to turn the spike into a ramp; early signup campaigns to spread auth/payment load; progressive/async feature loading so the core player initializes first | 🟡 Medium |
| SUP6 | Event-day communication plan & roles | runbooks / comms plan | A documented communication plan exists and is rehearsed in game-day sims: a Comms Manager aggregates updates and issues a single stakeholder update on a fixed cadence, each team has a designated reporter feeding it, bridge etiquette is defined (stay muted, direct address, side bridges, threaded IM), key actions/timestamps are logged for the retrospective, and a sequenced event off-boarding (e.g. stop sources before MediaLive to avoid false alarms) with producer approval is defined | 🟠 High |
| SUP7 | Live-captions & accessibility path tested | S1 captioning architecture (CEA-608/708 pass-through from MediaLive, Transcribe Live, or third-party vendor — Ai-Media / EEG / Enco); end-to-end player evidence | For events where live captions are a **regulatory requirement** (FCC, Ofcom, broadcast license) or an editorial commitment, the full captioning path is tested end-to-end before the event: ingest → encode (CEA-608/708 or WebVTT) → packager → player; the third-party captioning vendor has confirmed capacity at the event duration/concurrency; a documented fallback (switch to backup captioner, graceful disable with on-screen notice) is defined. Audio-only, closed-circuit, or demonstrably caption-exempt events → SUP7 N/A | 🟡 Medium |

---

## Applicability gates (when a pillar/row is N/A)

- No EKS → CAP3, CAP4 N/A (note it). ECS-only → grade via `ecs-operation-review`.
- **EKS Auto Mode** → CAP1/CAP4 AWS-handled, CAP3 N/A; grade the Auto Mode residuals in the CAP note above (pre-scaled workloads, resource requests, startup time). An idle Auto Mode cluster is **not** an automatic PASS.
- No Lambda on the critical path → CAP5, QTA3 N/A.
- Single-Region by design → RES1/RES2 become **risk observations**, not automatic
  FAIL; record the customer's fault-isolation decision and its residual risk.
- No ad-supported tier → TST4, CDN4 ad-marker portion N/A.
- No self-managed identity (third-party IdP) → DAT4/DAT5 graded on the integration
  and caching in front of the IdP, and on the IdP's published rate limits.
- No Keyspaces on the critical path → DAT6 N/A; no DynamoDB → DAT1 N/A. Grade only
  the data stores actually used.
- No EBS on the critical path (e.g. fully serverless, or instance-store only) → CAP9 N/A.
- Origin is not S3 (e.g. MediaPackage or a custom HTTP origin) → CDN6 N/A.
- **No MediaTailor / client-side SSAI only** (ads inserted by the player via CSAI) →
  CDN7 N/A; grade the ad path via TST4 (player-side ad switching + ADS capacity) and
  OBS6 (ad-tracking beacon volume).
- **Single-CDN by design** (lower-tier event or deliberate choice) → CDN8 is a
  **risk observation**, not an automatic FAIL — record the residual risk that a
  single-CDN peering issue is shed only by the slower Route 53/CloudFront paths.
- **Standard-latency delivery** (no LL-HLS / CMAF low-latency commitment,
  glass-to-glass ≥ 10s acceptable) → CDN9 N/A.
- **No DRM** (open streams / test events / public-service free-to-air) → DAT7 N/A.
- **CloudWatch-only telemetry** (no Kinesis / Firehose / MSK carrying QoE,
  CMCD, ad-tracking, or heartbeats) → OBS6 N/A.
- **Captions not required** (audio-only, closed-circuit internal event, or
  demonstrably caption-exempt by the applicable regulator) → SUP7 N/A.
- **Amazon IVS-based platform** (turn-key low-latency streaming, service-managed
  edge/origin/encode) → CAP (except CAP5 if Lambda is on the API path), NET, CDN
  mostly N/A — AWS manages those primitives; grade RES6/RES7 against IVS service
  quotas and version lifecycle, DAT against the customer-managed state stores,
  TST on the IVS SDK and Live Session Low-Latency Chat limits where applicable,
  OBS1 against the IVS client SDK QoE metrics, and SUP as-is. A full IVS review
  requires an IVS-specific skill; this review grades only the portions that
  remain customer-managed.
- Third-party observability (Datadog / New Relic / Grafana / Splunk / Dynatrace) →
  the DevOps Agent cannot read these, so empty CloudWatch `describe-alarms` is not a
  FAIL on its own (see the OBS4 third-party rule): grade OBS2/OBS4 on the declared
  third-party coverage from S1, N/A where it is asserted but not machine-verifiable,
  FAIL only where no actionable alarm exists in any tool.
- **IAM `AccessDenied` on `mediatailor:*`** (base `AIDevOpsAgentAccessPolicy` deployed
  without the custom `DevOpsAgentSkill-LiveStreamingEventReadinessReview` policy
  attached, or the actions explicitly denied) → **CDN7 N/A** with the reason
  "MediaTailor API not accessible under the configured IAM role; confirm the SSAI
  playback configuration and PrefetchSchedule for scheduled breaks manually from S1
  context." Do not infer a gap — missing permission is not evidence of
  misconfiguration.
- **IAM `AccessDenied` on `route53-recovery-cluster:ListRoutingControls`** → the
  **RES2 ARC branch is N/A** with the reason "Route 53 ARC API not accessible under
  the configured IAM role; grade RES2 against standard Route 53 health-check failover
  and CDN5/CDN8 only." The base RES2 DNS-failover path still grades.
- No documented success criteria provided and not derivable in-session → OBS5 is a
  **risk observation** ("no measurable success definition for the event"), not N/A —
  the absence is itself the finding.
