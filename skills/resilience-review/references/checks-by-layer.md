# Read-only checks by layer

Map the workload first, then check every layer. A Region recovery fails at its
weakest layer: replicated data is no use if the load balancer, the container
images or the secrets do not exist in the recovery Region.

Run these only for the resources in scope. All calls are read-only. Record any call
that is denied or skipped and show it next to the finding.

## Find the workload (when the user names none)

Look in the Regions the user named. If they named none, do not scan every Region:
read where the account spends with `ce:GetCostAndUsage` (the last full month,
grouped by the `REGION` dimension) and check the Regions with the most spend. If
that call is denied, ask the user which Regions to check, as the last line of the
answer. Always say which Regions you checked and why.

- `ListServices` in the next generation of AWS Resilience Hub: a workload that is
  already a Resilience Hub service. Follow "If the workload is already in
  Resilience Hub" in SKILL.md for it. This check also runs when the user names a
  workload.

- `cloudformation:ListStacks` and `cloudformation:ListStackResources`: each
  application stack is a candidate. Stacks that only hold tooling (for example CDK
  bootstrap or SAM-managed buckets) are not workloads.
- `cloudformation:ListStackSets` (with `CallAs` set to `DELEGATED_ADMIN` in a
  delegated administrator account), then `cloudformation:ListStackInstances` for
  each StackSet: the `Account` and `Region` of every stack instance. A StackSet
  deploys the same stack to several Regions: add every Region where it deploys
  part of the workload to the Regions you check. A StackSet is Regional and lives
  in the administrator account that created it, so run the call in each Region
  you check; if the account is only a target, say StackSets were not checked.
- `servicecatalog:ListApplications` (myApplications, AWS Service Catalog
  AppRegistry): the resources of an application carry the `awsApplication` tag.
- `resource-groups:ListGroups`.
- `tag:GetResources`: tag values shared by several resources (for example `app`,
  `application`, `service`, `project`, `workload`).

Shared infrastructure, such as a network stack whose exports several stacks
import, is a dependency of each workload, not a workload of its own. Always review
the parts of it that the workload uses, in the Shared dependencies layer: the VPC,
subnets, route tables, NAT gateways, endpoints and Transit Gateway attachments
that its resources use (read from their own configuration), and the exports its
stacks import (`cloudformation:ListExports`, then `cloudformation:ListImports` for
each export). Put its gaps in the workload's roadmap, marked shared, without
naming the other workloads that use it.

Then follow "Choose the path first" in SKILL.md: assess the only workload, or list
the candidates and ask which one to assess first.

## Map the workload

Find every component of the one workload, by the names, tags or CloudFormation
stack the user gives, plus the resources connected to them by configuration.
Group them into layers:

| Layer | Typical components |
|---|---|
| Entry and routing | Route 53, CloudFront, API Gateway, Application/Network Load Balancers |
| Compute | EC2 instances, Auto Scaling groups, Amazon ECS services, Amazon EKS clusters, AWS Lambda functions, AWS Step Functions state machines |
| Data | RDS, Aurora, DynamoDB, ElastiCache, MemoryDB, DocumentDB, Neptune, Redshift, OpenSearch |
| Storage | EBS, EFS, FSx, S3 |
| Messaging and events | SQS, SNS, Kinesis, MSK, EventBridge |
| Identity | Amazon Cognito user pools |
| Shared dependencies | Network (VPC, subnets, security groups, endpoints), Secrets Manager, KMS keys, ECR images, Parameter Store, certificates, IaC, service quotas |

A service that is not in this table still belongs to its layer: check it with
"Any other service" below. If a layer is empty for this workload, say so. If you
cannot tell whether a component belongs to the workload, list it as a possible
member instead of sweeping the account.

## What each finding breaks

