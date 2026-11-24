# Read-only discovery for a games workload

Run discovery in this order. Stop early when the user scoped the review to one pillar
or scenario; collect only what that scope needs. Every call is a read (`Describe*`,
`List*`, `Get*`). Record for each area: found / not found / access denied. "Access
denied" and "not found" are different outcomes: denied becomes N/A with the reason;
not found is evidence.

Keep the inventory as a short in-conversation ledger (resource type, count, names or
ARNs truncated, Region). Do not write files.

## D0 — Scope and demand context (ask or infer)

- Game title(s), platforms, genre and interaction mode (real-time synchronous,
  turn-based/asynchronous), monetization (purchases, subscriptions).
- Current and target CCU / DAU, the next launch or in-game event and its date.
- Which accounts and Regions are in scope; which third-party tools cover
  observability or security (Datadog, Grafana, Splunk, New Relic, Honeycomb and
  similar), because those are not machine-verifiable from AWS reads.

## D1 — Game server hosting (Scenario A)

| Read | Purpose |
|---|---|
| `gamelift:ListFleets`, `DescribeFleetAttributes`, `DescribeFleetCapacity`, `DescribeFleetLocationAttributes`, `DescribeFleetLocationCapacity`, `DescribeRuntimeConfiguration`, `DescribeScalingPolicies`, `DescribeFleetEvents` (last 24–72 h) | Fleet type (On-Demand/Spot, EC2/container/Anywhere), locations, protection policy, density, scaling, recent capacity or process errors |
| `gamelift:DescribeGameSessionQueues`, `DescribeMatchmakingConfigurations`, `DescribeMatchmakingRuleSets`, `ListGameServerGroups`, `DescribeGameServerGroup`, `ListContainerFleets`, `ListContainerGroupDefinitions` | Placement and matchmaking design, FleetIQ Spot diversification, container fleets |
| `autoscaling:DescribeAutoScalingGroups`, `DescribeScalingActivities`, `DescribeLifecycleHooks`, `DescribePolicies` | Self-managed EC2 game servers: mixed instances, protection, drain hooks, capacity errors |
| `eks:ListClusters`, `DescribeCluster`, `ListNodegroups`, `DescribeNodegroup`; `ecs:ListClusters`, `DescribeServices` | Container-hosted game servers and backends |
| `ec2:DescribeInstances` (tags, `InstanceType`, `EnaSupport`), `DescribeInstanceTypes`, `DescribeCapacityReservations`, `DescribeSecurityGroups` (UDP ingress) | Instance families (flag `t*`), ENA, reservations, game-server ports |
| CloudWatch metrics `AWS/GameLift` (fleet, queue, FlexMatch), CloudWatch agent ethtool allowance metrics, `AWS/EC2`, `AWS/AutoScaling` | Capacity headroom, interruptions, abnormal terminations, network allowances |

## D2 — Game backend (Scenario B)

| Read | Purpose |
|---|---|
| `apigateway:GET` (REST APIs, HTTP APIs, authorizers, stages), `appsync:ListGraphqlApis`, `elasticloadbalancing:DescribeLoadBalancers`/`DescribeListeners`/`DescribeLoadBalancerAttributes` | Entry points, authorizers, ALB auth actions, access logs |
| `lambda:ListFunctions`, `GetFunctionConcurrency`, `GetProvisionedConcurrencyConfig`; `ecs:DescribeServices`; `eks` workloads via `eks:AccessKubernetesApi` when granted | Backend compute, provisioned concurrency on login/matchmaking paths |
| `dynamodb:ListTables`, `DescribeTable` (capacity mode, warm throughput, GSIs, replicas), `DescribeTimeToLive`, `DescribeContributorInsights` | Player data stores |
| `rds:DescribeDBClusters`, `DescribeDBInstances`, `DescribeGlobalClusters`; `application-autoscaling:DescribeScalableTargets` (rds) | Relational stores, read-replica scaling, global databases |
| `elasticache:DescribeReplicationGroups`, `DescribeServerlessCaches`; `memorydb:DescribeClusters` | Leaderboards, pub/sub, session state |
| `sqs:ListQueues`/`GetQueueAttributes`, `sns:ListTopics`, `events:ListRules`, `states:ListStateMachines` | Asynchronous and decoupled paths, ban workflows |
| `cognito-idp:ListUserPools`, `DescribeUserPool`, `GetUserPoolMfaConfig`, `DescribeRiskConfiguration`, `ListIdentityProviders`; `cognito-identity:ListIdentityPools`, `DescribeIdentityPool` | Player identity model, password policy, MFA, guest access |

## D3 — Edge, network and protection

