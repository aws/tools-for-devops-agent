# Games workload scenarios — what to recognize and what to check

The Games Industry Lens describes five scenario families. Use this file in step S1 of
the review to classify the workload from observed resources, and in incident work to
know which components sit on the player's critical path.

Source: [Scenarios](https://docs.aws.amazon.com/wellarchitected/latest/games-industry-lens/scenarios.html)
and [Definitions](https://docs.aws.amazon.com/wellarchitected/latest/games-industry-lens/definitions.html)
in the lens.

## Vocabulary the lens uses

| Term | Meaning |
|---|---|
| Game server instance | The compute (EC2 instance, container host) that runs one or more game server processes. |
| Game server process | One running copy of the game server build hosting one game session. Process and session are used interchangeably. |
| Game session | An instance of the running game that players connect to through player sessions. |
| Player session | One player's connection to a game session; the matchmaker reserves it before the client connects. |
| Game backend | REST (HTTPS) or WebSocket services for identity, profiles, inventory, stats, leaderboards, matchmaking, presence and chat. |
| Live Ops | Running the game as a live service: events, promotions, content drops, and the team that watches game health. |
| Matchmaking | Finds a game session for a player, using skill, mode, party and measured client latency per hosting Region. |
| Logical game Region | A player-facing grouping (for example "North America") of several physical hosting locations. |
| CCU / DAU / MAU | Concurrent, daily and monthly active users — the demand metrics scaling plans are built on. |

## Scenario A — Game hosting for real-time synchronous gameplay

Shooters, MMOs, sports and action titles where connected players share state in near
real time.

Recognize it by: GameLift fleets, queues and matchmaking configurations
(`gamelift:ListFleets`, `DescribeGameSessionQueues`, `DescribeMatchmakingConfigurations`);
or EC2 Auto Scaling groups / EKS / ECS running long-lived processes that expose UDP
ports (security groups with UDP ingress ranges, `ec2:DescribeSecurityGroups`); Global
Accelerator custom routing accelerators; Shield Advanced protections on game-server
endpoints; client latency metrics flowing to CloudWatch.

Critical player path: identity → matchmaking → session placement → connect to
IP:port → gameplay (UDP) → end-of-match writes (asynchronous).

Characteristics to check against the lens:

- Dedicated servers (or STUN/TURN relays for peer-to-peer-like designs) are hosted in
  several Regions and locations; a "game Region" is logical and decoupled from the
  physical location (GAMEREL01-BP01, GAMEPERF02-BP02).
- Clients ping every hosting location and submit latency with the match request;
  matchmaking enforces latency thresholds (GAMEPERF07-BP01) and runs per game mode
  and Region (GAMEPERF07-BP02).
- Gameplay uses UDP; matchmaking, auth and other client-server traffic use HTTPS.
- Game servers are frequent DDoS targets: Shield Advanced on the accelerator and
  backends (GAMESEC06-BP01).
- Scaling must not interrupt active sessions (GAMEREL02-BP01) and must survive one
  instance type being unavailable (GAMEREL02-BP02).
- Packing density: several processes per instance, mixed game modes per instance
  (GAMECOST02-BP02, GAMEPERF04-BP01).

### Reference: session-based hosting with a serverless backend (GameLift managed)

Flow in the lens: client gets a Cognito identity (identity pool, optionally federated)
→ signs a request to API Gateway → Lambda reads player data from DynamoDB (identity
from the request context) → Lambda starts FlexMatch matchmaking with player skill and
client latency → FlexMatch places the session through a GameLift queue over fleets
with one or more locations → placement events go to SNS → Lambda writes the
connection info back; the client polls or is notified and connects to the game
server. The game server process is started by the GameLift agent, validates the
player session, and reports session state back.

What to check: queue has multiple fleet/location destinations with latency policies;
FlexMatch configuration per mode; `FullProtection` for active sessions; SNS/Lambda
notification path has a DLQ; DynamoDB player table capacity mode and warm throughput;
API Gateway authorizer on every route (GAMESEC03-BP02).

### Reference: multi-Region and hybrid architecture for low-latency games

Flow in the lens: Route 53 latency-based routing sends the client to the nearest
Regional backend; each backend has its own Regional matchmaker that can still place a
player into another game Region; AWS WAF and Shield Advanced protect each backend;
a Global Accelerator custom routing accelerator maps listener ports to game-server
instance ports and routes the player deterministically to the session; hosting
locations combine AWS Regions (preferred, most capacity), Local Zones for under-served
geographies, Outposts/GameLift Anywhere for hybrid or on-premises capacity.

What to check: Route 53 record types and health checks; accelerator endpoint groups
and traffic dials; which locations each matchmaker can place into; capacity per
location (`gamelift:DescribeFleetLocationCapacity`).

## Scenario B — Game backends

REST or WebSocket services for player profiles, inventory, stats, leaderboards,
presence and chat. Deployed on instances, containers or serverless.

### Container-based backend (EKS/ECS)

Recognize it by: EKS cluster or ECS services in private subnets across AZs behind an
ALB with AWS WAF; NAT gateways per AZ; Global Accelerator in front of the ALB with
Route 53 custom domains; Aurora for profiles/entitlements/purchases, ElastiCache for
leaderboards, pub/sub and caching, DynamoDB for high-volume key-value player data;
CloudFront distributing client binaries and assets.

What to check: HPA plus cluster/node autoscaling on utilization that tracks player
demand; multi-AZ placement; replication for databases and caches; WAF on the ALB
(GAMESEC04-BP02, GAMESEC06-BP01); NAT gateway port-allocation errors under login
storms (see `incident-symptom-map.md`).

### Serverless backend (API Gateway + Lambda + DynamoDB)

Recognize it by: Cognito user pool for players; API Gateway HTTP/REST APIs invoking
Lambda per feature; one DynamoDB table per feature (connection state, game details,
progress, leaderboard); WebSocket API for multiplayer notifications; SNS/SQS/
EventBridge for asynchronous work.

What to check: per-feature tables and functions (enables cost attribution,
GAMECOST01-BP01); Lambda concurrency quotas and provisioned concurrency for login and
matchmaking paths; API authorizers; DynamoDB on-demand vs provisioned against the
traffic shape; TTL on connection-state tables (GAMESUS01-BP02).

## Scenario C — Cloud game development (CGD)

Build farms, source control and virtual workstations for distributed development
teams.

### CI/CD

Recognize it by: Perforce (Helix Core) on EC2 with EBS, replicated across AZs;
Jenkins controllers (ideally two, one per AZ, behind a load balancer) driving
ephemeral Docker build agents on Spot/On-Demand; EC2 Mac instances for iOS signing;
Secrets Manager for provisioning profiles and certificates; artifacts to S3 with
notifications; AWS Device Farm for mobile test; Direct Connect for in-office
developers, Client VPN or Verified Access for remote; Transit Gateway between VPCs.

What to check: source control replication and backups to S3; build-farm auto scaling
and Spot diversification; pipeline-stage least privilege and CloudTrail auditing
(GAMESEC08-BP01); SAST/SCA in the pipeline (GAMESEC09-BP01).

### Workstations

Recognize it by: GPU graphics instances in Auto Scaling groups built from EC2 Image
Builder AMIs with Amazon DCV server; DCV Session Manager broker; Client VPN; Route 53
private DNS; managed Microsoft AD; FSx for Windows File Server for project storage.

What to check: idle workstations shut down and work backed up to durable storage;
GPU instances used only where needed (GAMESUS02-BP02).

## Scenario D — Game analytics pipeline

Recognize it by: Kinesis Data Streams (or MSK) ingesting JSON events from clients,
servers and backends; Amazon Data Firehose to S3 (data lake); Managed Service for
Apache Flink or Kinesis analytics for real-time metrics into CloudWatch; Glue catalog
and Athena for interactive analysis; API Gateway + Lambda + DynamoDB as the
solution's admin API; QuickSight or Grafana dashboards.

What to check: stream shard/throughput headroom for launch-day telemetry
(`kinesis:DescribeStreamSummary`), Firehose delivery failures, S3 lifecycle and
One Zone-IA for transient telemetry (GAMECOST03-BP01), Live Ops real-time dashboards
and alerts (GAMEOPS06-BP01, GAMESEC05-BP01), no PII in client telemetry
(GAMESOPS04-BP01).

## Messaging patterns the lens expects

| Need | Lens guidance |
|---|---|
| Player engagement (invites, push) | SNS mobile push; Amazon Pinpoint for email/SMS/push campaigns and transactional messages such as MFA codes and password resets. |
| Group messaging / in-game chat | ElastiCache (Redis OSS) pub/sub; WebSocket API. |
| Service-to-service | SQS for decoupled background work (leaderboards, playtime), SNS pub/sub, MSK for streaming. |

## Hosting option trade-offs (GAMEPERF01)

| Option | Fits | Watch for |
|---|---|---|
| Amazon GameLift managed (EC2 or container fleets) | Session-based multiplayer when the team does not want to build fleet management and matchmaking | Queue/location design, Spot fleet interruptions, runtime configuration density |
| EC2 Auto Scaling | Legacy server builds, maximum control | Session-aware scale-in, instance diversification, ENA and PPS limits, patching |
| ECS / EKS (including Fargate) | High packing density, same image as dev | Node termination vs active sessions, networking complexity, PDBs not honored by managed node group termination |
| AWS Lambda | Turn-based or asynchronous gameplay, lightweight stateless logic | Not for long-lived sessions; cold starts on login spikes |
| Local Zones / Outposts / GameLift Anywhere | Latency to under-served geographies, hybrid capacity | Parent-Region dependencies, capacity footprint smaller than Regions |