| Finding | Breaks which scenario |
|---|---|
| A single EC2 instance not in an Auto Scaling group, a single node, a single task | single node failure, AZ failure |
| An Auto Scaling group, ECS service, EKS node group or load balancer in one AZ only | AZ failure |
| No Multi-AZ, no replica, no automatic failover on a data store | single node failure, AZ failure |
| Backup frequency longer than the RPO | every scenario that needs a restore |
| Backup retention too short to reach a clean copy | bad data |
| No copy or replica of data outside the Region | Region failure |
| No AMIs, container images, IaC or pipeline able to deploy compute in the recovery Region | Region failure |
| Secrets, KMS keys or certificates missing in the recovery Region | Region failure (restores and apps fail to start) |
| Service quotas or capacity in the recovery Region below what the workload needs (see Shared dependencies) | Region failure |
| The network or other shared infrastructure the workload needs (VPC and subnets, Transit Gateway, VPN or Direct Connect, endpoints) missing in the recovery Region and not in IaC | Region failure (nothing can start or be reached there) |
| Point-in-time recovery off, no versioning on a bucket, no backups of a file system | bad data |
| Deletion protection off | bad data (an accidental delete) |
| Backups only in the same account | compromised account, ransomware |
| No failover routing (DNS or other) | Region failure (the copy exists but traffic cannot reach it) |
| One zonal NAT gateway serving several AZs, or an interface endpoint in one AZ | AZ failure (outbound or service access lost in the other AZs) |
| A VPN tunnel down, or one Direct Connect connection or location | single node failure (the on-premises link), location failure |

## Entry and routing

- `elbv2:DescribeLoadBalancers` (Availability Zones), `elbv2:DescribeLoadBalancerAttributes`
  (cross-zone, `zonal_shift.config.enabled`), `elbv2:DescribeTargetHealth`.
- `route53:ListHealthChecks` and the hosted zone's records: is there failover or
  other routing that could send traffic to a recovery Region?
- `arc-zonal-shift:ListManagedResources`: which resources can be shifted away from
  an impaired AZ.

Traps:

- Load balancers are Regional. The recovery Region needs its own load balancer,
  created ahead of time or from IaC, plus its own certificate.
- ARC zonal shift and zonal autoshift support EC2 Auto Scaling groups, Amazon EKS,
  and Application and Network Load Balancers. A load balancer that is failing open
  ignores a zonal shift.
- No routing means a copy can exist but users cannot reach it.

### Amazon API Gateway

- `apigateway:GET` on the REST APIs, HTTP APIs and custom domain names: endpoint
  type, stages, custom domains.

Traps:

- APIs are Regional. Failover to another Region needs the API deployed in the
  recovery Region with the same custom domain name, and Route 53 failover records
  in front of both. Clients that call the default `execute-api` URL are tied to one
  Region.
- The recovery Region also needs whatever the API calls (functions, authorizers,
  backends).

### Amazon CloudFront

- `cloudfront:ListDistributions` and `cloudfront:GetDistributionConfig`: origins
  and origin groups.

Traps:

- CloudFront is global; its origins are not. An origin group fails over to a
  secondary origin on the HTTP error codes you set, and only for `GET`, `HEAD` and
  `OPTIONS` requests. Writes need another failover path, such as Route 53 or ARC.

## Compute

### EC2 and Auto Scaling

- `autoscaling:DescribeAutoScalingGroups`: subnets and AZs, minimum and desired
  capacity.
- `ec2:DescribeInstances`: instances that are not in any Auto Scaling group are
  single points of failure.
- `ec2:DescribeImages` (owner self) and `ec2:DescribeSnapshots`, in the source and
  in the recovery Region: do AMIs and EBS snapshots exist there? Map each copy to
  its source before you credit it:
  - AMI: `SourceImageId` and `SourceImageRegion` on the copy name the source AMI
    (set by `CopyImage`; missing on some older AMIs).
  - Copy made by AWS Backup: `backup:ListRecoveryPointsByBackupVault` on the vault
    in the recovery Region gives each recovery point's `ResourceArn` (the source
    resource) and `SourceBackupVaultArn`; `backup:ListCopyJobs` links each
    `SourceRecoveryPointArn` to its `DestinationRecoveryPointArn`.
  - EBS snapshot copied by hand: the `VolumeId` of a copy is arbitrary and does
    not name the source. Match by description or tags; if neither names the
    source, say the copy could not be mapped and do not count it.
- `drs:DescribeSourceServers`: is AWS Elastic Disaster Recovery replicating the
  servers?

Traps:

- An AMI or launch template that exists only in the source Region cannot start
  instances in the recovery Region.