| Read | Purpose |
|---|---|
| `cloudfront:ListDistributions`, `GetDistributionConfig` (origins with OAC/OAI, `WebACLId`, `TrustedKeyGroups`, `Restrictions`, `Logging`, Origin Shield) | Content delivery and content access control |
| `s3:GetBucketPublicAccessBlock`, `GetBucketPolicyStatus`, `GetBucketLifecycleConfiguration`, `GetBucketIntelligentTieringConfiguration`, `GetBucketLogging` on content/UGC/telemetry buckets | Public exposure, lifecycle, access logs |
| `globalaccelerator:ListAccelerators`, `ListCustomRoutingAccelerators`, `ListListeners`, `ListEndpointGroups` | Network acceleration and traffic dials |
| `route53:ListHostedZones`, `ListResourceRecordSets`, `ListHealthChecks` | Latency/failover routing and health checks |
| `shield:DescribeSubscription`, `ListProtections`, `ListAttacks` (last 30 days); `wafv2:ListWebACLs`, `GetWebACL`, `GetWebACLForResource`, `GetLoggingConfiguration` | DDoS and layer-7 protection, bot control |
| `ec2:DescribeFlowLogs`, `DescribeNatGateways`; `networkmonitor:ListMonitors`, `internetmonitor:ListMonitors` | Flow logs, NAT, network path monitoring |

## D4 — Observability and operations

| Read | Purpose |
|---|---|
| `cloudwatch:DescribeAlarms`, `ListDashboards`, `DescribeAnomalyDetectors`; `synthetics:DescribeCanaries`; `logs:DescribeLogGroups` (retention) | Alarm coverage, player-journey canaries, dashboards, log retention |
| `xray:GetSamplingRules`, `GetServiceGraph`; `application-signals:ListServices`; `aps:ListWorkspaces`; `grafana:ListWorkspaces` | Tracing and visualization stack |
| `kinesis:ListStreams`, `DescribeStreamSummary`; `firehose:ListDeliveryStreams`; `kafka:ListClustersV2`; `glue:GetDatabases`; `athena:ListWorkGroups` | Telemetry and analytics pipeline (Scenario D) |
| `cloudformation:ListStacks`, `DescribeStacks`, `DescribeStackResourceDrifts`; `codedeploy:ListApplications`, `ListDeploymentConfigs` | IaC and deployment strategy evidence |
| `fis:ListExperimentTemplates`, `ListExperiments` | Fault injection practice |
| `health:DescribeEvents` (companion `aws-health-events`) | Current/recent AWS events affecting the Regions in use |

## D5 — Accounts, identity and governance

| Read | Purpose |
|---|---|
| `organizations:DescribeOrganization`, `ListRoots`, `ListOrganizationalUnitsForParent`, `ListAccounts`, `ListPolicies`, `ListPoliciesForTarget`; `controltower:ListLandingZones`, `ListEnabledControls` | Multi-account structure, SCPs, tag policies |
| `iam:GetAccountSummary`, `ListUsers`, `ListSAMLProviders`, `ListOpenIDConnectProviders`; `sso-admin:ListInstances`; `access-analyzer:ListAnalyzers`, `ListFindingsV2` | Root hygiene, federation, least privilege |
| `guardduty:ListDetectors`, `GetDetector`; `securityhub:GetEnabledStandards`, `DescribeStandardsControls`; `config:DescribeConfigRules`, `DescribeConformancePacks` | Threat detection and standards |
| `tag:GetResources` (by game/environment tags); `ce:ListCostAllocationTags`, `GetCostAndUsage`, `GetAnomalyMonitors`, `GetSavingsPlansCoverage`; `budgets:DescribeBudgets` | Tag coverage, cost attribution, commitments |
| `servicequotas:ListServiceQuotas` for `ec2`, `gamelift`, `lambda`, `cognito-idp`, `apigateway`, `dynamodb` (companion `service-quota-check`) | Quota headroom for the next event |

## Applicability gates

- **No GameLift resources and no UDP game-server tiers** → the title is backend-only
  or turn-based: grade GAMEPERF03 (iterative development on GameLift) and the
  game-server-specific checks (GAMEREL02-BP01 session-aware scaling,
  GAMECOST02-BP02 packing density, GAMEPERF04) as N/A with "no dedicated game
  servers found", and say so in the coverage note.
- **Access denied on Organizations / Control Tower / Compute Optimizer / Cost
  Explorer** → N/A with the reason for GAMEOPS02-BP01, GAMESEC01-BP02/BP04,
  GAMESUS02-BP02, GAMECOST01; do not fail the customer for permissions the agent
  lacks.
- **Third-party observability or security tooling declared** → empty CloudWatch alarm
  or GuardDuty results are not an automatic FAIL; grade N/A pending manual
  confirmation and name the tool.
- **Cloud game development only (build farm, workstations, no live title)** → grade
  Scenario C checks (GAMESEC08, GAMESEC09, GAMESUS02-BP02, cost of idle workstations)
  and mark player-facing pillars N/A.
