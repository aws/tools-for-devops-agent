# Player-impacting symptoms → likely causes → evidence

Use this file during incident triage and RCA for a games workload. Start from the
symptom the players or the alarm describe, work the candidate causes in the order
listed (most common first), and collect the named evidence before naming a root
cause. Every call is read-only. The last column ties the finding back to the Games
Industry Lens best practice whose absence usually explains it, so the RCA's
prevention section can cite it.

General rules for games incidents:

- **Frame impact in player terms first**: how many players could not log in, match,
  connect or stay connected, for how long, in which game Regions. CCU drop,
  matchmaking wait time and session-interruption counts are the primary impact
  metrics; CPU and 5xx counts are supporting evidence.
- **Check for a planned demand event before anything else**: a launch, season start,
  content drop, promotion, streamer event or regional release explains most capacity
  symptoms. Correlate the incident start with deployment and marketing timelines.
- **Separate the three failure domains**: (1) AWS service impairment — check AWS
  Health first (companion skill `aws-health-events`); (2) the studio's own change —
  deployments, config, rule-set or fleet changes in CloudTrail; (3) demand or
  external — player surge, ISP routing, DDoS.
- **Spot is a usual suspect** for game-server interruptions; so are hard EC2 network
  allowances (PPS, bandwidth, connection tracking) that do not show up as CPU.

## 1. Players cannot log in / login storm

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Cognito user pool request-rate quota exceeded during a surge | `cloudwatch` metrics `AWS/Cognito` `SignInThrottles`, `TokenRefreshThrottles`, `FederationThrottles`; `servicequotas:GetServiceQuota` for Cognito category rates; CloudTrail `TooManyRequestsException` | GAMEOPS03-BP05, GAMESEC03-BP02 |
| Lambda concurrency limit on the auth/login function | `AWS/Lambda` `Throttles`, `ConcurrentExecutions` vs account quota; `lambda:GetFunctionConcurrency`, provisioned concurrency config | GAMEOPS03-BP05 |
| API Gateway throttling | `AWS/ApiGateway` `4XXError` with 429s, `Count` vs stage throttle settings (`apigateway:GET` stage) | GAMEOPS03-BP05 |
| DynamoDB throttling on player/profile table (hot partition on a popular key, or capacity below surge) | `AWS/DynamoDB` `ThrottledRequests`, `ReadThrottleEvents`, `WriteThrottleEvents`; `dynamodb:DescribeTable` capacity mode, warm throughput; Contributor Insights for hot keys | GAMEOPS03-BP05, GAMEPERF06-BP02 |
| Third-party identity provider (platform/social login) degraded | Elevated `FederationThrottles`/errors scoped to one provider; provider status; `cognito-idp:DescribeIdentityProvider` | GAMESEC03-BP01 |
| Credential-stuffing or bot login attack | `AWS/WAFV2` `BlockedRequests` with Bot Control / ATP labels, `wafv2:GetSampledRequests`; Cognito threat protection risk events; GuardDuty findings | GAMESEC06-BP01, GAMESEC03-BP04 |
| NAT gateway port exhaustion for backend egress to an external IdP or payment provider | `AWS/NATGateway` `ErrorPortAllocation`, `PacketsDropCount`, `ConnectionAttemptCount` | GAMEREL03-BP03 |