- AWS Elastic Disaster Recovery is a pilot-light style option that can give RPO and
  RTO close to warm standby at lower cost (Well-Architected REL13-BP02). It covers
  applications and databases hosted on EC2, not RDS: RDS and Aurora need their own
  cross-Region copies or replicas (see Data).

### Amazon ECS

- `ecs:DescribeServices`: desired count, subnets (one AZ or several), capacity
  providers, task definition.
- `ecs:DescribeTaskDefinition`: container images and where they come from.
- `ecr:DescribeRegistry`: replication configuration for the images.

Traps:

- A service with one task, or subnets in one AZ, fails with that task or AZ.
- ECR replication only copies images pushed after it is configured. Older images
  need replication backfill.
- Always report where each image lives and whether it can be pulled in the
  recovery Region: a private ECR repository with or without replication, an ECR
  pull-through cache (the cache rule and its repositories are Regional, so the
  recovery Region needs its own rule), or a public or third-party registry (an
  outside dependency during recovery).

### Amazon EKS

- `eks:DescribeCluster`: subnets and AZs.
- `eks:ListNodegroups` and `eks:DescribeNodegroup`: subnets, scaling limits.
- `backup:ListProtectedResources`: is the cluster protected by AWS Backup?

Traps:

- AWS Backup supports EKS: cluster state and persistent volumes (EBS, EFS, S3),
  with cross-Region and cross-account copies, and restore of a whole cluster, a
  namespace or a single volume.
- Without a backup, the recovery Region needs the cluster from IaC and the
  workloads from Git or a pipeline. Ask how the cluster would be recreated.

### AWS Lambda

- `lambda:GetFunction`: where the code comes from (S3 or ECR). If it is denied, use
  `lambda:GetFunctionConfiguration` (package type, image URI, runtime) and
  `lambda:ListEventSourceMappings` (triggers), and say the code location was not
  read.

Traps:

- Functions are Regional. The recovery Region needs the code, the IaC and the event
  sources (queues, streams, schedules) too.

### AWS Step Functions

- `states:ListStateMachines` and `states:DescribeStateMachine`: type, definition,
  the services each state calls.

Traps:

- State machines are Regional. AWS Resilience Hub checks that the same workflow is
  deployed in another Region and that it uses versions and aliases. The recovery
  Region also needs every function and service the workflow calls.

## Data

### Amazon RDS and Aurora

- `rds:DescribeDBInstances`: `MultiAZ`, `BackupRetentionPeriod`,
  `ReadReplicaDBInstanceIdentifiers`, `DeletionProtection`, `StorageEncrypted`.
- `rds:DescribeDBInstanceAutomatedBackups`: replicated automated backups in another
  Region, if any.
- `rds:DescribeDBSnapshots`: manual and automated snapshots, and where they are.
- Aurora: `rds:DescribeDBClusters` and `rds:DescribeGlobalClusters` (is the cluster
  part of an Aurora Global Database?).

Traps:

- Automated backups give point-in-time recovery inside the retention window. With
  retention of 1 day, you cannot go back further than a day.
- RDS for MySQL and other RDS engines support cross-Region read replicas
  (asynchronous). In a Region event you promote the replica to a standalone
  instance; replication lag at that moment is the data you lose.
- Cross-Region automated backups are not available for every engine and Region
  pair. Check with `rds:DescribeSourceRegions` and the RDS documentation before
  recommending them.
- Aurora Global Database: an unplanned failover has an RPO usually measured in
  seconds (the replication lag at the time). A planned switchover has RPO 0.
- With AWS Backup, RDS, Aurora, DocumentDB and Neptune copies can go to another
  Region and another account in a single action. RDS Multi-AZ DB clusters (not
  Multi-AZ instances) do not support copy operations.
- Encrypted instances need a KMS key in the destination Region for cross-Region
  copies and replicas.

### Amazon DynamoDB

- `dynamodb:DescribeContinuousBackups`: `PointInTimeRecoveryStatus` and
  `RecoveryPeriodInDays`. The account-level "continuous backups" flag is not the
  PITR status; read PITR itself.
- `dynamodb:ListBackups`: on-demand backups.
- `dynamodb:DescribeTable`: `Replicas` (is it a global table?). If this call is
  blocked, say that replica information could not be read.

Traps:

- PITR restores to any second in the recovery period. The default period is 35
  days; it can be set from 1 to 35 days.
