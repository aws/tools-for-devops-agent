# Changelog

All notable changes to the `live-streaming-event-readiness-review` skill are
documented here.

## [1.0.0] - 2026-10-30

### Added
- Initial release. Read-only, graded large-scale live event (LSE) readiness
  review across nine pillars: Capacity & Scaling (CAP), Service Quotas (QTA),
  Resilience (RES), Content Delivery (CDN), Networking (NET), Data & State
  (DAT), Testing & Chaos (TST), Observability (OBS), and Operational Readiness
  & Support (SUP).
- `references/best-practices.md` — **61 canonical checks** with PASS criteria
  and severity, grounded in *Preparing for large-scale live streaming events
  on AWS* (blog Parts 1 & 2), the Streaming Media Lens:
  - **CAP (9):** instance diversification, future-dated ODCRs, EKS control-plane
    pre-provisioning (incl. an EKS Auto Mode branch that grades pre-scaled
    workloads / resource requests / startup time), warm capacity & fast pod
    starts, Lambda provisioned concurrency, ELB LCU reservation, pre-provisioned
    minimum capacity, capacity-planning timeline tracking, and EBS volume
    performance / snapshot-restore initialization (gp3 IOPS/throughput sizing,
    Fast Snapshot Restore vs lazy-load first-access latency).
  - **QTA (5):** EC2 vCPU, NAT/EIP, Lambda concurrency, ELB quotas, and
    early-submission discipline — authoritative values via `service-quota-check`.
  - **RES (7):** multi-Region active-active, DNS-based failover (Route 53 health
    checks + optional Route 53 ARC sub-TTL shed, paired with CDN5/CDN8), service
    isolation, graceful-degradation hierarchy, stateless compute, maintenance
    overlap via `aws-health-events`, and version lifecycle / auto-upgrade
    exposure (EKS / RDS / OpenSearch / ElastiCache / MSK / Lambda; authoritative
    EOL signal is AWS Health, cross-ref `eks-upgrade-readiness`).
  - **CDN (9):** CloudFront with single consistent origin, Origin Shield, cache-
    hit ratio / manifest-vs-segment TTL discipline (SMPERF03-BP02 / SMCOST01-BP02
    / MediaPackage CDN recommendations), CloudFront Functions vs Lambda@Edge
    placement, origin redundancy via CloudFront origin groups, **S3-origin
    per-prefix request-rate scaling** (~5,500 GET/s per partitioned prefix),
    **MediaTailor (SSAI) playback configuration + PrefetchSchedule for scheduled
    ad breaks + player slate / graceful fallback**, **multi-CDN with client-side
    switching** for tier-1 events, and **LL-HLS / CMAF latency-vs-cache tradeoff**
    where sub-5s latency is promised.
  - **NET (4):** NAT (PeakPacketsPerSecond leading indicator, ErrorPortAllocation,
    PacketsDropCount; ceilings ~10M pps, ~55k conn/dest), Transit Gateway
    per-attachment throughput (BytesIn/Out vs ~100 Gbps), VPC endpoint capacity,
    and Support pre-warms (NET4) with the ~5-minute reactive-ramp decision rule.
  - **DAT (7):** **DynamoDB warm throughput vs peak** (`DescribeTable.WarmThroughput`,
    12,000 RCU / 4,000 WCU floor, 3,000/1,000 hot-partition caveat), ElastiCache
    sizing + ≥60-min Serverless pre-warm, RDS/Aurora read scaling via
    `rds-operation-review`, session-token caching, identity login-rate validation
    (incl. third-party IdP per-tenant limits), **Keyspaces warm throughput vs
    peak** (parallel to DynamoDB), and **DRM license-server capacity & token
    caching** (SPEKE key provider vendor confirmation at projected peak license-
    request rate, staggered key-renewal windows, player-SDK token caching).
  - **TST (7):** four staged gates (component → integration → full-scale
    production rehearsal at 1.3–1.5× peak → spike+failure), viewer-realistic
    ramp profile (~60-min ramp, 2–3 h sustain with 20–40% spikes, decline;
    codec/protocol mix; multi-origin spread), identity/signup surge test, ad-
    decisioning path test (ADS/VAST capacity + ad-tracking beacon volume), AWS
    FIS experiments with stop conditions, viewer-term steady state (VST < 3s,
    rebuffer < 0.5%, error < 0.1%), and external-dependency cross-team sign-off
    before the test.
  - **OBS (6):** viewer SLIs (VST / VSF / VPF / rebuffer / error) correlated
    with CDN via CMCD in CloudFront real-time logs, early alarm onboarding,
    capacity-headroom dashboards, **tool-agnostic alarm coverage** (CloudWatch
    *or* a declared third-party platform — Datadog / New Relic / Grafana /
    Splunk / Dynatrace; missing CloudWatch alarms is a FAIL only if no
    third-party tool covers the service), measurable success criteria & KPI
    threshold matrix with stakeholder sign-off, and **telemetry / analytics
    pipeline headroom** (Kinesis / Firehose / MSK carrying CMCD, QoE beacons,
    ad-tracking pixels, session heartbeats).
  - **SUP (7):** AWS account team + WAFR 12–16 weeks out, Unified Operations
    for Media (incl. IDR) or Countdown Premium (2–3 wk minimum, 8–12 wk for
    complex events), change freeze with event-day monitor-don't-deploy,
    cross-functional runbooks with KPI-breach SOPs, business-driven demand
    shaping, event-day communication plan & roles (Comms Manager, per-team
    reporters, update cadence, bridge etiquette, off-boarding sequence), and
    **live-captions & accessibility path tested** end-to-end for events where
    captions are a regulatory requirement (FCC, Ofcom, broadcast license) or
    an editorial commitment.