## 2. Matchmaking is slow, times out or fails

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Not enough players in a mode/Region for the rule set (overly strict skill or latency rules, new mode launch) | FlexMatch `TimeToMatch`, `CurrentTickets`, `TicketsTimedOut`, `RuleEvaluationsFailed`, `MatchAcceptancesTimedOut`; `gamelift:DescribeMatchmakingConfigurations`, `DescribeMatchmakingRuleSets`; recent rule-set changes in CloudTrail | GAMEPERF07-BP03, GAMEPERF07-BP02 |
| Placement failing for lack of game-server capacity (queue has no fleet with free sessions in the latency-eligible locations) | Queue metrics `PlacementsFailed`, `PlacementsTimedOut`, `FirstChoiceOutOfCapacity`, `QueueDepth`, `AverageWaitTime`; fleet `AvailableGameSessions`, `PercentAvailableGameSessions`, `IdleInstances` per location; `gamelift:DescribeFleetLocationCapacity` | GAMEOPS03-BP05, GAMEREL02-BP01 |
| Fleet cannot scale out: EC2 `InsufficientInstanceCapacity`, Spot pool exhausted, or vCPU/fleet quota hit | `gamelift:DescribeFleetEvents` (`FLEET_SCALING_EVENT`, capacity errors), `autoscaling:DescribeScalingActivities` failures, EC2 vCPU quota via `service-quota-check`; fleet `MaxSize` reached; `InstanceInterruptions` | GAMEREL02-BP02, GAMEOPS03-BP05 |
| Latency policies exclude the only Regions with capacity | Queue `PlayerLatencyPolicies` in `DescribeGameSessionQueues`; `LowestLatencyPlacement` vs placed location | GAMEPERF07-BP01 |
| Matchmaking backend (custom) under-provisioned or single mode deployment contended | Backend service latency/5xx, queue depth of the matchmaking service, Lambda throttles | GAMEPERF07-BP02 |
| Game server build failing to activate (new build rollout) | `ActivatingGameSessions` high with low `ActiveGameSessions`; `ServerProcessAbnormalTerminations`; fleet events `SERVER_PROCESS_*`; recent `CreateFleet`/`UpdateRuntimeConfiguration`/deployment in CloudTrail | GAMEOPS03-BP04 |

## 3. Players disconnected mid-match / sessions interrupted

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Spot interruption of game-server instances | GameLift `InstanceInterruptions`, `GameSessionInterruptions`; FleetIQ `GameServerInterruptions`; EC2 Spot interruption notices in CloudTrail/EventBridge; which game modes run on Spot | GAMEREL03-BP01, GAMECOST02-BP03 |
| Scale-in or deployment terminated instances with active sessions (no session protection, no drain) | `DescribeFleetAttributes` → `NewGameSessionProtectionPolicy`; ASG scale-in activities and lifecycle hooks; EKS node terminations vs pod disruption budgets; CodeDeploy/ECS deployment timeline | GAMEREL02-BP01, GAMEOPS03-BP04 |
| Game server process crash | `ServerProcessAbnormalTerminations`; server logs (CloudWatch Logs / GameLift log paths); correlation with a build version | GAMEPERF04-BP01 |
| EC2 network allowance exceeded on game-server instances (packets per second, bandwidth, connection tracking) — symptoms are packet loss and lag spikes, not CPU | CloudWatch agent ethtool metrics `pps_allowance_exceeded`, `bw_in/out_allowance_exceeded`, `conntrack_allowance_exceeded`, `linklocal_allowance_exceeded`; instance type network baseline from `ec2:DescribeInstanceTypes`; whether a burstable `t` family is in use | GAMEREL03-BP03, GAMEPERF05-BP01 |
| Noisy neighbor process on a shared instance (one session starving others) | Per-process CPU/memory metrics; runtime configuration density; game-mode mix per instance | GAMEPERF04-BP01 |
| DDoS against game-server IPs or the accelerator | `shield:ListAttacks`, `DescribeAttack`; `AWS/DDoSProtection` `DDoSDetected`; Global Accelerator `ProcessedBytesIn` surges; whether Shield Advanced covers the endpoints | GAMESEC06-BP01 |
| ISP or internet routing change affecting one geography | CloudWatch Internet Monitor health events, Network Monitor probes; client latency telemetry by ISP/ASN; Global Accelerator per-endpoint-group metrics | GAMEPERF07-BP04, GAMEPERF07-BP05 |

## 4. High latency, rubber-banding, "lag" reports from one region

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Players placed far from home because nearby locations were full | Queue `LowestLatencyPlacement` vs actual placed location; `FirstChoiceOutOfCapacity`; per-location capacity | GAMEOPS03-BP05, GAMEPERF02-BP02 |
| No hosting location near the affected player population | Fleet locations vs client latency telemetry by geography; Local Zone options | GAMEPERF02-BP02 |
| Server tick starved: CPU steal, wrong instance family, GPU/compute mismatch | Instance `CPUUtilization`, per-process metrics, instance family (`t` burst credits `CPUCreditBalance`) | GAMEPERF05-BP01, GAMEPERF01-BP01 |
| Traffic not using Global Accelerator (client connecting to public IP directly) | Accelerator listener/endpoint config, client connection target in telemetry | GAMEPERF07-BP05 |
| Synchronous backend calls on the gameplay path (leaderboard or stats write blocking match end) | Backend latency correlated with match-end spikes; absence of SQS/async pattern | GAMEPERF05-BP02, GAMEREL03-BP02 |