- Global tables replicate deletes and bad writes. Keep PITR on even with global
  tables.
- AWS Backup can copy DynamoDB backups to another Region or account only when
  DynamoDB advanced features are turned on in AWS Backup. Read
  `backup:DescribeRegionSettings`: `ResourceTypeManagementPreference.DynamoDB` is
  `true` when they are on. Without them, a copy rule in a backup plan does not
  protect the table against a Region failure.

### Amazon ElastiCache (Valkey, Redis OSS)

- `elasticache:DescribeReplicationGroups`: number of member clusters (replicas),
  `AutomaticFailover`, `MultiAZ`, `SnapshotRetentionLimit`,
  `GlobalReplicationGroupInfo`, node type.
- `elasticache:DescribeSnapshots`: existing backups.

Traps:

- AWS Backup does not support ElastiCache. Use ElastiCache's own automatic
  snapshots and exports; do not recommend adding the cache to a backup plan.
- Ask first whether the cache is rebuildable. If it is, cross-Region protection is
  usually not worth it.
- Global Datastore needs node-based ElastiCache (Valkey 7.2+ or Redis OSS 5.0.6+)
  on large-and-above nodes of supported families (M5, M6g, M7g, M8g, R5, R6g, R7g,
  R8g, C7gn, C8gn). Automatic failover needs at least one replica.
- To seed a cache in another Region from a backup: export the backup to an S3
  bucket in the same Region, copy the `.rdb` file to the other Region, then seed a
  new cluster from it.

### Amazon MemoryDB

- `memorydb:DescribeClusters`: `AvailabilityMode` (`multiaz` or `singleaz`), the
  nodes in each shard, `SnapshotRetentionLimit`, `MultiRegionClusterName`.
- `memorydb:DescribeMultiRegionClusters`: the Regions of a Multi-Region cluster.

Traps:

- MemoryDB keeps every write in a Multi-AZ transaction log, so it can be the only
  copy of the data. Ask before treating it as a rebuildable cache.
- Multi-AZ needs more than one node per shard. A shard with one node stops
  accepting writes until its node is replaced.
- MemoryDB Multi-Region is active-active: every regional cluster takes reads and
  writes, replication between Regions is asynchronous, and conflicting writes are
  resolved by last writer wins. It copies bad writes too: keep snapshots. It is
  available in some Regions only: check before recommending it.
- AWS Backup does not support MemoryDB. To restore in another Region, export a
  snapshot to an S3 bucket in the same Region, copy the `.rdb` file to the other
  Region, then seed a new cluster from it.

### Amazon DocumentDB and Amazon Neptune

- `docdb:DescribeDBClusters` / `neptune:DescribeDBClusters` (served by the RDS API,
  so `rds:Describe*` permissions apply): cluster members and their AZs,
  `BackupRetentionPeriod`, `DeletionProtection`; `DescribeGlobalClusters` for
  global clusters.

Traps:

- A cluster with one instance has no failover target. A replica in another AZ
  gives in-Region failover.
- Global clusters replicate to other Regions, and copy bad writes too.
- With AWS Backup, DocumentDB and Neptune copies can go to another Region and
  another account in a single action.

### Amazon Redshift

- `redshift:DescribeClusters`: node count, `ClusterSnapshotCopyStatus` (cross-Region
  snapshot copy), automated snapshot retention. For Redshift Serverless, read the
  namespace's snapshots and recovery points.

Traps:

- AWS Backup cannot copy Redshift backups to another Region or account. Use
  Redshift's own cross-Region snapshot copy.

### Amazon OpenSearch Service

- `es:DescribeDomain`: `ClusterConfig` (instance count, `ZoneAwarenessEnabled`,
  Multi-AZ with Standby, dedicated master nodes), VPC subnets.
- `es:DescribeOutboundConnections`: cross-cluster replication to another domain.

Traps:

- Without zone awareness, all nodes are in one AZ.
- Automated snapshots (hourly, kept 14 days, on OpenSearch and Elasticsearch 5.3
  and later) are only for recovering that domain. To restore in another domain or
  Region, use manual snapshots in your own S3 bucket or cross-cluster replication
  (OpenSearch 1.1 or later, Elasticsearch 7.10).
