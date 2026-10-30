# LSE Readiness — remediations

Load only after FAIL IDs are known. One block per check: **Why it matters →
Steps → References.** Every step is a *proposal for human approval* — this skill
performs no mutations, and several steps (pre-warm, ODCR, quota increase, change
freeze) are deliberate customer actions. Pair each remediation with the
capacity-planning timeline milestone it belongs to; if the event is too close to
remediate fully, add the **day-of mitigation** noted in the block.

---

## CAP — Capacity & Scaling

### CAP1 — Instance diversification
**Why:** Diversification across instance families, sizes, and AZs is the single
most effective lever for getting On-Demand capacity during a surge; a single
instance type is the most common capacity ceiling.
**Steps:** Configure the provisioner to accept multiple families and sizes across
all event AZs — Karpenter NodePool `requirements` (instance-category/family/size
+ zones), ASG mixed-instances policy, or ECS capacity-provider strategy. Make this
the first lever before reserving capacity.
**Day-of mitigation:** If nothing else is ready, widening diversification is the
fastest capacity win and needs no AWS lead time.
**References:** [Karpenter consolidation](https://aws.amazon.com/blogs/containers/optimizing-your-kubernetes-compute-costs-with-karpenter-consolidation/) · [EC2 Auto Scaling mixed instances](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-mixed-instances-groups.html)

### CAP2 — On-Demand Capacity Reservations (fallback)
**Why:** Diversification improves odds but never *guarantees* On-Demand capacity.
Where you need assurance for the critical path, reserve it.
**Steps:** Create ODCRs for the critical-path instance types/AZs; use
**future-dated** reservations (up to 120 days ahead) for the event window so
capacity is held before the ramp. Validate the reservations during load testing.
**Day-of mitigation:** Future-dated ODCRs need lead time — if too late, fall back
to CAP1 (diversification) plus a NET4 Support pre-warm and raised CAP7 minimums.
**References:** [Reserving EC2 capacity with ODCRs](https://aws.amazon.com/blogs/compute/reserving-ec2-capacity-across-availability-zones-by-utilizing-on-demand-capacity-reservations-odcrs/)

### CAP3 — EKS control plane pre-provisioning
**Why:** In standard mode the control plane scales reactively; mass pod
scheduling and burst API calls during the ramp can exceed its allocation.
**Steps:** Switch the cluster to provisioned mode ahead of the event to
pre-allocate API-server throughput, controller capacity, and etcd at a fixed
scaling tier. Validate under the rehearsal (TST1).
**References:** [Amazon EKS](https://aws.amazon.com/eks/) · deep dive: reuse `aws-eks-operations-review`.

### CAP4 — Warm capacity & fast pod starts
**Why:** Even with capacity available, slow node/pod startup means you fall behind
the ramp.
**Steps:** Hold spare capacity with low-priority pause pods (evicted when real
workloads schedule); keep container images small; use SOCI lazy loading; pre-pull
critical images via a DaemonSet.
**References:** [SOCI / lazy loading](https://docs.aws.amazon.com/AmazonECR/latest/userguide/soci-indexes.html)

### CAP5 — Lambda provisioned concurrency
**Why:** Cold starts on latency-sensitive critical-path functions (token
validation, authz, session creation) add latency exactly when traffic spikes.
**Steps:** Configure provisioned concurrency on those functions sized to event
peak; confirm it against the Lambda concurrency quota (QTA3).
**References:** [Lambda provisioned concurrency](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)

### CAP6 — Load Balancer LCU reservation
**Why:** Load balancers themselves scale reactively; a sharp ramp can outrun
them.
**Steps:** Reserve minimum LCU capacity sized on the load-tested peak **plus a
margin**; normal auto scaling continues above the reservation.
**References:** [LCU reservation](https://aws.amazon.com/blogs/networking-and-content-delivery/using-load-balancer-capacity-unit-reservation-to-prepare-for-sharp-increases-in-traffic/)

### CAP7 — Pre-provisioned minimum capacity
**Why:** Reactive auto scaling always lags demand; the ramp arrives before the
capacity does.
**Steps:** Raise critical-path minimum capacity (ASG/Karpenter/replica counts)
ahead of the ramp so the baseline is already in place; scale back after.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (capacity planning)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### CAP8 — Capacity-planning timeline
**Why:** Flawless events are a planned discipline with milestones and owners, not
a last-minute exercise.
**Steps:** Adopt the milestone table (report §6); assign an owner per milestone;
track quota, ODCR, pre-warm, load-test, rehearsal, and change-freeze items.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (the capacity planning timeline)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### CAP9 — EBS volume performance & initialization
**Why:** Volumes restored from a snapshot lazy-load their blocks, so first access runs at
higher latency and reduced performance until initialization completes — exactly when the
event spike arrives. Under-sized gp3 IOPS/throughput also caps I/O.
**Steps:** Size event-critical gp3 volumes for peak IOPS/throughput (don't leave defaults).
For any volume created from a snapshot for the event, enable **Fast Snapshot Restore** on
the source snapshot (volume is fully initialized at creation) or pre-read all blocks before
the event; confirm with the volume-initialization status.
**References:** [EBS fast snapshot restore](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-fast-snapshot-restore.html) · [Initialize Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-prewarm.html)

---

## QTA — Service Quotas

### QTA1–QTA5 — quota headroom and early increases
**Why:** A quota ceiling on the critical path caps how fast you can scale, and
some increases require AWS-team coordination that cannot be done overnight.
**Steps:** Run `service-quota-check` for each critical-path quota; where
utilization-vs-peak leaves insufficient headroom, submit increases 8–12 weeks out
and confirm they are **granted**, not pending. Track EC2 vCPU (QTA1), NAT/EIP
(QTA2 / NET), Lambda concurrency (QTA3), ELB (QTA4).
**Day-of mitigation:** None for quotas needing manual review — this is why early
submission is a hard milestone; a near-event gap here is **residual risk**.
**References:** [AWS service quotas](https://docs.aws.amazon.com/general/latest/gr/aws_service_limits.html) · reuse `service-quota-check`.

---

## RES — Resilience & Fault Isolation

### RES1 — Multi-Region active-active
**Why:** A Region impairment during the event takes down a single-Region critical
path with no fallback.
**Steps:** Deploy auth, manifest generation, and ad decisioning in ≥ 2 Regions;
replicate state stores; validate failover in the rehearsal.
**References:** [AWS Regions](https://docs.aws.amazon.com/glossary/latest/reference/glos-chap.html) · [Reliability pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)

### RES2 — DNS-based failover
**Why:** Without health-checked DNS routing, a Regional failure isn't shed quickly
and viewers hit the impaired path. DNS failover is a backstop, not instant — it's
not the primary viewer-side shed.
**Steps:** Configure Route 53 health checks with failover or latency routing; budget
~60s for the shift (AWS Prescriptive Guidance treats 60s as typical for failover TTL),
not seconds, and account for resolvers serving cached/stale answers beyond TTL (e.g.
the VPC Resolver holding answers on origin SERVFAIL). Where sub-TTL shed matters,
consider **Route 53 Application Recovery Controller (ARC)** routing controls — an
operator-initiated `UpdateRoutingControlState` toggles traffic faster than DNS failover
can propagate. Pair with CDN5 (CloudFront origin failover) and CDN8 (multi-CDN
client-side switching) — the player-side shift is faster than any DNS mechanism.
Test the end-to-end shift under load.
**References:** [Route 53 failover routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-failover.html) · [Route 53 Application Recovery Controller](https://docs.aws.amazon.com/r53recovery/latest/dg/what-is-route53-recovery.html) · [AWS Prescriptive Guidance — Route 53 request routing / failover TTL](https://docs.aws.amazon.com/prescriptive-guidance/latest/dynamodb-global-tables/route-53-request-routing.html)

### RES3 — Service isolation
**Why:** A batch analytics job or transcode task sharing resources with the
viewer path can starve playback at peak.
**Steps:** Separate event-critical services onto dedicated compute/node
groups/clusters, databases, and network paths; isolate non-critical workloads.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (key architecture patterns)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### RES4 — Graceful degradation hierarchy
**Why:** Under load, something must give — it should be personalization and
analytics, never playback.
**Steps:** Define explicit priorities (personalization degrades before playback;
analytics before ad serving) and enforce them with circuit breakers; prove the
hierarchy with FIS dependency-latency injection (TST5).
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (chaos engineering)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### RES5 — Stateless compute, persistent state
**Why:** Stateful playback tiers can't scale horizontally cleanly and lose
sessions on scale events.
**Steps:** Keep playback/critical services stateless; hold session, preference,
and entitlement state in DynamoDB / ElastiCache / Keyspaces that scale
independently.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (key architecture patterns)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### RES6 — Maintenance overlap
**Why:** Scheduled maintenance during the event window is self-inflicted risk.
**Steps:** Run `aws-health-events`; for any scheduled change overlapping the
window on an event-critical service, defer it past the event.
**References:** [AWS Health Dashboard](https://health.aws.amazon.com/health/status) · reuse `aws-health-events`.

### RES7 — Version lifecycle & auto-upgrade exposure
**Why:** A managed-service version at end of standard support can be auto-upgraded
or force-maintained by AWS — RDS minor auto-upgrades in the maintenance window and
end-of-support majors move to (billed) extended support; EKS auto-upgrades the
control plane into extended support; OpenSearch applies service-software updates —
and that can execute inside the change freeze or the live event window.
**Steps:**
1. Inventory event-critical versions (`discovery.md` RES7): EKS; RDS/Aurora (+ `AutoMinorVersionUpgrade` and pending-maintenance-actions); OpenSearch (+ service software / auto-update); ElastiCache (+ `AutoMinorVersionUpgrade`); MSK; Lambda runtimes.
2. Flag any at/near end of standard support, and any with a pending upgrade or an `AutoMinorVersionUpgrade` + maintenance window that could fire in the event window.
3. Resolve each one way only: **upgrade well before the change freeze** (test first), **or defer the maintenance past the event**. Never let it ride into the window.
4. For EKS depth, reuse `eks-upgrade-readiness`.
**References:** [EKS version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) · [RDS maintenance & version upgrades](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Maintenance.html). Confirm current end-of-standard-support dates in AWS documentation.

---

## CDN — Content Delivery / Edge

### CDN1 — CloudFront + single consistent origin
**Why:** Fragmented origins for identical content multiply origin load and defeat
caching.
**Steps:** Deliver through CloudFront with one consistent origin; let the edge /
regional-edge-cache / private-network layers do their job.
**References:** [How CloudFront works](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/HowCloudFrontWorks.html)

### CDN2 — Origin Shield
**Why:** It's the primary control for keeping origin request rate predictable at
peak by consolidating cache-miss requests.
**Steps:** Enable Origin Shield in the Region closest to the origin; verify it in
the distribution's origin config.
**References:** [Origin Shield](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/origin-shield.html)

### CDN3 — Cache-hit ratio / cache-key hygiene
**Why:** Short-TTL live segments (2–6 s) lose efficiency if the cache is
fragmented by unnecessary key variation, driving origin load up.
**Steps:** Normalize cache keys; strip query-string variations that create unique
keys for identical content; measure CacheHitRate and tune. Apply TTL discipline by
object type: media **segments** are immutable — cache them long; the **manifest /
playlist** refreshes every segment — cache it short (≈ one segment duration, ~5–10 s
for live) so players get fresh playlists without hammering the origin. A long manifest
TTL stalls playback on stale playlists; a short segment TTL wrecks cache efficiency.
Honor the origin's cache-control rather than overriding it at the CDN (e.g. MediaPackage
publishes per-object TTLs and recommends you honor them).
**References:** [Managing cache keys](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-the-cache-key.html) · Streaming Media Lens SMPERF03-BP02 / SMCOST01-BP02 · [MediaPackage CDN configuration recommendations](https://docs.aws.amazon.com/mediapackage/latest/userguide/cdn-recommendations.html)

### CDN4 — Edge compute placement
**Why:** Running heavy logic where light logic belongs (or vice versa) wastes
cost and latency on the high-frequency request path.
**Steps:** Put cache-key normalization, URL rewrites, header work, and token
validation on CloudFront Functions (sub-ms, ~1/6 the cost); put manifest
manipulation, rendition filtering, geo-restriction, and ad-marker processing on
Lambda@Edge.
**References:** [CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html) · [Lambda@Edge](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/lambda-at-the-edge.html)

### CDN5 — Origin redundancy / CDN failover
**Why:** A single origin or peering issue shouldn't black out delivery.
**Steps:** Configure CloudFront origin groups for origin failover; where multi-CDN
is used, validate failover behavior. (Streaming Media Lens SMREL03-BP01.)
**References:** [Origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)

### CDN6 — S3 origin request-rate scaling
**Why:** With an S3 segment/manifest origin, S3 scales to ~5,500 GET/s per partitioned
prefix. A cache-miss thundering herd (cold edge, short-TTL segments) concentrated on one
prefix can hit that limit and return HTTP 503 slowdowns, starving delivery at the spike.
**Steps:** Distribute object keys across multiple prefixes so aggregate cache-miss GET stays
well within per-prefix limits (there is no limit on the number of prefixes); keep Origin
Shield on (CDN2) to collapse misses to the origin; validate the origin GET rate under load.
**References:** [Optimizing Amazon S3 performance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html)

### CDN7 — MediaTailor (SSAI) playback configuration & prefetch
**Why:** With server-side ad insertion, the critical risk is not MediaTailor itself (it
scales) but the backing ADS and the viewer-aligned call pattern. For a tier-1 live event
with **scheduled ad breaks** (sports halftime/timeouts, programming windows), the player
population hits the ADS simultaneously at each break — a surge that is often larger than
the opening-whistle ramp — and a slow ADS without a player slate/fallback stalls playback,
not just the ad.
**Steps:**
1. Verify each playback configuration points at a validated content segment prefix (CDN) and
   the correct ADS URL (`get-playback-configuration`).
2. For every known scheduled break in the event timeline, define a `PrefetchSchedule` so
   MediaTailor retrieves ad decisions ahead of the viewer surge instead of under it; align
   `Retrieval` and `Consumption` windows with the production run-of-show.
3. Confirm the player's graceful-degradation behavior when the ADS is slow or returns
   malformed VAST — slate / resume content, not a frozen player (cross-ref TST4).
4. Pair with OBS6 — confirm the ad-tracking beacon pipeline (impression / quartile /
   completion pixels) has headroom at peak concurrency.
**Day-of mitigation:** If prefetch isn't configured in time, work with the production team
to **widen ad-break margins** or **reduce ad load** for the break and raise ADS timeout
tolerance; the player-side slate fallback is the last line of defense.
**References:** [AWS Elemental MediaTailor — PrefetchSchedule](https://docs.aws.amazon.com/mediatailor/latest/apireference/API_PrefetchSchedule.html) · [MediaTailor server-side ad insertion overview](https://docs.aws.amazon.com/mediatailor/latest/ug/what-is.html)

### CDN8 — Multi-CDN with client-side switching
**Why:** CloudFront origin groups (CDN5) protect against origin failure, but a CDN-level
issue (a peering problem, a regional performance degradation, a routing anomaly) is only
shed by moving viewers to a different CDN. For tier-1 events (finals, Olympics-scale,
headline matches) the industry standard is **two or more CDNs with client-side (player-SDK)
switching** driven by live QoE (rebuffer / error / VST) or active-passive failover.
**Steps:** Onboard a second CDN with the same manifest/segment surface; implement
client-side switching in the player (QoE-based routing or active-passive); test the switch
in the rehearsal (TST1) with synthetic degradation of one CDN; align monitoring (OBS1) to
report per-CDN QoE so the switch is observable.
**Day-of mitigation:** None — multi-CDN requires onboarding lead time with the second CDN
and player-SDK work. A near-event gap is residual risk; mitigate at the DNS/CloudFront
level only (RES2 + CDN5) and accept slower shed.
**References:** [Streaming Media Lens SMREL03](https://docs.aws.amazon.com/wellarchitected/latest/streaming-media-lens/smrel-bp.html) · [Amazon CloudFront origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)

### CDN9 — Low-latency HLS / CMAF cache-TTL tradeoff
**Why:** Sub-5s glass-to-glass latency (LL-HLS, CMAF chunked encoding) requires chunked
transfer and short partial-segment TTLs, which drives up cache-miss rate and origin
pressure compared to standard-latency delivery. Teams that commit to low latency without
sizing the origin and cache stack for the increased miss rate hit origin saturation at
peak.
**Steps:** Confirm the CloudFront behavior supports chunked transfer end-to-end; keep
Origin Shield on (CDN2); size the packager/origin and any upstream pipeline for the
higher cache-fill rate implied by shorter TTLs; validate under the production rehearsal
(TST1) that the origin GET rate stays within quota.
**References:** [Low-latency HLS with CMAF chunked encoding](https://aws.amazon.com/blogs/media/part-1-back-to-basics-gops-explained/) · [AWS Elemental MediaPackage low-latency HLS](https://docs.aws.amazon.com/mediapackage/latest/userguide/ll-hls.html)

---

## NET — Networking Capacity

### NET1 — NAT gateway headroom
**Why:** Each NAT gateway tops out around 55,000 simultaneous connections **per
destination** and has a bandwidth ceiling; east-west traffic can hit it at peak.
**Steps:** From load testing, identify hot destinations and peak connection/
bandwidth; spread across multiple NAT gateways or destinations and request a
pre-warm (NET4) where you approach the limit.
**References:** [NAT gateway limits](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)

### NET2 — Transit gateway bandwidth
**Why:** TGW attachments have a per-attachment baseline bandwidth that peak
east-west traffic can exceed.
**Steps:** Compare load-tested peak to the per-attachment baseline; distribute
across attachments or request pre-warm where needed.
**References:** [Transit Gateway quotas](https://docs.aws.amazon.com/vpc/latest/tgw/transit-gateway-quotas.html)

### NET3 — VPC endpoint capacity
**Why:** Interface endpoints on the critical path can throttle service traffic at
peak.
**Steps:** Validate endpoint throughput against peak; scale endpoints / ENIs as
needed.
**References:** [Interface VPC endpoints](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html)

### NET4 — Support pre-warm
**Why:** Pre-warming NAT/TGW/ELB cannot be done instantly on event day.
**Steps:** Where load tests approach NAT/TGW/ELB limits, request pre-warming
through AWS Support ahead of the event with your tested peak numbers.
**Day-of mitigation:** None — submit early; a near-event gap is residual risk.
**References:** [AWS Support](https://aws.amazon.com/support/)

---

## DAT — Data & State Stores

### DAT1 — DynamoDB warm throughput vs peak
**Why:** A table throttles at the spike only if its **warm throughput** — the level
it can serve instantly, reflecting historical / previously-provisioned peak — is below
the event peak. Billing mode alone doesn't decide this: an on-demand table that was
previously provisioned high already carries that capacity.
**Steps:** Read `DescribeTable.WarmThroughput` and compare to the projected peak. If it
already covers the peak, no action. If below (or a new on-demand table at the
12,000 RCU / 4,000 WCU floor), **pre-warm** by raising warm throughput via UpdateTable
ahead of the event (no billing-mode change needed), or provision sized to peak. Ensure
access is well-distributed so no single partition (~3,000 RCU / 1,000 WCU) throttles.
Warm throughput can't be decreased once raised, and pre-warming carries a one-time cost.
**References:** [Understanding DynamoDB warm throughput](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/warm-throughput.html) · [Pre-warming DynamoDB tables](https://aws.amazon.com/blogs/database/pre-warming-amazon-dynamodb-tables-with-warm-throughput/)

### DAT6 — Amazon Keyspaces warm throughput vs peak
**Why:** A Keyspaces table throttles at the spike only if its **warm throughput** —
what it can serve instantly, reflecting prior on-demand peak or previously-provisioned
capacity — is below the event peak. Capacity mode alone doesn't decide this: a
PAY_PER_REQUEST table previously provisioned high already carries that capacity.
**Steps:** Read the table's warm throughput (`GetTable`) and compare to the projected
peak. If it covers the peak, no action. If below (or a new on-demand table at the
12,000 RCU / 4,000 WCU floor), **pre-warm** by raising warm throughput ahead of the
event (no capacity-mode change needed), or switch to PROVISIONED sized to peak.
Distribute access — each partition caps at 3,000 RCU / 1,000 WCU — so a hot partition
doesn't throttle below the table's warm throughput.
**References:** [Configure pre-warming for Keyspaces tables](https://docs.aws.amazon.com/keyspaces/latest/devguide/warm-throughput.html) · [Keyspaces read/write capacity modes](https://docs.aws.amazon.com/keyspaces/latest/devguide/ReadWriteCapacityMode.html)

### DAT2 — ElastiCache sizing & pre-warm
**Why:** Undersized clusters or hot shards throttle the cache at peak; Serverless
needs lead time to scale out.
**Steps:** Size provisioned clusters for peak connections/throughput; validate
shard distribution to avoid hot keys; for ElastiCache Serverless, pre-warm ≥ 60
min before the ramp.
**References:** [ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html)

### DAT3 — RDS / Aurora read scaling
**Why:** Read load at peak can overwhelm a writer-only or under-replicated
cluster.
**Steps:** Scale read replicas to peak count beforehand; consider Aurora
Serverless v2 where the profile is uncertain (scales in seconds). Reuse
`rds-operation-review` for the deep dive.
**References:** [Aurora Serverless v2](https://aws.amazon.com/rds/aurora/serverless/)

### DAT4 — Session-token caching
**Why:** Validating every request against the identity database bottlenecks the
login surge.
**Steps:** Cache session tokens (e.g. in ElastiCache) so repeated validation
doesn't hit the DB.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (architectural evaluation — identity & session)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### DAT5 — Identity login-rate validation
**Why:** The event drives a subscriber/login surge independent of streaming
traffic.
**Steps:** Load-test the identity platform to the pre-event login/signup rate
(cross-ref TST3); fix token throttling and write contention found. **For third-party
IdPs (social OAuth: Google / Facebook / Apple ID, or an identity vendor), confirm the
provider's per-tenant request-rate limits ahead of the event** — they cannot be raised
on event-day, and a cold limit on the social-sign-in path can bottleneck before your
own identity DB does.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (two tests the pipeline won't catch)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### DAT7 — DRM license-server capacity & token caching
**Why:** DRM-protected delivery issues a license request per playback session (and
again on key rotation). At scale, the limiter is almost always the **third-party
license server** behind SPEKE (Verimatrix / EZDRM / Irdeto / Axinom / self-hosted) and
its per-tenant capacity ceiling — not CloudFront or MediaPackage. A license-server
saturation at kickoff is a black-screen incident even when every other service is green.
**Steps:**
1. Identify the DRM key provider from the packager configuration (`mediapackage` or
   `mediapackagev2` encryption settings: SPEKE URL + system IDs for Widevine / PlayReady
   / FairPlay). Grade DAT7 N/A for non-DRM delivery.
2. **Confirm with the vendor** the license-request rate the provider can sustain at the
   projected peak concurrency × key-rotation frequency; get it in writing on the
   Countdown engagement (SUP2).
3. **Stagger license-renewal windows** so renewals don't cluster into a secondary spike
   mid-event (e.g. rotate every N seconds with a random offset per session).
4. In the player SDK, **cache short-lived DRM entitlement tokens** and refresh lazily so
   each key request does not round-trip to the identity service.
5. Test the full license-acquisition path at event concurrency during the production
   rehearsal (TST1); watch for 429 / 503 from the license endpoint.
**Day-of mitigation:** If vendor capacity cannot be confirmed in time, consider
**lengthening the key-rotation interval** for the event window (fewer renewals), and align
with the vendor on an **emergency-rate-raise contact** for the event bridge.
**References:** [SPEKE 2.0 — Secure Packager and Encoder Key Exchange](https://docs.aws.amazon.com/speke/latest/documentation/what-is-speke.html) · [MediaPackage DRM encryption](https://docs.aws.amazon.com/mediapackage/latest/userguide/content-encryption.html)

---

## TST — Testing & Chaos

### TST1 — Staged testing gates
**Why:** Each layer fails differently; a single test gives false confidence.
**Steps:** Run the four gates in order — component (≈2× component peak) →
integration (platform peak) → full-scale production rehearsal (1.3–1.5× peak) →
spike & failure. The production rehearsal is the definitive validation.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (a staged testing approach)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### TST2 — Realistic load profile
**Why:** Zero-to-peak ramps surface the wrong failure modes and misjudge scaling.
**Steps:** Ramp over ~60 min, sustain 2–3 h with periodic 20–40% spikes, then
decline; inject a 50% spike within 60 s from a ~70% baseline for spike testing.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (designing realistic load test profiles)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### TST3 — Identity & signup surge test
**Why:** The pipeline scale test never exercises signup/auth/payment.
**Steps:** Test the full signup-to-first-play journey at peak signup rate; watch
token-service throttling, account-creation write contention, and payment-provider
rate limits.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (two tests the pipeline won't catch)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### TST4 — Ad-decisioning path test
**Why:** A slow/failing ad decision can stall the player instead of dropping the
ad. And a tracking-pixel pipeline that throttles during the ad window loses the
monetization record for that break even when the ad itself was served.
**Steps:** Test ad decisioning at event concurrency; confirm the ADS/VAST endpoint
sustains the projected request rate and timeout budgets hold; confirm the player
skips to content / shows slate when the ad service is slow or unavailable;
**load-test the ad-tracking beacon pipeline** (impression / quartile / completion
pixels) at peak concurrency so the tracking endpoint and its downstream analytics
pipeline (OBS6) hold under the per-break surge, not just baseline.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (the ad-decisioning path)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### TST5 — Chaos / FIS experiments
**Why:** Controlled failure finds weaknesses before viewers do.
**Steps:** Build AWS FIS experiments with stop conditions that halt on viewer
impact: dependency-latency injection (confirm circuit breakers trip before
playback), and compute termination (EKS pods / EC2) — confirm reschedule,
deregistration, absorption, and auto-scaling replacement inside steady state.
**References:** [AWS Fault Injection Service](https://docs.aws.amazon.com/fis/)

### TST6 — Steady state in viewer terms + blast-radius order
**Why:** Experiments need a viewer-defined pass/fail and a safe ramp.
**Steps:** Define steady state as viewer metrics (e.g. VST < 3 s, rebuffer <
0.5%, error < 0.1%); run experiments nonprod → prod low traffic → moderate →
full-scale load test.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (chaos engineering for streaming platforms)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### TST7 — External dependencies & cross-team sign-off
**Why:** A scale test throttled by an unprepared CDN, ad system, or origin vendor
wastes an expensive test and hides your real ceiling.
**Steps:** Before the test, engage every external dependency (CDN, ad/ADS, origin,
other backend vendors) and the relevant AWS service teams; confirm each can sustain
the target load and has signed off. Agree per-team success criteria so every
participant knows their pass/fail. Prepare source content that mimics the production
signal (manifest size, ad-break frequency, number of origins).
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (engaging AWS Support)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

---

## OBS — Observability & Steady State

### OBS1 — Viewer-experience SLIs
**Why:** Component dashboards don't tell you what viewers experience.
**Steps:** Instrument video start time (VST), video start failures (VSF), video
playback failures (VPF), rebuffering ratio, and playback error rate as first-class
metrics and alarm on them. Correlate client-side QoE with CDN performance by
enabling CMCD fields in CloudFront real-time logs and joining on the shared
session ID.
**References:** [Streaming Media Lens SMPERF04-BP01 (real user logs & metrics)](https://docs.aws.amazon.com/wellarchitected/latest/streaming-media-lens/smperf04-bp01.html) · [CloudFront CMCD in real-time logs](https://aws.amazon.com/about-aws/whats-new/2024/04/amazon-cloudfront-cmcd-fields-real-time-logs/)

### OBS2 — Alarms onboarded early
**Why:** Monitoring stood up during the event is unproven when it matters.
**Steps:** Onboard critical workloads and alarms weeks ahead so monitoring is
proven; validate during the rehearsal.
**References:** [Preparing for large-scale live streaming events on AWS — Part 2 (engaging aws support)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### OBS3 — Capacity-headroom dashboards
**Why:** Event-day decisions need headroom visibility, not just error rates.
**Steps:** Build dashboards showing quota utilization, NAT/TGW, DB/cache, and
compute headroom across the critical path.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (capacity planning)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### OBS4 — Alarm coverage on critical-path services
**Why:** An unalarmed critical service fails silently — you learn about it from
viewers, not the system, which lengthens MTTR exactly when seconds count.
**Steps:** For each critical-path service with no actionable alarm in any tool,
create one on its primary failure/saturation signal, bound to a notification or
auto-action (CloudWatch alarm → SNS/incident tool, or the equivalent in the
customer's observability platform). Prove each fires in the rehearsal (ties to
OBS2). Where a third-party platform owns alerting, confirm the critical-path
services are covered there and the routing reaches on-call — this cannot be read
via AWS access, so confirm it manually rather than assuming.
**References:** [Using CloudWatch alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)

### OBS5 — Measurable success criteria & KPI threshold matrix
**Why:** Without an agreed definition of success, "ready" is subjective and alarms
have no principled thresholds.
**Steps:** With stakeholders, document glass-to-glass KPIs and a warning/critical/
failure threshold matrix (e.g. VPF < 0.05%, a VST target, a rebuffer ceiling, event-
window uptime), derived from past-event data and industry benchmarks; map each
threshold to the alarm/severity model (OBS1/OBS4) so monitoring enforces the agreed
criteria. Get explicit sign-off before the event.
**References:** [Streaming Media Lens](https://docs.aws.amazon.com/wellarchitected/latest/streaming-media-lens/streaming-media-lens.html)

### OBS6 — Telemetry / analytics pipeline headroom
**Why:** The signal pipeline — Kinesis Data Streams / Firehose / MSK carrying CMCD,
QoE beacons, ad-tracking pixels, and session heartbeats — scales reactively or on
provisioned shards. At peak concurrency, a throttling or lagging pipeline **blinds
the OBS pillar** (OBS1/OBS4) exactly when the viewer SLIs matter most, and ad-tracking
loss directly affects monetization reporting.
**Steps:**
1. Identify every stream/delivery-stream carrying event-critical telemetry.
2. For Kinesis in `PROVISIONED` mode, size the shard count against **peak records/s
   and MB/s** (per-shard limits: 1,000 records/s, 1 MB/s write; 2 MB/s read). For
   `ON_DEMAND`, confirm `WriteProvisionedThroughputExceeded` has been flat on previous
   comparable loads — on-demand scales but with a reactive lag.
3. Confirm `GetRecords.IteratorAgeMilliseconds` stays flat under the production
   rehearsal (TST1) — a rising iterator age during the ramp means consumers are
   falling behind, not the shard being throttled.
4. For Firehose, confirm the delivery-stream throughput quota (buffer size × delivery
   interval) covers peak; raise ahead of the event if needed.
5. For MSK, reuse `msk-operations`.
6. Alarm on `WriteProvisionedThroughputExceeded`, `IteratorAge` growth, and Firehose
   `DeliveryToS3.DataFreshness` so a telemetry stall is itself a critical alarm.
**Day-of mitigation:** If Kinesis is still `PROVISIONED` with insufficient shards near
the event, consider switching to `ON_DEMAND` (allowed once every 24 h per stream) —
accept the reactive lag over definite throttling. For Firehose, raise the throughput
quota via Service Quotas (not instant).
**References:** [Kinesis Data Streams quotas and limits](https://docs.aws.amazon.com/streams/latest/dev/service-sizes-and-limits.html) · [Kinesis Data Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)

---

## SUP — Operational Readiness & Support

### SUP1 — Account team + WAFR
**Why:** The cross-functional WAFR uncovers hidden coupling (e.g. identity rate
limits rejecting signup traffic) that no single team sees.
**Steps:** Engage the AWS account team 12–16 weeks out; run a Well-Architected
Review focused on Reliability and Performance Efficiency; produce a prioritized
risk report.
**References:** [Well-Architected Framework Review](https://docs.aws.amazon.com/wellarchitected/latest/userguide/wa-framework-review.html)

### SUP2 — Event support engagement
**Why:** Preparation surfaces risks but can't respond to them live; designated
specialists who know your architecture can.
**Steps:** Engage AWS Unified Operations for Media (preferred) or AWS Countdown
Premium; onboard workloads/alarms weeks ahead (2–3 wk minimum, 8–12 wk for
complex events) so the team can join load testing. Unified Operations for Media
includes **IDR (Incident Detection and Response)** monitoring — AWS watches your
defined thresholds and an incident manager opens a case and joins a bridge within
minutes of a breach; confirm critical workloads are onboarded to IDR.
**References:** [Unified Operations for Media](https://aws.amazon.com/premiumsupport/unified-operations-team/) · [AWS Countdown](https://aws.amazon.com/premiumsupport/aws-countdown/) · [AWS Incident Detection and Response](https://docs.aws.amazon.com/IDR/latest/userguide/what-is-idr.html)

### SUP3 — Change freeze & event-day discipline
**Why:** Deploys during the event window add avoidable risk.
**Steps:** Institute a change freeze ~1 week before; make event day "monitor,
don't deploy" with all capacity in place hours before start.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (the capacity planning timeline)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### SUP4 — Cross-functional runbooks
**Why:** Documenting expected behavior and failure modes across teams uncovers
issues before the event.
**Steps:** Have platform engineering, operations, and security jointly document
end-to-end behavior and runbooks for the critical path and its failure modes. For
each KPI threshold (OBS5), add a standard operating procedure with explicit
ownership, resolution steps, an escalation path, and the SLA it must meet; validate
the runbooks in a dress rehearsal so roles are exercised before event day.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (architectural evaluation)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)


### SUP5 — Business-driven demand shaping
**Why:** Technology alone doesn't solve demand scaling; business decisions turn a
spike into a ramp.
**Steps:** Broadcast pre-event programming 2–3 h before to bring viewers in
gradually; run early signup campaigns to spread auth/payment load; load
personalization and secondary UI asynchronously so the core player initializes
first.
**References:** [Preparing for large-scale live streaming events on AWS — Part 1 (business-driven demand shaping)](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)

### SUP6 — Event-day communication plan & roles
**Why:** When issues hit, unstructured information-gathering lengthens MTTR; a
defined comms structure keeps the bridge focused and stakeholders informed.
**Steps:** Define and rehearse (in game-day sims) a communication plan: a Comms
Manager who aggregates updates and issues a single stakeholder update on a fixed
cadence; a designated reporter per team feeding the Comms Manager ~10 min before
each cycle; bridge etiquette (stay muted unless speaking, address individuals/teams
directly, move investigations to side bridges, keep IM threaded by topic); and a log
of key actions/timestamps for the retrospective. Define a sequenced event
off-boarding (e.g. stop contribution sources before stopping MediaLive to avoid
false input alarms; verify Live-to-VOD exports) with producer/director approval per
step.
**References:** [AWS Well-Architected Framework — Operational Excellence pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html) · [Preparing for large-scale live streaming events on AWS — Part 2](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)

### SUP7 — Live-captions & accessibility path tested
**Why:** For broadcast-grade live events live captions are frequently a **regulatory
requirement** (FCC in the US, Ofcom in the UK, broadcast-license commitments in many
markets) and always an editorial expectation for premium content. A caption failure
during a live event is both a viewer-impact incident and a compliance incident; the
captioning stack is multi-vendor (ingest + encoder caption pass-through + packager +
player) and no single component owns the end-to-end test.
**Steps:**
1. Identify the captioning architecture: CEA-608/708 pass-through from MediaLive,
   WebVTT from a third-party captioner (Ai-Media, EEG, Enco), Amazon Transcribe Live,
   or a hybrid.
2. **Confirm third-party captioner capacity** with the vendor at the event duration
   and concurrency; get it in writing (SUP2).
3. Test the full path end-to-end **in the production rehearsal (TST1)** — captions
   present and legible in every target player (web, iOS, Android, tvOS, STB) with
   acceptable latency.
4. Define a **documented fallback**: switch to a backup captioner, degrade to
   auto-generated captions (Transcribe), or disable captions with an on-screen
   notice — whichever is acceptable to the compliance/editorial owner.
5. Add captioning health to the event-day comms plan (SUP6): a designated reporter
   watches the caption output and escalates.
**Day-of mitigation:** Pre-align with the backup captioner, confirm the on-screen
notice copy with the editorial lead, and keep the switchover runbook open on the
event bridge.
**References:** [AWS Elemental MediaLive captions](https://docs.aws.amazon.com/medialive/latest/ug/captions.html) · [Amazon Transcribe Live](https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html)