## 5. Launch or in-game event meltdown (everything slow at once)

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Demand above forecast with reactive autoscaling only; minimums never raised | ASG/fleet `MinSize` history (CloudTrail `UpdateAutoScalingGroup`, `UpdateFleetCapacity`), scaling activity timestamps vs CCU curve; DynamoDB warm throughput vs peak; ElastiCache CPU/evictions | GAMEOPS03-BP05, GAMEREL02-BP01 |
| Service quotas hit (EC2 vCPUs, Lambda concurrency, API Gateway, Cognito, GameLift fleets/instances per location) | companion `service-quota-check`; `servicequotas:GetServiceQuota` + usage metrics | GAMEOPS03-BP05 |
| Database writes from end-of-match surges | Aurora `DatabaseConnections`, `CommitLatency`, writer CPU; DynamoDB throttles | GAMECOST03-BP02, GAMEPERF06-BP02 |
| Content/patch download saturating origin instead of CDN | S3 `5xxErrors`/`SlowDown`, CloudFront cache-hit ratio and origin latency, whether clients hit S3 directly | GAMECOST02-BP01, GAMESEC04-BP02 |
| Telemetry pipeline backpressure (Kinesis `WriteProvisionedThroughputExceeded`) feeding back into clients | `AWS/Kinesis` `WriteProvisionedThroughputExceeded`, `IteratorAgeMilliseconds`; Firehose `DeliveryToS3.Success` | GAMEOPS06-BP01 |

## 6. Suspected cheating, fraud or abuse wave

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Unauthenticated or replayed backend requests | API Gateway authorizer config and 401/403 rates; routes without authorizers | GAMESEC03-BP02 |
| Clients joining sessions without a matchmaker reservation | Server-side validation of player session IDs (`gamelift:DescribePlayerSessions` status), join-attempt logs | GAMESEC03-BP03 |
| Account takeover (weak passwords, no MFA) | Cognito risk events, password policy, MFA configuration | GAMESEC03-BP04, GAMESEC03-BP05 |
| Bot traffic on store/economy APIs | WAF Bot Control labels and sampled requests; GuardDuty findings | GAMESEC06-BP01 |
| No automated ban path, response is manual | Presence of a ban workflow (Step Functions/Lambda), token revocation evidence | GAMESEC07-BP02 |

## 7. Cost spike after a launch or event

| Likely cause | Evidence to collect | Lens BP |
|---|---|---|
| Pre-scaled minimums never lowered after the event | Current `MinSize` vs utilization; `ce:GetCostAndUsage` by tag/account | GAMEOPS03-BP05, GAMECOST01-BP01 |
| Data transfer out from origins instead of CloudFront | Data-transfer usage types in Cost Explorer; CloudFront vs S3/EC2 egress | GAMECOST02-BP01 |
| Low packing density (one session per instance) | Runtime configuration `ConcurrentExecutions`; instance utilization | GAMECOST02-BP02 |
| Idle Aurora replicas or unused DynamoDB indexes | Replica utilization; GSI consumed capacity | GAMECOST03-BP02 |
| Logs/telemetry retained forever | CloudWatch Logs retention, S3 lifecycle on telemetry buckets | GAMEPERF06-BP04, GAMESUS01-BP02 |

## Evidence collection order for a games incident (RCA)

1. Scope the impact in player terms: CCU, logins/min, matchmaking wait, session
   interruptions, by game Region, from the start of the anomaly.
2. AWS Health events for the Regions and services involved (companion skill).
3. Change timeline: deployments, fleet/queue/rule-set updates, config changes,
   scaling-policy edits, in the hour before impact (CloudTrail).
4. Demand timeline: planned events, marketing, streamer traffic, regional release.
5. Capacity signals: fleet/ASG capacity vs max, scaling failures, quota utilization,
   Spot interruptions.
6. Network signals: ENA allowance metrics, NAT gateway errors, Shield attacks,
   Internet Monitor health events, Global Accelerator metrics.
7. Dependency signals: Cognito, DynamoDB, Aurora, ElastiCache, external IdP/payment
   providers.
8. Only then name the root cause, list contributing factors, and attach the lens BP
   whose implementation would have prevented or shortened the incident.