- A search index can often be rebuilt from its source data. Ask before protecting
  it like a source of truth.

### AWS Backup

- `backup:ListBackupPlans`, `backup:ListProtectedResources`,
  `backup:ListRecoveryPointsByResource` for the resources in scope.
- `backup:ListRecoveryPointsByBackupVault` on the destination vault of each copy
  rule, and `backup:ListCopyJobs`: did copies actually land?
- `backup:DescribeRegionSettings`: which resource types are opted in, and whether
  DynamoDB advanced features are on.
- `backup:ListBackupVaults`: `VaultType` (`LOGICALLY_AIR_GAPPED_BACKUP_VAULT`) and
  `Locked` of each vault that holds the workload's copies.
- `backup:GetBackupPlan` (`ScanSettings`, and `ScanActions` in each rule) and
  `backup:ListScanJobs`: does Malware Protection for AWS Backup scan the recovery
  points, and with what result?
- For a full account-wide coverage audit, recommend the `aws-backup-coverage-review`
  skill instead of repeating it here.

Traps:

- A resource inside a backup plan is not protected until recovery points exist.
  Check recovery points, not only plan membership.
- Not every service supports every feature. Check the AWS Backup feature
  availability table before recommending a copy rule (for example, DynamoDB needs
  advanced features for cross-Region copies; ElastiCache is not supported).
- A cross-Region or cross-account copy of a continuous backup becomes a snapshot.
  Point-in-time restore is not available from the copy, so the copy's RPO is the
  copy frequency.
- Against ransomware or a compromised account, a logically air-gapped vault is
  AWS Backup's own answer: it is always locked in Vault Lock compliance mode, so
  no one can delete its recovery points early, and it can be shared with a
  recovery account (AWS RAM) or opened through multi-party approval if the owning
  account is lost. Check which resource types it supports in the feature
  availability table.
- Malware Protection for AWS Backup (Amazon GuardDuty) scans EC2, EBS and S3
  recovery points, after each backup or on demand, with the result
  `THREATS_FOUND` or `NO_THREATS_FOUND`. Use it to find the last clean recovery
  point before a restore. Other resource types are not scanned.

## Storage

- EBS: snapshots and their copies outside the Region (`ec2:DescribeSnapshots`).
- EFS: `elasticfilesystem:DescribeReplicationConfigurations`. EFS replication is
  continuous and designed for an RPO and RTO of minutes.
- FSx: `fsx:DescribeFileSystems`: `DeploymentType` in `OntapConfiguration`,
  `OpenZFSConfiguration` or `WindowsConfiguration`, and
  `AutomaticBackupRetentionDays`. A `MULTI_AZ_*` file system has a standby file
  server in a second AZ and fails over to it automatically; a `SINGLE_AZ_*` one
  keeps its file servers in one AZ. Backups also go through AWS Backup, which can
  copy them to another Region or account. Across Regions, FSx for ONTAP
  replicates with NetApp SnapMirror (RPO as low as 5 minutes), which is set up in
  ONTAP itself (CLI or REST API), so ask the team whether it exists. FSx for
  OpenZFS has on-demand replication to a file system in another Region or account
  (RPO as low as 15 minutes and RTO as low as 5 minutes, for up to 2 GB/s of
  changes).
- S3: `s3:GetBucketVersioning` and `s3:GetReplicationConfiguration`. Without versioning,
  an overwrite or delete cannot be undone; replication to another Region needs
  versioning on both buckets. In the same `GetBucketVersioning` response,
  `MFADelete` set to `Enabled` means that deleting an object version or changing
  versioning needs the root user with MFA; if the field is missing, MFA delete was
  never set up. For a full bucket posture review, point to the
  `storage-s3-resiliency-expertise` skill.

## Messaging and events

- SQS, SNS, Kinesis and MSK are Regional. Check whether queues, topics and streams
  exist in the recovery Region, and how messages in flight would be handled.
- `sqs:GetQueueAttributes` (`RedrivePolicy`): a queue without a dead-letter queue
  keeps retrying failing messages until they expire.