- `references/discovery.md` — read-only discovery calls per pillar, including
  MediaTailor (`list-playback-configurations` / `get-playback-configuration` /
  `list-prefetch-schedules`), MediaPackage / MediaPackagev2 SPEKE encryption
  reads for DRM, Kinesis / Firehose / MSK reads for OBS6, MediaLive caption-
  output reads for SUP7, Amazon IVS channel reads for the IVS applicability
  gate, and Route 53 ARC routing-control reads for RES2.
- `references/remediations.md` — per-check remediation blocks with timeline
  milestones, day-of mitigations where the event is too close for full
  remediation, and authoritative AWS references.
- `references/reuse-skills.md` — delegation map to `service-quota-check`,
  `aws-eks-operations-review`, `ecs-operation-review`, `rds-operation-review`,
  `msk-operations`, `aws-health-events`, `eks-upgrade-readiness`,
  `support-cases`, and `investigation-cost-guardrail`, with ordering and
  boundaries. Graceful degradation when a companion isn't installed, reported
  in the §7 Coverage note.
- `references/report-format.md` — single-message Markdown report contract with
  §1 Executive summary → §2 Event & architecture snapshot → §3 Prioritized
  action plan → §4 Detailed findings → §5 full-canonical-ID Scorecards → §6
  Timeline status → §7 What was not assessed + Companion-skill coverage.
- `evals/evals.json` — nine positive readiness scenarios (full readiness on
  EKS; capacity pre-warm incl. DynamoDB + Keyspaces warm-throughput; CDN +
  Origin Shield audit; testing & chaos; near-event residual risk; third-party
  (Datadog) alarm coverage; success-criteria + comms plan; MediaTailor SSAI +
  DRM; Amazon IVS applicability) plus three negative trigger queries
  (media-pipeline encode question, event-day incident, unrelated Lambda/S3).
- `cloudformation/devops-agent-skill-policies/` — custom IAM policy
  `DevOpsAgentSkill-LiveStreamingEventReadinessReview` granting the MediaTailor
  and Route 53 ARC read-only actions that are not in the base
  `AIDevOpsAgentAccessPolicy` (`mediatailor:ListPlaybackConfigurations`,
  `mediatailor:GetPlaybackConfiguration`, `mediatailor:ListPrefetchSchedules`,
  `route53-recovery-cluster:ListRoutingControls`). Toggleable via the
  `EnableLiveStreamingEventReadinessReview` parameter.
