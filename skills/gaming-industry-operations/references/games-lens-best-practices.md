# Games Industry Lens — canonical best-practice checklist

Source: [Games Industry Lens — AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/games-industry-lens/games-industry-lens.html)
(publication date December 9, 2025). The lens is also available as a custom lens for
the AWS Well-Architected Tool in the
[AWS Well-Architected custom lens GitHub repository](https://github.com/aws-samples/sample-well-architected-custom-lens/tree/main/games-industry-lens).

This file lists every best practice (BP) in the lens: **78 checks** across six pillars.
Grade each one that is in scope by its exact ID, meaning and lens risk level. Do not
drop, renumber, re-bucket or invent checks. Out-of-scope or unobservable checks are
**N/A with a reason**, never omitted.

Conventions used below:

- **Risk** is the lens's own "Level of risk exposed if this best practice is not
  established". Two BPs do not state a level in the lens; they are marked
  `Not stated (treat as Medium)`.
- **Verify** names the read-only evidence to look for. Every call is a read
  (`Describe*`, `List*`, `Get*`); the skill never changes a resource.
- **PASS when** is the observable condition. Missing evidence is N/A, not PASS.
- **Companion** names a skill in this repository that already grades the area in
  depth; prefer it when it is installed and fold its findings in.

Lens IDs are reproduced as published. Two pages carry irregular IDs in the lens itself
(`GAMESOPS04-BP01`; the `GAMESEC03-BP05` and `GAMESEC05-BP02` pages use `gamsec` in
their URLs). Use the IDs shown here.

---

## Pillar 1 — Operational excellence (12 BPs)

Lens design principles for this pillar: define measurable, achievable objectives for
game operations teams and adapt them; use operational runbooks to plan scaling for
launches and special events; establish an operating model for receiving,
investigating and responding to player support requests.

### GAMEOPS01 Live operations

#### GAMEOPS01-BP01 Use game objectives and business performance metrics to develop your live operations strategy — Risk: High
- Verify: documented targets for CCU, DAU/MAU, infrastructure budget, release cadence
  (for example "monthly content updates with no downtime"), maintenance windows and
  recoverability goals; whether a Live Ops team or on-call rotation exists.
- PASS when: the team can state its CCU/DAU targets and release/maintenance objectives,
  and alarms or dashboards exist for the metrics those targets depend on
  (`cloudwatch:DescribeAlarms`, `cloudwatch:ListDashboards`).
- Evidence is largely organizational: when it is not in the conversation or the
  account, grade N/A — "Interview needed", not FAIL.

### GAMEOPS02 Account structure

#### GAMEOPS02-BP01 Adopt a multi-account strategy to isolate different games and applications into their own accounts — Risk: High
- Verify: separate accounts (or at least OUs) for development, test/QA, staging,
  production, shared services/tools and security/log archive; AWS Organizations in
  use with OU-level policies (`organizations:DescribeOrganization`, `ListRoots`,
  `ListOrganizationalUnitsForParent`, `ListAccounts`, `ListPolicies`).
- PASS when: production game infrastructure is in its own account(s), isolated from
  dev/test, and the organization has OUs that mirror environments or titles.
- If Organizations reads are denied or the account is standalone, grade N/A with the
  reason and recommend the multi-account structure.

#### GAMEOPS02-BP02 Organize infrastructure resources using resource tagging — Risk: High
- Verify: a tagging policy with owner, game/project, studio, environment and resource
  role tags; tag coverage on the workload's resources (`tag:GetResources`); AWS Config
  `required-tags` rule or Organizations tag policies (`config:DescribeConfigRules`,
  `organizations:ListPolicies --filter TAG_POLICY`).
- PASS when: ≥ 90% of in-scope resources carry owner, environment and game/project
  tags, and tagging is enforced by Config or a tag policy. Partial coverage without
  enforcement is FAIL.

### GAMEOPS03 Game deployments

#### GAMEOPS03-BP01 Validate and test your existing core game systems and infrastructure before reusing it in your game — Risk: High
- Verify: reused components (login, inventory, matchmaking, telemetry SDKs, legacy
  services) are cataloged with known issues and covered by integration tests;
  high-risk legacy components replaced rather than worked around.
- PASS when: the team confirms a review and test pass for reused components.
  Otherwise N/A (Interview needed). Recurring incidents on a reused component are
  evidence toward FAIL.

#### GAMEOPS03-BP02 Conduct performance engineering before every release (or at least for major releases) — Risk: High
- Verify: APM or tracing in place (`xray:GetSamplingRules`, `xray:GetServiceGraph`,
  CloudWatch Application Signals via `application-signals:ListServices`), OS-level
  metrics collected (CloudWatch agent), and a pre-production review before major
  releases. For launches, AWS Countdown (Infrastructure Event Management) engagement.
- PASS when: tracing or APM covers the game backend's critical path and the team runs
  a performance review per major release.

#### GAMEOPS03-BP03 Load test early and often — Risk: High
- Verify: a load-testing setup (for example Distributed Load Testing on AWS, or Locust
  on EKS per the Guidance for Kubernetes-based game load testing), recorded
  baselines, and fault-injection experiments (`fis:ListExperimentTemplates`,
  `fis:ListExperiments`).
- PASS when: a load test ran against the current architecture with a recorded
  baseline, and at least one FIS or equivalent fault experiment exists for the
  critical path. Infrastructure that looks like a load generator (ASGs/EKS named
  `loadtest`, `locust`, `k6`, `gatling`) is supporting evidence, not proof.

#### GAMEOPS03-BP04 Adopt a deployment strategy that minimizes impact to players — Risk: High
- Verify: infrastructure as code (`cloudformation:ListStacks`, drift status via
  `DescribeStackResourceDrifts`; Terraform state cannot be read, ask); a rolling,
  blue/green or canary strategy (CodeDeploy deployment configs, ECS/EKS rolling
  update settings, Lambda aliases with weighted routing, GameLift fleet aliases).
- PASS when: production infrastructure is deployed from IaC and releases use rolling
  substitution, blue/green or canary so players are not kicked out for a deploy.
  For game servers, PASS also needs draining of active sessions before replacement
  (GameLift protection policy `FullProtection`, ASG lifecycle hooks, or a
  documented drain step).

#### GAMEOPS03-BP05 Pre-scale infrastructure required to support peak requirements — Risk: High
- Verify: a demand estimate for the next launch or in-game event, pre-scaled
  minimums (ASG `MinSize`/desired, GameLift fleet `MinSize` and location capacity
  via `gamelift:DescribeFleetLocationCapacity`, DynamoDB warm throughput or
  provisioned capacity, ElastiCache sizing), capacity reservations
  (`ec2:DescribeCapacityReservations`), and quota headroom (companion:
  `service-quota-check`).
- PASS when: pre-scale targets exist and are reflected in current minimums/
  reservations, or the event is far enough out that a dated plan exists. Reactive
  autoscaling alone for a known launch is FAIL.

### GAMESOPS04 Health monitoring

#### GAMESOPS04-BP01 Instrument the game to detect and monitor player-impacting issues — Risk: Not stated (treat as Medium)
- Verify: client telemetry and crash/error reporting reach a backend (Kinesis/Firehose
  streams, an analytics pipeline, or a third-party APM); backend services have
  alarms on error rate and latency; CloudWatch Synthetics canaries exercise login,
  matchmaking or session-join (`synthetics:DescribeCanaries`); no PII in client logs.
- PASS when: at least one player-journey canary or client telemetry stream exists and
  every player-facing service has an actionable alarm (CloudWatch or a declared
  third-party tool).

### GAMEOPS05 Load testing

#### GAMEOPS05-BP01 Choose the right stage, architecture, and load testing framework to meet your goals — Risk: High
- Verify: load tests are run at the stages that matter (early architecture validation,
  per sprint, pre-production, post-deployment), on an appropriate generator
  architecture (EC2, EKS, Fargate or Lambda) with a framework the team can operate
  (JMeter, Locust, Grafana k6, Gatling).
- PASS when: the approach is documented and the last pre-production test matches the
  current release. Otherwise N/A (Interview needed).

### GAMEOPS06 Optimize over time

#### GAMEOPS06-BP01 Monitor key game metrics to identify player trends and patterns, and use the information to improve the game — Risk: High
- Verify: a telemetry ingestion path (`kinesis:ListStreams`,
  `firehose:ListDeliveryStreams`, `kafka:ListClustersV2`), a data lake or warehouse
  (S3 + Glue/Athena, Redshift) and dashboards; clients buffer locally when the
  backend is unreachable.
- PASS when: gameplay telemetry is ingested, stored and queried; dashboards or
  reports exist for player trends.

#### GAMEOPS06-BP02 Update and adapt the load testing approach as the game changes — Risk: High
- Verify: load scenarios updated with new features and protocols; framework
  re-evaluated as the game changes; cost of the test rig reviewed.
- PASS when: the most recent load test includes the features shipped in the last
  major release. Otherwise N/A (Interview needed).

---

## Pillar 2 — Security (25 BPs)

Lens design principle for this pillar: monitor and moderate player usage behavior.

### GAMESEC01 Security foundations

#### GAMESEC01-BP01 Use roles and federated access, rather than the account root user, to perform actions on your AWS environment — Risk: High
- Verify: root user has MFA and no access keys (`iam:GetAccountSummary` →
  `AccountMFAEnabled`, `AccountAccessKeysPresent`); recent root activity in
  CloudTrail (`cloudtrail:LookupEvents`, `Username = root`); human access through
  IAM Identity Center or federation, not long-lived IAM users.
- PASS when: root MFA on, no root access keys, no root API activity in 90 days, and
  humans sign in through federation.

#### GAMESEC01-BP02 Use AWS Control Tower to quickly set up a multi-account environment on AWS — Risk: Medium
- Verify: Control Tower landing zone (`controltower:ListLandingZones`,
  `ListEnabledControls`) or an equivalent governed multi-account setup.
- PASS when: a landing zone with environment-based OUs exists. Standalone account:
  FAIL with recommendation; reads denied: N/A.

#### GAMESEC01-BP03 Use least privilege role policies that are tailored to specific job functions — Risk: Medium
- Verify: IAM Access Analyzer findings and unused-access analyzers
  (`access-analyzer:ListAnalyzers`, `ListFindingsV2`); roles for QA, Live Ops,
  developers are distinct; `AdministratorAccess` limited to break-glass roles.
- PASS when: no active external-access findings on game resources and admin
  permissions are confined to break-glass roles.

#### GAMESEC01-BP04 Use roles and federated access policies together with account level access policies to grant access to your AWS resources — Risk: Medium
- Verify: SCPs attached to production OUs (`organizations:ListPoliciesForTarget`),
  for example denying unapproved Regions or disabling of GuardDuty/CloudTrail.
- PASS when: production accounts are under at least one deny-style SCP guardrail.

#### GAMESEC01-BP05 Use a central identity provider — Risk: Medium
- Verify: IAM Identity Center enabled (`sso-admin:ListInstances`) or an external IdP
  federation (`iam:ListSAMLProviders`, `ListOpenIDConnectProviders`); count of IAM
  users with console passwords.
- PASS when: workforce access is federated and IAM users are limited to
  service/break-glass use.

### GAMESEC02 Ongoing security

#### GAMESEC02-BP01 Use ready to deploy templates for standard security practices — Risk: Medium
- Verify: AWS Config conformance packs (`config:DescribeConformancePacks`) and
  Security Hub CSPM standards (`securityhub:GetEnabledStandards`) enabled in
  production accounts; failed-control counts.
- PASS when: at least one standard (FSBP or CIS) is enabled with a review cadence.

### GAMESEC03 Identity and access management (players)

#### GAMESEC03-BP01 Determine your approach to identify and control player access to your game's environment and resources — Risk: High
- Verify: the player identity model is deliberate: anonymous/guest identities with
  account linking (Cognito identity pool `AllowUnauthenticatedIdentities`), username
  and password, and/or federated third-party IdPs (`cognito-idp:ListIdentityProviders`).
- PASS when: the model is documented and the configuration matches it (for example
  guest access intended → identity pool allows unauthenticated identities with a
  scoped-down guest role).

#### GAMESEC03-BP02 Authenticate requests that are sent to your game backend service — Risk: High
- Verify: backend APIs require a short-lived token: API Gateway authorizers
  (`apigateway:GET` on authorizers; HTTP API JWT authorizers), ALB OIDC auth
  actions, or AppSync auth modes; Cognito user pools issuing JWTs; identity pool
  credentials for anonymous players.
- PASS when: every player-facing API route has an authorizer or IAM/SigV4
  requirement; unauthenticated routes are limited to health checks or deliberate
  public content.

#### GAMESEC03-BP03 Use your game backend service to validate player requests to join a multiplayer game — Risk: Medium
- Verify: game servers validate a player session ID or server-generated ticket from
  the matchmaking service before accepting a connection (GameLift player sessions
  via `gamelift:DescribePlayerSessions`; for custom backends, the join flow in the
  team's description).
- PASS when: join requests are validated server-side against the matchmaker's
  reservation. Clients connecting with only an IP:port they obtained is FAIL.

#### GAMESEC03-BP04 Enforce a strict security policy for player user accounts by requiring a strong password — Risk: High
- Verify: `cognito-idp:DescribeUserPool` → `Policies.PasswordPolicy` (minimum length,
  character classes, `PasswordHistorySize`, temporary password validity).
- PASS when: minimum length ≥ 8 with mixed character requirements and password
  history enabled. Third-party identity only (no passwords stored): N/A.

#### GAMESEC03-BP05 Provide an option for players to set up multi-factor authentication (MFA) on their accounts — Risk: Medium
- Verify: `cognito-idp:GetUserPoolMfaConfig` → `MfaConfiguration` `OPTIONAL` or `ON`,
  with SMS, TOTP or email MFA configured; advanced security / threat protection
  (`DescribeRiskConfiguration`) for new-location or risky sign-ins.
- PASS when: MFA is at least `OPTIONAL` for games with purchases or in-game currency.

### GAMESEC04 Access control (content)

#### GAMESEC04-BP01 Restrict access of downloadable content to authorized clients and users — Risk: High
- Verify: content buckets block public access (`s3:GetBucketPublicAccessBlock`,
  `GetBucketPolicyStatus`); private content served via CloudFront signed URLs/cookies
  (`TrustedKeyGroups` in `cloudfront:GetDistributionConfig`) or S3 presigned URLs.
- PASS when: no content bucket is public and paid or pre-release content requires
  signed access. Companion: `storage-s3-resiliency-expertise`.

#### GAMESEC04-BP02 Limit origin access to authorized content delivery networks (CDNs) — Risk: High
- Verify: CloudFront origin access control (OAC) or legacy OAI on S3 origins; bucket
  policy limited to the distribution; custom-origin header checks for third-party
  CDNs; AWS WAF web ACL associated with the distribution (`WebACLId` in
  `cloudfront:GetDistributionConfig`; for ALB origins `wafv2:GetWebACLForResource`).
- PASS when: S3 origins are reachable only through CloudFront (OAC) and a web ACL is
  associated. Public bucket behind CloudFront is FAIL.

#### GAMESEC04-BP03 Implement geographic restrictions to limit unauthorized access — Risk: High
- Verify: `Restrictions.GeoRestriction` in the distribution config when the title has
  country-by-country release or legal restrictions; WAF geo-match rules.
- PASS when: a restriction requirement exists and is enforced at CloudFront or WAF.
  No requirement: N/A (state it). Do not treat geo blocking as PII protection.

#### GAMESEC04-BP04 Restrict access to content with digital rights management (DRM) solutions — Risk: Medium
- Verify: pre-load or pre-order content is encrypted with keys released at launch
  (DRM/key service integration, KMS-backed key distribution).
- PASS when: pre-release content is encrypted at rest in the CDN path and keys are
  gated by release time. Titles without pre-load: N/A.

### GAMESEC05 Detection (player behavior)

#### GAMESEC05-BP01 Implement a comprehensive data collection strategy to monitor player behavior — Risk: Medium
- Verify: player actions, purchases, social interactions and server-side metrics land
  in a warehouse or data lake (Redshift, S3 + Athena/Glue), with visualization
  (QuickSight/Grafana).
- PASS when: gameplay and transaction events are collected centrally with retention
  and analysis in place.

#### GAMESEC05-BP02 Collect, store, and analyze player usage logs to detect inappropriate behavior — Risk: Medium
- Verify: structured player usage logs (CloudWatch Logs, OpenSearch or a partner
  tool) with detections for cheating, fraud or abuse; ML-assisted review where used.
- PASS when: usage logs are structured and at least one automated detection exists
  (anomaly alarm, rule, or model).

### GAMESEC06 Infrastructure protection

#### GAMESEC06-BP01 Use tools for detecting and responding to threats to your infrastructure — Risk: High
- Verify: GuardDuty enabled (`guardduty:ListDetectors`, `GetDetector`) with findings
  routed to Security Hub; AWS WAF Bot Control on player-facing endpoints
  (`wafv2:GetWebACL` managed rule group `AWSManagedRulesBotControlRuleSet`);
  AWS Shield Advanced for game servers and backends
  (`shield:DescribeSubscription`, `ListProtections`, `ListAttacks`); a penetration
  testing cadence within AWS policy.
- PASS when: GuardDuty is on in every production account and internet-facing game
  endpoints are behind Shield Advanced (or Shield Standard with a documented
  decision) and WAF with bot control.

#### GAMESEC06-BP02 Use artificial intelligence and machine learning tools to automate aspects of your infrastructure protection strategy — Risk: High
- Verify: anomaly detection on business/operational metrics (CloudWatch anomaly
  detection alarms via `cloudwatch:DescribeAnomalyDetectors`; the lens cites Amazon
  Lookout for Metrics) and custom models (SageMaker AI) for cheat, fraud or toxicity
  detection.
- PASS when: logins, transactions or revenue metrics have anomaly-based alarms, or a
  custom detection model is in production.

#### GAMESEC06-BP03 Use insights from system-level logs to continuously improve your infrastructure protection strategy — Risk: Medium
- Verify: S3 server access logs, CloudFront standard/real-time logs and ALB access
  logs enabled (`cloudfront:GetDistributionConfig` → `Logging`,
  `elasticloadbalancing:DescribeLoadBalancerAttributes` → `access_logs.s3.enabled`),
  queryable with Athena; IAM Access Analyzer for S3.
- PASS when: edge and load-balancer access logs are enabled and retained with a
  query path.

### GAMESEC07 Incident response (players)

#### GAMESEC07-BP01 Implement an incident response plan to handle bad actors and abusive behavior — Risk: Medium
- Verify: a tiered policy for suspensions and bans with human review for severe cases.
- PASS when: the policy exists and is enforced through a workflow. Otherwise N/A
  (Interview needed).

#### GAMESEC07-BP02 Ban accounts that are associated with bad actors — Risk: High
- Verify: an automated ban/restriction workflow (Step Functions + Lambda updating the
  player store and revoking tokens; `states:ListStateMachines`,
  `cognito-idp:AdminDisableUser` usage in CloudTrail).
- PASS when: confirmed bad actors can be banned in batch by a repeatable workflow.

### GAMESEC08 Application security

#### GAMESEC08-BP01 Apply security at every stage of the CI/CD pipeline — Risk: Medium
- Verify: least-privilege roles for pipeline stages, CloudTrail auditing of pipeline
  API calls, pre-commit hooks/policy checks.
- PASS when: pipeline roles are scoped per stage and pipeline activity is audited.

### GAMESEC09 Automate security

#### GAMESEC09-BP01 Integrate tooling and automation to reduce the mean time of security reviews — Risk: Medium
- Verify: SAST (the lens cites Amazon CodeGuru), DAST and software composition
  analysis in the pipeline; secure code review practice.
- PASS when: at least SAST and dependency scanning run on every build of the game
  backend.

### GAMESEC10 Threat modeling

#### GAMESEC10-BP01 Determine when and how to complete threat modeling exercises throughout your application development lifecycle — Risk: Medium
- Verify: threat models exist for the game backend, payments/virtual economy and
  player identity, revisited as the game evolves.
- PASS when: a current threat model exists for the money and identity paths.
  Otherwise N/A (Interview needed).

---

## Pillar 3 — Reliability (6 BPs)

Lens design principles: establish the baseline for peak player concurrency and
scalability targets; measure reliability and its impact on player experience. The
lens has no games-specific Foundations BPs (use the base framework).

### GAMEREL01 Workload architecture

#### GAMEREL01-BP01 Distribute game infrastructure across multiple Availability Zones and Regions to improve resiliency — Risk: High
- Verify: ASGs, EKS node groups, ECS services and GameLift fleet locations span ≥ 2
  AZs with roughly even capacity; backends behind multi-AZ load balancers or built on
  Regional managed services (Lambda, API Gateway, DynamoDB, SQS); multi-Region for
  critical services (Aurora Global Database `rds:DescribeGlobalClusters`, DynamoDB
  global tables `dynamodb:DescribeTable` → `Replicas`, GameLift multi-location fleets
  and queues, Route 53 failover/latency records); logical player-facing "game
  Regions" decoupled from physical locations.
- PASS when: no single-AZ production tier and the critical player path (identity,
  matchmaking, session placement, player data) has a multi-Region or documented
  recovery design.

### GAMEREL02 Change management (scaling)

#### GAMEREL02-BP01 Implement a scaling strategy that incorporates the state of active player game sessions — Risk: High
- Verify: scaling that is session-aware: GameLift target-tracking on
  `PercentAvailableGameSessions` with `FullProtection` game session protection
  (`gamelift:DescribeScalingPolicies`, `DescribeFleetAttributes`
  → `NewGameSessionProtectionPolicy`); for EC2/containers, custom CloudWatch metrics
  for sessions/capacity driving a scaler, ASG scale-in protection or lifecycle hooks
  that drain, EKS pod disruption budgets honored; CloudWatch Synthetics covering
  session join.
- PASS when: scale-in cannot terminate a server hosting active players and scale-out
  is driven by player/session metrics, not CPU alone.

#### GAMEREL02-BP02 Support the use of multiple EC2 instance types for your game — Risk: High
- Verify: ASG `MixedInstancesPolicy` with several types/sizes and weights
  (`autoscaling:DescribeAutoScalingGroups`); GameLift fleets across multiple
  locations and, for Spot, FleetIQ game server groups with multiple instance
  definitions (`gamelift:DescribeGameServerGroup`); EKS Karpenter/node groups with
  diversified types; `InsufficientInstanceCapacity` in
  `autoscaling:DescribeScalingActivities` history.
- PASS when: every game-server tier can launch from ≥ 3 instance types (more for
  Spot) and recent scaling activity shows no unresolved capacity errors.

### GAMEREL03 Failure management

#### GAMEREL03-BP01 Monitor game server disruptions, and use the data to improve hosting architecture to achieve reliability goals — Risk: High
- Verify: metrics and alarms for `ServerProcessAbnormalTerminations`,
  `GameSessionInterruptions`, `InstanceInterruptions` (GameLift) or equivalent
  process-crash and Spot-interruption signals on EC2/containers; degraded servers are
  removed or replaced; game state checkpointed to ElastiCache/MemoryDB where session
  recovery is feasible; server disruption logs retained for debugging (remote access
  for GameLift instances, log shipping to CloudWatch Logs).
- PASS when: abnormal terminations and interruptions are alarmed and the trend is
  used to adjust fleet composition (for example moving a game mode off Spot).

#### GAMEREL03-BP02 Implement loose coupling of game features to handle failures with minimal impact to player experience — Risk: High
- Verify: non-critical features (leaderboards, stats, achievements, store catalog)
  are separate services with asynchronous writes (SQS, EventBridge, Kinesis);
  timeouts/retries/backoff configured; feature flags or kill switches so degraded
  features fail soft in the client.
- PASS when: a failure of leaderboards or similar does not block login or
  session join, and the dependency is asynchronous.

#### GAMEREL03-BP03 Monitor infrastructure events over time to measure impact on player behavior — Risk: High
- Verify: alarms on EC2 network allowance metrics (`bw_in_allowance_exceeded`,
  `bw_out_allowance_exceeded`, `pps_allowance_exceeded`,
  `conntrack_allowance_exceeded`, `linklocal_allowance_exceeded` from the ENA
  driver via the CloudWatch agent); CloudWatch Synthetics on login and critical
  paths; GameLift `GameServerInterruptions`/`InstanceInterruptions`; metrics exported
  to S3 for long-term correlation with player metrics (Metric Streams, Athena).
- PASS when: network-limit and interruption metrics are collected and correlated with
  CCU/retention over time.

---

## Pillar 4 — Performance efficiency (24 BPs)

Lens design principles: measure game performance end to end; optimize for metrics
that reflect actual player experience; use technologies that simplify game operations;
design for peak concurrency and scale dynamically.

### GAMEPERF01 Architecture selection

#### GAMEPERF01-BP01 Evaluate game server resource requirements and scalability needs — Risk: High
- Verify: the hosting choice (EC2, containers, GameLift managed, Lambda) is backed by
  measured CPU, memory, network (packets per second) and storage needs per game
  server process; fleet design allows elastic scale (Spot advisor used).
- PASS when: instance family matches the measured profile (for example
  compute-optimized for simulation-heavy servers, network-optimized where PPS is
  the bottleneck) and utilization data exists.

#### GAMEPERF01-BP02 Consider operational overhead for scaling game servers — Risk: High
- Verify: for self-managed EKS/ECS game servers, node termination respects session
  draining (lifecycle hooks or custom controllers, since managed node groups do not
  honor pod disruption budgets on node termination); the team has the skills to
  operate the chosen stack.
- PASS when: termination handling is explicit and tested, or GameLift manages it.

#### GAMEPERF01-BP03 Evaluate integration with other AWS services, development environments, target CPU architectures, and features — Risk: High
- Verify: integration with Secrets Manager/ACM, Route 53 for coordinated traffic
  shifts, Global Accelerator traffic dials; CPU architecture choice (Graviton for
  price-performance vs x86 for specific instruction sets) and OS tuning where used.
- PASS when: traffic shifting is coordinated through Route 53 or Global Accelerator
  and the architecture choice is deliberate and tested.

### GAMEPERF02 Region selection

#### GAMEPERF02-BP01 Select a home Region that is near your players — Risk: High
- Verify: the home Region hosts the player-facing backend near the primary player
  base and supports needed services and failover Regions; Local Zone parent-Region
  implications understood.
- PASS when: home Region choice is explained by player demand signals (pre-orders,
  marketing, interest registrations) and service availability.

#### GAMEPERF02-BP02 Design an approach that supports placing latency-sensitive game infrastructure close to players to improve performance — Risk: High
- Verify: repeatable IaC for adding hosting locations; GameLift multi-location fleets
  (`gamelift:DescribeFleetLocationAttributes`), Local Zones, Outposts, or
  GameLift Anywhere/ECS Anywhere/EKS Anywhere for hybrid; matchmaking-time impact
  of adding/removing locations considered.
- PASS when: a new hosting location can be added from code and current locations
  cover the main player populations.

### GAMEPERF03 Iterative development

#### GAMEPERF03-BP01 Use Amazon GameLift Anywhere and a GameLift testing toolkit — Risk: High
- Verify: an Anywhere fleet (`ComputeType = ANYWHERE`) for local/cloud iteration and
  the GameLift Testing Toolkit for simulated players and FlexMatch validation.
- PASS when: builds are tested on an Anywhere fleet before managed-fleet upload.
  Non-GameLift hosting: N/A.

#### GAMEPERF03-BP02 Test performance and scalability of game servers — Risk: High
- Verify: integration tests against the GameLift server SDK (session start, events),
  scalability tests of queues, latency policies and fleet scaling.
- PASS when: queue and scaling behavior was tested at projected peak.

#### GAMEPERF03-BP03 Optimize resource utilization of GameLift containers — Risk: High
- Verify: container fleets (`gamelift:ListContainerFleets`,
  `DescribeContainerGroupDefinition`) with a primary container (game server +
  GameLift Agent), sidecars for dependencies, CPU/memory limits per container group,
  daemon group for monitoring.
- PASS when: limits are set per container group and utilization is monitored.
  No container fleets: N/A.

### GAMEPERF04 Compute and hardware

#### GAMEPERF04-BP01 Monitor game server processes to detect issues — Risk: High
- Verify: multiple processes per instance with a mix of low- and high-load game
  modes to avoid hot-spotting; per-process resource monitoring and alerts; client
  and server telemetry (ping, jitter, frame drops, API latency) correlated with
  server logs; durable log storage; dashboards (CloudWatch, Managed Grafana).
- PASS when: per-process metrics and alarms exist and one noisy session cannot starve
  others on the same instance.

#### GAMEPERF04-BP02 Performance test your game server with simulated and real gameplay scenarios — Risk: High
- Verify: bot-driven gameplay simulations (for example Distributed Load Testing on
  AWS running client builds), internal playtests, and device testing (AWS Device
  Farm) for mobile/browser titles.
- PASS when: a gameplay-realistic test (not only HTTP load) ran against the current
  server build.

### GAMEPERF05 Compute selection

#### GAMEPERF05-BP01 Benchmark your game performance across multiple compute types — Risk: High
- Verify: benchmarks across compute-optimized `c`, memory-optimized and
  network-optimized `n` families and Intel/AMD/Graviton; no burstable `t` family for
  game servers; enhanced networking (ENA) enabled
  (`ec2:DescribeInstances` → `EnaSupport`, `DescribeInstanceTypes` → network
  performance).
- PASS when: game servers run on non-burstable, ENA-enabled types chosen from a
  benchmark. Any `t`-family game server tier is FAIL.

#### GAMEPERF05-BP02 Move non-latency-sensitive compute tasks to asynchronous workflows — Risk: High
- Verify: leaderboard updates, stats, rewards and similar run through queues
  (`sqs:ListQueues`, `GetQueueAttributes`), EventBridge or Step Functions; clients
  fetch results asynchronously.
- PASS when: end-of-match and progression writes are queued, not synchronous on the
  gameplay path.

### GAMEPERF06 Data management

#### GAMEPERF06-BP01 Centralize log collection and storage — Risk: High
- Verify: game server and GameLift instance logs in CloudWatch Logs
  (`logs:DescribeLogGroups`), agent batch size and buffer tuned to limit server impact.
- PASS when: all game-server tiers ship logs to a central store.

#### GAMEPERF06-BP02 Categorize and store game data based on access patterns — Risk: High
- Verify: player profiles/progression in DynamoDB; game saves in S3 (Transfer
  Acceleration or CloudFront for upload/download); persistent world state in
  DynamoDB, ElastiCache or MemoryDB; analytics via Kinesis Data Streams or MSK with
  Managed Service for Apache Flink.
- PASS when: each data class sits on a store that fits its access pattern (no
  player-profile table on a relational single writer sized for peak, no saves in a
  database blob column).

#### GAMEPERF06-BP03 Enable efficient log formatting and batching — Risk: High
- Verify: structured (JSON) logs, batched shipping, debug/verbose logging off by
  default in production.
- PASS when: logs are structured and batched; debug level is not the production
  default.

#### GAMEPERF06-BP04 Implement log rotation and retention policies — Risk: Low
- Verify: log rotation on servers; CloudWatch Logs retention set
  (`retentionInDays` not null in `logs:DescribeLogGroups`); archival to S3 where
  required.
- PASS when: no production log group has infinite retention without a reason.

#### GAMEPERF06-BP05 Use monitoring and visualization tools — Risk: High
- Verify: CloudWatch alarms and dashboards; Amazon Managed Service for Prometheus and
  Managed Grafana where used (`aps:ListWorkspaces`, `grafana:ListWorkspaces`).
- PASS when: a dashboard covers fleet capacity, session metrics and player-facing
  latency with alarms on breaches.

### GAMEPERF07 Networking and content delivery

#### GAMEPERF07-BP01 Define network latency thresholds for your game — Risk: High
- Verify: clients ping hosting locations and report latency, jitter and packet loss;
  matchmaking uses latency as an input (FlexMatch rule set `latency` rules, GameLift
  queue `PlayerLatencyPolicies` in `gamelift:DescribeGameSessionQueues`).
- PASS when: a latency threshold is defined and enforced in matchmaking/placement.

#### GAMEPERF07-BP02 Run a separate matchmaking service for each gameplay mode and game hosting Region — Risk: High
- Verify: one matchmaking configuration per game mode
  (`gamelift:DescribeMatchmakingConfigurations`) or separate deployments per mode in
  a custom matchmaker; matchmaking deployed near hosting Regions.
- PASS when: game modes do not share a single matchmaking configuration/deployment.

#### GAMEPERF07-BP03 Regularly monitor matchmaking performance — Risk: High
- Verify: alarms and dashboards on FlexMatch `TimeToMatch`, `CurrentTickets`,
  `TicketsTimedOut`, `TicketsFailed`, `MatchAcceptancesTimedOut`,
  `RuleEvaluationsFailed`; rule changes tested or rolled out gradually.
- PASS when: wait-time and ticket-failure metrics are alarmed and reviewed before
  rule changes ship.

#### GAMEPERF07-BP04 Regularly monitor networking performance — Risk: High
- Verify: CloudWatch Network Monitor / Internet Monitor
  (`networkmonitor:ListMonitors`, `internetmonitor:ListMonitors`) to separate ISP
  issues from game issues; VPC Flow Logs enabled (`ec2:DescribeFlowLogs`) to spot
  drops and abnormal patterns.
- PASS when: network path monitoring exists for player-facing endpoints and flow
  logs are enabled on game VPCs.

#### GAMEPERF07-BP05 Use network acceleration technology to improve performance across the internet — Risk: High
- Verify: AWS Global Accelerator standard accelerators for backends and custom
  routing accelerators for deterministic routing to game sessions
  (`globalaccelerator:ListAccelerators`, `ListCustomRoutingAccelerators`,
  `ListEndpointGroups` with traffic dials); S3 Multi-Region Access Points or
  Cross-Region Replication for globally shared content.
- PASS when: gameplay, voice and real-time messaging traffic enters through Global
  Accelerator (or a documented alternative with measured results).

### GAMEPERF08 Process and culture

#### GAMEPERF08-BP01 Inform and include the player in your process — Risk: High
- Verify: in-game latency/FPS/packet-loss indicators, a public status page,
  diagnostic dump submission from the client, a support forum; Live Ops workflows
  account for idle and active client behavior.
- PASS when: players can see network quality in-game and a status page is maintained.

#### GAMEPERF08-BP02 Align solution selection with engineering team skills and expertise — Risk: Not stated (treat as Medium)
- Verify: the hosting option matches team capability (managed GameLift when
  infrastructure skills are thin; EC2/containers when the team can tune and scale).
- PASS when: operational incidents do not trace back to missing platform expertise.
  Otherwise N/A (Interview needed).

---

## Pillar 5 — Cost optimization (7 BPs)

Lens design principles: measure infrastructure cost per player, system and feature;
assess the trade-off of cost optimization versus player experience. The lens has no
games-specific BPs for cloud financial management, managing demand/supply, or
optimizing over time (use the base framework).

### GAMECOST01 Expenditure and usage awareness

#### GAMECOST01-BP01 Implement attribution of cost per player, game feature, and environment — Risk: High
- Verify: cost allocation tags activated (`ce:ListCostAllocationTags`), features
  decoupled into separately tagged resources (Lambda functions, DynamoDB tables,
  Fargate services), environments in separate accounts; `ce:GetCostAndUsage`
  grouped by tag or account returns per-feature and per-environment spend.
- PASS when: cost per environment and per feature can be reported, and cost per
  player (spend ÷ CCU or DAU) is tracked.

#### GAMECOST01-BP02 Discover opportunities for optimization — Risk: Low
- Verify: Cost Optimization Hub, Cost Anomaly Detection
  (`ce:GetAnomalyMonitors`), budgets (`budgets:DescribeBudgets`), Data Exports.
- PASS when: anomaly detection and budgets exist and optimization recommendations
  are reviewed on a cadence.

### GAMECOST02 Cost-effective resources

#### GAMECOST02-BP01 Optimize the cost of data transfer across the internet — Risk: High
- Verify: content and patches delivered through CloudFront in front of S3/EC2
  origins (Origin Shield when multiple CDNs pull); VPC Flow Logs and Internet
  Monitor used to find costly paths; `ce:GetCostAndUsage` filtered to data transfer
  usage types.
- PASS when: game content egress goes through CloudFront and data transfer cost is
  measured.

#### GAMECOST02-BP02 Optimize the number of game sessions hosted on each game server instance to optimize costs — Risk: Medium
- Verify: packing density: multiple server processes per instance (GameLift runtime
  configuration `ConcurrentExecutions` via `gamelift:DescribeRuntimeConfiguration`;
  container task density; EC2 process manager), utilization monitored to refine it.
- PASS when: more than one game session runs per instance and utilization data
  supports the chosen density.

#### GAMECOST02-BP03 Select the appropriate compute pricing option to reduce costs — Risk: Medium
- Verify: Savings Plans cover predictable baseline (`ce:GetSavingsPlansUtilization`,
  `GetSavingsPlansCoverage`); Spot for short-session or interruption-tolerant game
  servers diversified across types and AZs (GameLift Spot fleets / FleetIQ, ASG
  capacity rebalancing); On-Demand for the remainder.
- PASS when: baseline capacity is covered by a commitment and Spot is used only
  where sessions tolerate interruption.

### GAMECOST03 Data transfer costs (storage and database)

#### GAMECOST03-BP01 Choose the appropriate type of storage for user generated content to reduce costs — Risk: Low
- Verify: S3 lifecycle rules or Intelligent-Tiering
  (`s3:GetBucketLifecycleConfiguration`, `GetBucketIntelligentTieringConfiguration`);
  One Zone-IA for transient telemetry/matchmaking records; EFS for shared dev
  storage.
- PASS when: UGC and save buckets have lifecycle or Intelligent-Tiering configured.

#### GAMECOST03-BP02 Optimize databases for game backends — Risk: Medium
- Verify: Aurora read-replica auto scaling (`application-autoscaling:DescribeScalableTargets`
  for `rds` namespace), snapshot exports to S3 for analytics instead of extra
  replicas; DynamoDB on-demand for new workloads and provisioned with auto scaling
  for predictable traffic, unused GSIs/LSIs removed, Scan-heavy access patterns
  avoided, reserved capacity for steady state, Streams + Lambda for event
  processing. Companion: `rds-operation-review`.
- PASS when: capacity mode matches traffic shape and no idle replicas or unused
  indexes are billed.

---

## Pillar 6 — Sustainability (4 BPs)

Lens design principles: select appropriate storage for user data; apply lifecycle
policies that de-duplicate and purge; right-size compute selectively; use serverless
for brief, transactional processes. No games-specific BPs for Region selection,
alignment to demand, or software and architecture (use the base framework).

### GAMESUS01 Data management

#### GAMESUS01-BP01 Use storage technologies that fit the patterns adapted to user content, subscriber information, and in-game purchases — Risk: High
- Verify: fast-changing data in DynamoDB or in-memory stores, transactional
  purchases/subscriptions in Aurora, semi-structured in DocumentDB where used, large
  assets/UGC in S3 with the right storage class; data tagged by retention need.
- PASS when: each data type is on a fitting store and classified for retention.

#### GAMESUS01-BP02 Use lifecycle policies or TTL expiration to delete unnecessary games user data, log files, or deprecated assets — Risk: High
- Verify: S3 lifecycle expiration on logs and deprecated assets; DynamoDB TTL
  enabled (`dynamodb:DescribeTimeToLive`) on session/ephemeral tables; ElastiCache
  key TTLs; CloudWatch Logs retention.
- PASS when: ephemeral tables have TTL, log groups have retention, and S3 lifecycle
  expires stale objects.

### GAMESUS02 Hardware and services

#### GAMESUS02-BP01 Select managed services for appropriate compute workloads — Risk: High
- Verify: Lambda for event-driven work (purchases, auth hooks, matchmaking
  requests), Fargate for backend services, GameLift for dedicated game servers,
  instead of self-managed instances for variable load.
- PASS when: variable or event-driven components run on managed/serverless compute.

#### GAMESUS02-BP02 Right-size your compute and deploy GPU performance only where needed — Risk: High
- Verify: instance families match workloads (compute-optimized servers,
  memory-optimized data tiers), Graviton adoption where supported, GPU instances
  only for GPU-dependent servers or build tasks (for example HLOD rebuilds), AWS
  Compute Optimizer recommendations (`compute-optimizer:Get*`; may be denied → N/A).
- PASS when: no GPU instances serve non-GPU workloads and right-sizing findings are
  reviewed.