- Amazon MSK:
  - `kafka:ListClustersV2` and `kafka:DescribeClusterV2`: provisioned or
    serverless, the broker subnets (`ClientSubnets`, so the AZs) and the number of
    brokers.
  - The MSK `DescribeTopic` API for each topic the workload uses:
    `replicationFactor` (provisioned clusters on Kafka 3.6 or later). It needs
    `kafka-cluster:Connect` and `kafka-cluster:DescribeTopic` on the cluster; if
    it is denied, list topic replication as not checked.
  - `kafka:ListReplicators`: does MSK Replicator copy the topics to a cluster in
    another Region?
  - Traps: use three AZs, a replication factor of at least 3, and
    `min.insync.replicas` of at most the replication factor minus 1. A
    replication factor of 1 can take partitions offline during a rolling update
    or a broker failure; `min.insync.replicas` equal to the replication factor can
    stop producers during a rolling update. AWS Backup does not support MSK. For a
    Region failure, MSK Replicator copies the data, topic configuration and
    consumer group offsets asynchronously to a cluster in the recovery Region; it
    copies bad messages too.
  - For MSK operations, point to the `msk-operations` skill.
- Kinesis Data Streams: `kinesis:DescribeStreamSummary` (mode, retention). A stream
  is replicated across three AZs in its Region; retention is 24 hours by default
  and up to 365 days. The recovery Region needs its own stream, and producers and
  consumers that can switch to it.
- EventBridge: `events:ListEventBuses`, `events:ListRules`, `events:ListArchives`
  and `events:ListEndpoints`. Buses, rules and archives are Regional. A global
  endpoint fails event ingestion over to an event bus in a secondary Region, using
  a Route 53 health check; that bus needs the same rules and targets.

## Identity

- Amazon Cognito: `cognito-idp:DescribeUserPool`. A user pool is Regional.
  Multi-Region replication creates a replica user pool in another Region that
  handles sign-in and tokens; sign-up, password resets and configuration changes
  work only in the primary. Without a replica, a pool in the recovery Region has
  none of the users.

## Shared dependencies

- Network: VPCs, subnets, security groups, VPC endpoints, transit gateways and
  on-premises links are Regional. In the recovery Region, read
  `ec2:DescribeVpcs`, `ec2:DescribeSubnets` and `ec2:DescribeTransitGateways`, and
  say whether the network the workload needs exists there (subnets in several
  AZs, the same routes to on-premises and other VPCs) or can be created from IaC,
  including a shared network stack.
- Network single points in the Region (they break the AZ scenario even when every
  data store is Multi-AZ). Check only what the workload's subnets use:
  - **NAT gateways:** `ec2:DescribeNatGateways` and `ec2:DescribeRouteTables`. A
    zonal NAT gateway lives in one AZ: if private subnets in other AZs route
    through it and its AZ fails, they lose outbound access. Good: one zonal NAT
    gateway per AZ with each AZ's subnets routed to their own, or a regional NAT
    gateway (it spans AZs on its own; in manual mode, check it covers each AZ the
    workload uses).
  - **Interface VPC endpoints:** `ec2:DescribeVpcEndpoints`. An endpoint with
    subnets in one AZ only is a single point; production needs at least two AZs.
  - **Transit Gateway:** `ec2:DescribeTransitGatewayVpcAttachments`
    (`SubnetIds`). A VPC attachment takes one subnet per AZ, and resources in an
    AZ with no attachment subnet cannot reach the transit gateway: check that
    every AZ the workload uses has one. A transit gateway is Regional, so the
    recovery Region needs its own, with its own attachments and on-premises
    connections; inter-Region peering
    (`ec2:DescribeTransitGatewayPeeringAttachments`) connects the two while both
    Regions run.
  - **Site-to-Site VPN:** `ec2:DescribeVpnConnections`. Each connection has two
    tunnels; both must be configured and up (`VgwTelemetry` status). One tunnel
    down means no redundancy during maintenance.
  - **Direct Connect:** `directconnect:DescribeConnections` and
    `directconnect:DescribeVirtualInterfaces`. One connection, or several at a
    single location, cannot survive a location failure. Name the Resiliency
    Toolkit model it matches: development and test (separate devices in one
    location, no protection against a location failure), high resiliency (single
    connections to more than one location, SLA of 99.9%) or maximum resiliency
    (separate connections on separate devices in more than one location, SLA of
    99.99%). A Site-to-Site VPN configured as backup is a second path with less
    bandwidth (up to 1.25 Gbps per tunnel); say whether it can carry the traffic.
    The Direct Connect failover test in the Resiliency Toolkit proves the second
    path works.
  - Do not read on-premises devices; say they are not checked.