- Defensive applicability gates for IAM `AccessDenied` on `mediatailor:*`
  (CDN7 → N/A-with-reason, confirm SSAI from S1 context) and on
  `route53-recovery-cluster:ListRoutingControls` (RES2 ARC branch → N/A, base
  DNS-failover path still grades). Keeps the skill robust when the base
  `AIDevOpsAgentAccessPolicy` is deployed without the custom policy attached.

### Design decisions
- **Reuse-first orchestrator.** This skill owns the LSE-specific checklist and
  the cross-pillar risk view; it delegates per-service depth to existing
  companion skills rather than re-implementing them. When a companion is
  absent, the skill degrades to direct read-only discovery, marks the affected
  pillar as reduced-depth, and records the gap in the Coverage note so it is
  never silent.
- **Evidence-first grading with "present but unprepared = FAIL".** Every
  verdict needs observed evidence — missing evidence is **N/A with a reason**,
  never a PASS. For CAP and DAT, however, a resource that exists but is not
  configured for the event peak (idle, default/minimum throughput, on-demand
  with no pre-warm plan, no pre-scaled minimums) is a capacity **risk** for
  the spike, not a blank — it is graded FAIL with the pre-event action.
- **Warm throughput, not billing mode, for DynamoDB and Keyspaces** (DAT1 /
  DAT6). An on-demand table whose warm throughput already covers the peak
  (previously provisioned high) is correctly PASSED, not failed as "cold". A
  new on-demand table at the 12,000 RCU / 4,000 WCU floor is correctly
  flagged. Hot-partition caveat (3,000 RCU / 1,000 WCU) called out.
- **Tool-agnostic alarm coverage** (OBS4). The DevOps Agent reads AWS state
  only — it cannot inspect Datadog / New Relic / Grafana / Splunk / Dynatrace.
  Empty CloudWatch `describe-alarms` is not an auto-FAIL; third-party coverage
  asserted but not machine-verifiable is **N/A pending manual confirmation**,
  never auto-PASS; a critical-path service with no actionable alarm in any
  tool is a FAIL.
- **Near-event residual-risk framing.** Manual quota increases, future-dated
  ODCRs, and AWS Support pre-warms can't be done event-day — within the lead
  window they are labeled **residual risk** with a day-of mitigation, not a
  fully fixable gap.
- **S0 — deliver an assessment in-turn, state assumptions, never end with
  only clarifying questions**, plus a single-pillar fast path so a focused
  prompt (e.g. "do we have alarms on our critical services?") gets that
  pillar's graded findings fast, not a full nine-pillar sweep that may not
  finish inside the turn.
- **Canonical-checklist fidelity** enforced in three places: the S3 grading
  step mandates grading every canonical check by its exact ID / meaning /
  severity with no drop / renumber / re-bucket / invent (out-of-scope →
  N/A-with-reason, never omitted); `report-format.md` §5 requires the full
  canonical ID set in the scorecard; the S6 self-validation gate re-checks it
  before render. This is the belt-and-suspenders fix for the drift pattern
  where the agent synthesizes its own per-pillar checklist from a long
  reference, reuses IDs for different checks, drops real checks, invents
  non-canonical ones, or re-rates severities.

### Scope boundary
- Proactive readiness review only. **Not** an event-day incident tool and
  **not** a media-pipeline encode/package scale test. For tier-1 live events
  this skill is **complementary to a pipeline-side review** grounded in the
  Streaming Media Lens Reliability best practices SMREL01 (redundant
  contribution via MediaConnect), SMREL02 (redundant live encoding via
  MediaLive dual-pipeline / input failover), and SMREL03 (origin redundancy
  via MediaPackage / CDN failover). The two reviews are complementary, not
  substitutes.
