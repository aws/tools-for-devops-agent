# Live Streaming Event Readiness Review skill

This skill gives the AWS DevOps Agent a read-only, graded readiness review that tells a streaming / OTT platform team whether they are ready for a large-scale live event (LSE), where the risks are, and how to remediate them — weeks before the event, not during it.

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Validate in a non-production environment first. All output
> is AI-generated and must be independently verified before you rely on it for an
> event.

It grades nine pillars as PASS / FAIL / N/A with evidence and severity, delegates
per-service depth to existing skills, and renders a prioritized action plan in
the response. It never mutates resources: every remediation is a proposal for
human approval, and capacity actions (pre-warm, ODCR, quota increase, change
freeze) are deliberate customer actions.

## Purpose

A large-scale event pushes concurrency to multiples of the daily baseline within
minutes, sustains it for hours, then drops — live, in public, with no second
take. Reactive auto scaling alone cannot absorb that. This skill assesses the
application platform and the AWS primitives around the media pipeline (compute,
delivery, state, networking, quotas, testing, support) — the part teams most
consistently underestimate — against AWS's published LSE guidance.

## Grounded in

- *Preparing for large-scale live streaming events on AWS* —
  [Part 1: strategy, architecture, capacity planning](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-1/)
  and
  [Part 2: content delivery, nonfunctional testing, chaos engineering, support](https://aws.amazon.com/blogs/media/preparing-for-large-scale-live-streaming-events-on-aws-part-2/)
- [Streaming Media Lens — AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/streaming-media-lens/streaming-media-lens.html)

## Key capabilities

- Confirm event context (date/window, expected peak concurrency, Regions,
  critical viewer path) and frame every finding against the weeks-to-event
  capacity-planning timeline.
- Grade 61 checks across nine pillars (CAP, QTA, RES, CDN, NET, DAT, TST, OBS,
  SUP) with evidence and severity.
- Highlight risks in viewer terms (video start time, rebuffering, errors) and
  produce a severity-ranked action plan with remediations and day-of mitigations.
- Flag near-event items that can no longer be fully remediated (manual quota
  increases, future-dated ODCRs, Support pre-warms) as residual risk.
- Reuse existing skills for depth instead of re-implementing them.

## Nine pillars

| Pillar | Focus |
|---|---|
| CAP — Capacity & Scaling | Instance diversification, ODCRs, EKS control-plane pre-provisioning, warm capacity, Lambda provisioned concurrency, LCU reservation, pre-provisioned minimums, EBS volume performance/initialization |
| QTA — Service Quotas | EC2 vCPU, NAT, Lambda, ELB, and critical-path quota headroom and early increases |
| RES — Resilience | Multi-Region active-active, DNS failover (incl. Route 53 ARC), service isolation, graceful degradation, statelessness, maintenance overlap, version lifecycle |
| CDN — Content Delivery | CloudFront + single origin, Origin Shield, cache-hit ratio / TTL discipline, edge-compute placement, origin failover, S3-origin request-rate scaling, MediaTailor (SSAI) prefetch & player fallback, multi-CDN with client-side switching, LL-HLS / CMAF latency-vs-cache tradeoff |
| NET — Networking | NAT connection/bandwidth headroom, transit gateway bandwidth, endpoint capacity, Support pre-warms |
| DAT — Data & State | DynamoDB/Keyspaces warm-throughput vs peak, ElastiCache sizing/pre-warm, RDS/Aurora read scaling, session-token caching, identity login-rate (incl. third-party IdP limits), DRM license-server capacity |
| TST — Testing & Chaos | Staged load gates, realistic ramp profiles, identity/signup + ad-decisioning (ADS + tracking beacons) tests, AWS FIS experiments, viewer-term steady state |
| OBS — Observability | Viewer-experience SLIs (incl. VSF/VPF, CMCD), tool-agnostic alarm coverage, measurable success criteria / KPI thresholds, capacity-headroom dashboards, telemetry pipeline (Kinesis / Firehose / MSK) headroom |
| SUP — Operational Readiness & Support | Account team + WAFR, Unified Operations for Media / Countdown Premium, change freeze, runbooks, demand shaping, event-day comms plan, live-captions / accessibility path |

## Companion skills — install these alongside

This skill is an **orchestrator**: it owns the LSE checklist and cross-pillar risk
view and delegates per-service depth to the skills below. It **degrades gracefully**
when a companion is absent (it falls back to direct read-only discovery), but depth
is reduced and some checks drop to N/A — so for a real review, install the companions
too. Every generated report states which companions were available and which were
missing (see the Coverage note), so a reduced-depth run is never silent.

| Companion skill | Adds depth to | Without it |
|---|---|---|
| `service-quota-check` | QTA, NET, CAP5 | quota headroom estimated, not authoritative |
| `aws-eks-operations-review` | CAP, RES (EKS) | EKS compute graded from basic discovery only |
| `ecs-operation-review` | CAP, RES (ECS) | ECS/Fargate depth limited |
| `rds-operation-review` | DAT3 | RDS/Aurora resilience depth limited |
| `msk-operations` | OBS/DAT (if MSK) | MSK not deeply assessed |
| `aws-health-events` | RES6 | maintenance / EOL-event overlap from basic Health query only |
| `eks-upgrade-readiness` | RES7, SUP3 | EKS version / end-of-support upgrade risk not deeply assessed |
| `support-cases` | SUP context | open-case risk not surfaced |
| `investigation-cost-guardrail` | whole review | review not cost-bounded |

**Install them the same way as this skill** — Import from repository (point at each
`skills/<name>` directory in `aws/tools-for-devops-agent`) or upload each zip. See
`references/reuse-skills.md` for the full map and invocation order.

## Prerequisites

- AWS DevOps Agent with audited **read-only** access to the account(s) under
  review. The skill performs no mutations.
- Read-only permissions on the critical-path services, e.g.
  `cloudfront:GetDistributionConfig`, `cloudfront:ListDistributions`,
  `ec2:DescribeCapacityReservations`, `ec2:DescribeNatGateways`,
  `autoscaling:DescribeAutoScalingGroups`, `eks:DescribeCluster`,
  `lambda:GetProvisionedConcurrencyConfig`, `elasticloadbalancing:Describe*`,
  `dynamodb:DescribeTable`, `elasticache:Describe*`, `rds:Describe*`,
  `route53:List*`, `route53-recovery-control-config:List*`,
  `route53-recovery-cluster:ListRoutingControls`, `fis:List*`,
  `cloudwatch:GetMetricStatistics`, `health:DescribeScheduledChanges`,
  `mediatailor:ListPlaybackConfigurations`, `mediatailor:GetPlaybackConfiguration`,
  `mediatailor:ListPrefetchSchedules`, `mediapackage:ListChannels`,
  `mediapackage:DescribeOriginEndpoint`, `mediapackagev2:ListChannelGroups`,
  `mediapackagev2:GetOriginEndpoint`, `kinesis:ListStreams`,
  `kinesis:DescribeStreamSummary`, `firehose:ListDeliveryStreams`,
  `firehose:DescribeDeliveryStream`, `ivs:ListChannels`, `medialive:ListChannels`.
- Most of the above are already in the AWS managed policy `AIDevOpsAgentAccessPolicy`.
  The MediaTailor (CDN7) and Route 53 ARC (RES2 ARC branch) actions are **not** in the
  managed policy — attach the `DevOpsAgentSkill-LiveStreamingEventReadinessReview`
  policy from
  [`cloudformation/devops-agent-skill-policies/`](../../cloudformation/devops-agent-skill-policies/)
  to pick them up. Without it, CDN7 and the RES2 ARC branch gracefully degrade to
  N/A-with-reason (the skill does not fail on `AccessDenied`).
- For quota depth, the `service-quota-check` skill and its Service Quotas
  permissions.
- For EKS depth, the `aws-eks-operations-review` skill and an EKS access entry
  (see that skill's README).

## Limitations

- Proactive readiness review only — **not** an event-day incident tool and
  **not** a media-pipeline encode/package scale test.
- **Complementary to a pipeline-side review.** A full tent-pole check should pair
  this skill (the application platform + AWS primitives around the pipeline) with a
  media encode/package/origin review grounded in the Streaming Media Lens Reliability
  best practices (SMREL01/02/03). The two reviews are complementary, not substitutes.
- Testing/chaos (TST), observability onboarding (OBS), and support-engagement
  (SUP) pillars are largely evidence-based: without load-test results, FIS
  templates, runbooks, or engagement records, those rows are N/A, not PASS.
- Single-Region-by-design architectures are graded as risk observations for
  RES1/RES2, not automatic FAIL — the residual risk is recorded.
- Quota values, limits, and pre-warm/reservation state are never assumed; quota
  values come from `service-quota-check`.
- **Broad orchestrator — activation is probabilistic.** It triggers most reliably on
  holistic "are we ready for our live event" / full-readiness requests. On a narrow
  single-domain prompt (e.g. a pure CloudFront or quota question) the agent may
  answer directly or load a focused companion skill instead — which is acceptable.
  For a full review, invoke it explicitly (e.g. "run a large-scale live event
  readiness review for …").

## Agent types

- **Chat tasks** — conversational and proactive event-readiness review.

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)** — if a GitHub connection is
configured in your Agent Space, import directly from the repository, pointing to
the `skills/live-streaming-event-readiness-review` directory. See
[Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills).

**Option B: Upload as a zip file**

1. Zip the directory (allowed extensions only, excluding dev tooling):

   ```bash
   cd skills
   zip -r live-streaming-event-readiness-review.zip live-streaming-event-readiness-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' \
     -x '*/.git/*' '*/evals/*' '*/.skilleval.yaml' '*/CHANGELOG.md' '*/README.md' '*.DS_Store'
   ```

2. In the AWS DevOps Agent web app, go to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the zip (max 6 MB).
5. Select the agent type: **Chat tasks**.
6. Click **Upload**.

**Option C: Upload via the Asset API** — assign the skill to the `CHAT` agent
type. See
[Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to use this skill

Sample prompts:

- "We have a major match streaming live in 6 weeks, peak ~8x baseline, critical
  path on EKS in us-east-1 and eu-west-1. Review our large-scale event readiness."
- "Audit our CloudFront and origin setup for a big live event — live segments are
  4 seconds."
- "For our live event, have we done enough on capacity? Karpenter on EKS,
  DynamoDB sessions, ElastiCache."
- "Before our event, how do we prove the platform will hold? What load and chaos
  testing should we have done?"
- "Will our MediaTailor setup hold at halftime? We have scheduled ad breaks and a
  Widevine/PlayReady DRM path — readiness check please."
- "Our live event is in 4 days — quick readiness check, can we still fix
  everything?"
- "What AWS support engagement and operational practices should we have in place
  for a high-profile live stream?"

## Package layout

```text
live-streaming-event-readiness-review/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── .skilleval.yaml
├── references/
│   ├── best-practices.md     # 9 pillars, 61 canonical checks
│   ├── discovery.md          # read-only discovery calls per pillar
│   ├── remediations.md       # per-check remediation blocks + day-of mitigations
│   └── reuse-skills.md       # delegation map to existing skills
└── evals/
    └── evals.json            # positive + negative trigger scenarios with assertions
```