- Secrets Manager: `secretsmanager:DescribeSecret` shows replica Regions. Secrets
  can be replicated to other Regions.
- KMS: encrypted copies and replicas need a key in the destination Region.
  Multi-Region keys keep the same key material in several Regions.
- ECR: see Amazon ECS above.
- Certificates (ACM) and Parameter Store values are Regional.
- Service quotas in the recovery Region: point to the `service-quota-check` skill.
- Capacity in the recovery Region, for EC2 and for ECS or EKS on EC2:
  `ec2:DescribeInstanceTypeOfferings` there (location type `availability-zone`)
  shows whether each instance type the workload uses is offered in its AZs, and
  `ec2:DescribeCapacityReservations` there shows reserved capacity. Only a
  Capacity Reservation makes capacity sure at failover time: without one, say the
  capacity is not reserved, never that it will be there. Capacity Reservations do
  not apply to Fargate or Lambda.
- IaC and pipelines: can they deploy the workload to the recovery Region today?

## Any other service

For a service with no section above, answer these questions and put each gap in
the roadmap like any other:

1. **State:** does it hold data or configuration that would be lost, or can it be
   recreated from IaC alone?
2. **In-Region redundancy:** does it span several AZs, and is that turned on?
3. **Bad data:** does it have backups or point-in-time recovery, and how long are
   they kept? Does AWS Backup support it (feature availability table)?
4. **Region:** is there a copy, replica or deployment in the recovery Region?
   Look up the service's own backup copy or cross-Region feature in the AWS
   documentation. Do not assume that one exists or that none exists.
5. **Dependencies:** which keys, secrets, networks, quotas or other services must
   exist in the recovery Region for it to run?
6. **Not readable:** if a call is denied, list the component under Not checked
   with the reason.

## Sources

- NAT gateway basics (one per AZ):
  https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html
- Regional NAT gateways:
  https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateways-regional.html
- Interface endpoints, subnets and Availability Zones:
  https://docs.aws.amazon.com/vpc/latest/privatelink/privatelink-access-resources.html
- Site-to-Site VPN tunnel options (two tunnels):
  https://docs.aws.amazon.com/vpn/latest/s2svpn/VPNTunnels.html
- Direct Connect Resiliency Toolkit:
  https://docs.aws.amazon.com/directconnect/latest/UserGuide/resiliency_toolkit.html
- Direct Connect resiliency recommendations (VPN backup bandwidth):
  https://aws.amazon.com/directconnect/resiliency-recommendation/
- AWS Well-Architected Framework, REL13-BP02:
  https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_planning_for_recovery_disaster_recovery.html
- ARC zonal shift supported resources:
  https://docs.aws.amazon.com/r53recovery/latest/dg/arc-zonal-shift.resource-types.html
- AWS Backup for Amazon EKS:
  https://docs.aws.amazon.com/aws-backup/latest/devguide/working-with-supported-services.html
- ECR private image replication:
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/replication.html
- EFS replication:
  https://docs.aws.amazon.com/efs/latest/ug/features.html
- Secrets Manager multi-Region secrets:
  https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_ReplicateSecretToRegions.html
- DynamoDB configurable PITR periods:
  https://aws.amazon.com/blogs/database/announcing-configurable-point-in-time-recovery-periods-for-amazon-dynamodb/
- ElastiCache Global Datastore prerequisites:
  https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Redis-Global-Datastores-Getting-Started.html
- ElastiCache exporting a backup:
  https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/backups-exporting.html
- Cross-Region read replicas for RDS for MySQL:
  https://aws.amazon.com/blogs/aws/cross-region-read-replicas-for-amazon-rds-for-mysql/
- Aurora Global Database switchover and failover:
  https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database-disaster-recovery.html
- AWS Backup feature availability by resource:
  https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html
- myApplications and the `awsApplication` tag:
  https://aws.amazon.com/blogs/mt/getting-started-with-myapplications-for-terraform-managed-applications/
- Multi-Region failover for Amazon API Gateway:
  https://aws.amazon.com/blogs/compute/implementing-multi-region-failover-for-amazon-api-gateway/
- CloudFront origin failover:
  https://aws.amazon.com/blogs/networking-and-content-delivery/improve-web-application-availability-with-cloudfront-and-route53-hybrid-origin-failover/
- AWS Resilience Hub checks for Step Functions:
  https://docs.aws.amazon.com/resilience-hub/latest/userguide/resilience-checks.html
- Amazon DocumentDB global clusters:
  https://docs.aws.amazon.com/documentdb/latest/devguide/replication.html
- Amazon Redshift cross-Region snapshot copy:
  https://aws.amazon.com/blogs/aws/automated-cross-region-snapshot-copy-for-amazon-redshift/
- OpenSearch Service snapshots:
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/managedomains-snapshots.html
- OpenSearch Service cross-cluster replication:
  https://docs.aws.amazon.com/opensearch-service/latest/developerguide/replication.html
- S3 replication requires versioning:
  https://aws.amazon.com/s3/faqs/
- Kinesis Data Streams durability and retention:
  https://aws.amazon.com/kinesis/data-streams/features/
- EventBridge global endpoints:
  https://aws.amazon.com/blogs/compute/introducing-global-endpoints-for-amazon-eventbridge/
- Amazon Cognito multi-Region replication:
  https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-multi-region.html
- Cost Explorer `GetCostAndUsage` (group by `REGION`):
  https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html
- StackSets concepts (administrator account, Regional StackSets) and
  `ListStackInstances`:
  https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-concepts.html
  https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_StackInstanceSummary.html
- AMI ancestry (`SourceImageId`, `SourceImageRegion`):
  https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_Image.html
- EBS snapshot copies have an arbitrary volume ID:
  https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_Snapshot.html
- AWS Backup recovery points and copy jobs (`ResourceArn`, `SourceBackupVaultArn`,
  `SourceRecoveryPointArn`):
  https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_RecoveryPointByBackupVault.html
  https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_CopyJob.html
- AWS Backup logically air-gapped vaults:
  https://docs.aws.amazon.com/aws-backup/latest/devguide/logicallyairgappedvault.html
- Malware Protection for AWS Backup:
  https://docs.aws.amazon.com/aws-backup/latest/devguide/malware-protection.html
- Elastic Disaster Recovery covers EC2-hosted databases, not RDS:
  https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html
- MemoryDB Multi-AZ, Multi-Region and snapshot export:
  https://docs.aws.amazon.com/memorydb/latest/devguide/autofailover.html
  https://docs.aws.amazon.com/memorydb/latest/devguide/multi-region.html
  https://docs.aws.amazon.com/memorydb/latest/devguide/snapshots-exporting.html
- MSK best practices, topic operations and MSK Replicator:
  https://docs.aws.amazon.com/msk/latest/developerguide/bestpractices.html
  https://docs.aws.amazon.com/msk/latest/developerguide/msk-topic-operations-information.html
  https://docs.aws.amazon.com/msk/latest/developerguide/msk-replicator.html
- FSx deployment types, SnapMirror and OpenZFS on-demand replication:
  https://docs.aws.amazon.com/fsx/latest/APIReference/API_OntapFileSystemConfiguration.html
  https://docs.aws.amazon.com/fsx/latest/APIReference/API_OpenZFSFileSystemConfiguration.html
  https://aws.amazon.com/fsx/netapp-ontap/features/
  https://aws.amazon.com/fsx/openzfs/features/
- S3 MFA delete (`MFADelete` in `GetBucketVersioning`):
  https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetBucketVersioning.html
  https://repost.aws/knowledge-center/s3-bucket-mfa-delete
- Transit Gateway VPC attachments and Availability Zones, and transit gateways as
  a Regional construct with inter-Region peering:
  https://docs.aws.amazon.com/vpc/latest/tgw/tgw-vpc-attachments.html
  https://aws.amazon.com/blogs/networking-and-content-delivery/building-a-global-network-using-aws-transit-gateway-inter-region-peering/
- Capacity Reservations for recovery:
  https://docs.aws.amazon.com/drs/latest/userguide/Target-Related-FAQ.html
  https://aws.amazon.com/blogs/architecture/pilot-light-with-reserved-capacity-how-to-optimize-dr-cost-using-on-demand-capacity-reservations/
