# LSE Readiness — read-only discovery

Run only the calls relevant to the critical-path services confirmed in S0. All
are **read-only**; execute through the AWS DevOps Agent's audited read-only
access, in each event Region. Record configuration as evidence; never grade from
assumption. If a critical-path service can't be read, its rows are N/A with the
reason. Snippets show the read being made — they are illustrative, not run with
ambient credentials.

> Keep the review cheap: prefer `--query` server-side filtering and reuse one
> fetch across rows. Consider the `investigation-cost-guardrail` skill.

## CAP — Capacity & scaling

```bash
# Compute provisioner shape (diversification + min capacity)
aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[].{name:AutoScalingGroupName,min:MinSize,max:MaxSize,mixed:MixedInstancesPolicy}"
aws ec2 describe-launch-template-versions --versions '$Latest' \
  --query "LaunchTemplateVersions[].LaunchTemplateData.InstanceRequirements"
# Karpenter: via use_kubectl -> get nodepools -o yaml (zones + instance families)

# Capacity reservations (and future-dated for the event)
aws ec2 describe-capacity-reservations \
  --query "CapacityReservations[].{type:InstanceType,az:AvailabilityZone,count:TotalInstanceCount,state:State,start:StartDate}"

# EKS control-plane scaling / version + Auto Mode detection
aws eks describe-cluster --name <cluster> \
  --query "cluster.{version:version,status:status,autoMode:computeConfig.enabled,nodePools:computeConfig.nodePools}"
# autoMode=true -> AWS manages node provisioning/diversification; branch to the
# "EKS Auto Mode" note in best-practices.md CAP (grade pre-scaled workloads,
# resource requests, startup time; do NOT auto-PASS an idle Auto Mode cluster).

# Lambda provisioned concurrency (critical-path functions)
aws lambda get-provisioned-concurrency-config --function-name <fn> --qualifier <alias>
aws lambda list-provisioned-concurrency-configs --function-name <fn>

# ELB + LCU reservation
aws elbv2 describe-load-balancers --query "LoadBalancers[].{name:LoadBalancerName,type:Type,state:State.Code}"
aws elbv2 describe-capacity-reservation --load-balancer-arn <arn>

# EBS volume performance + snapshot-restore initialization (CAP9)
aws ec2 describe-volumes \
  --query "Volumes[].{id:VolumeId,type:VolumeType,iops:Iops,tput:Throughput,size:Size,snap:SnapshotId}"
aws ec2 describe-fast-snapshot-restores \
  --query "FastSnapshotRestores[].{snap:SnapshotId,az:AvailabilityZone,state:State}"
# A volume created from a snapshot lazy-loads blocks -> first access is slow until
# initialized. For the event, enable Fast Snapshot Restore on the source snapshot (volume
# is fully initialized at creation) or pre-read all blocks, so event-critical volumes serve
# full IOPS/throughput from the start. Size gp3 Iops/Throughput for peak (don't leave defaults).
```

## QTA — Service quotas  → delegate to `service-quota-check`

Do not guess limits. Invoke `service-quota-check` for: EC2 On-Demand vCPU
(`ec2` / L-1216C47A), NAT gateways, EIPs, Lambda concurrent executions
(`lambda` / L-B99A9384), ELB (`elasticloadbalancing`), and any service-specific
critical-path quota. Also pull increase-request history to confirm early
submissions are **granted**, not pending:

```bash
aws service-quotas list-requested-service-quota-change-history \
  --service-code <code> --query "RequestedQuotas[].{quota:QuotaName,status:Status,desired:DesiredValue}"
```

## RES — Resilience & fault isolation

```bash
# Multi-Region: run describe calls in each event Region and compare presence of
# auth / manifest / ad-decisioning services.

# DNS failover
aws route53 list-health-checks
aws route53 list-resource-record-sets --hosted-zone-id <zone> \
  --query "ResourceRecordSets[?Failover || contains(keys(@),'Region')]"
# Route 53 ARC routing controls (sub-TTL shed, operator-initiated) — if the customer has adopted
# ARC, this path is faster than plain Route 53 health-check failover (~60s TTL floor):
aws route53-recovery-control-config list-clusters
aws route53-recovery-control-config list-control-panels --cluster-arn <arn>
aws route53-recovery-cluster list-routing-controls --cluster-endpoints <endpoints>
# Not having ARC is NOT a FAIL — many customers rely on Route 53 health checks + CloudFront
# origin failover (CDN5) + multi-CDN switching (CDN8). ARC is a strengthening option, not a floor.

# Maintenance overlap -> delegate to aws-health-events (preferred)
aws health describe-scheduled-changes \
  --query "entities[].{service:service,region:region,start:startTime,end:endTime}"

# Version lifecycle / auto-upgrade exposure (RES7) vs end-of-standard-support:
aws eks describe-cluster --name <cluster> \
  --query "cluster.{version:version,support:upgradePolicy.supportType}"
# support=STANDARD -> EKS auto-upgrades at end of standard support; =EXTENDED -> stays
# on (billed) extended support until its end, then force-upgrades.
aws rds describe-db-instances \
  --query "DBInstances[].{id:DBInstanceIdentifier,engine:Engine,ver:EngineVersion,autoMinor:AutoMinorVersionUpgrade}"
aws rds describe-pending-maintenance-actions \
  --query "PendingMaintenanceActions[].{id:ResourceIdentifier,actions:PendingMaintenanceActionDetails[].Action}"
aws opensearch describe-domain --domain-name <domain> \
  --query "DomainStatus.{ver:EngineVersion,sw:ServiceSoftwareOptions.UpdateStatus,autoUpdate:SoftwareUpdateOptions.AutoSoftwareUpdateEnabled}"
aws elasticache describe-cache-clusters \
  --query "CacheClusters[].{id:CacheClusterId,engine:Engine,ver:EngineVersion,autoMinor:AutoMinorVersionUpgrade}"
# Also MSK cluster version and Lambda runtimes vs runtime deprecation.
# AUTHORITATIVE EOL SIGNAL: cross-check AWS Health (RES6 describe-scheduled-changes /
# describe-events) for "end of support" / "end of life" notifications on these services
# — the API version alone does not carry the EOL date. For EKS depth reuse eks-upgrade-readiness.
```

Service isolation (RES3), graceful degradation (RES4) and statelessness (RES5)
are mostly architectural: confirm from tags, separate clusters/node groups/VPCs,
circuit-breaker config (e.g. app mesh / Envoy / library config), and S1 context.

## CDN — Content delivery / edge

```bash
aws cloudfront list-distributions \
  --query "DistributionList.Items[].{id:Id,domain:DomainName,enabled:Enabled}"
aws cloudfront get-distribution-config --id <dist-id> \
  --query "DistributionConfig.{origins:Origins.Items[].{id:Id,domain:DomainName,shield:OriginShield},\
originGroups:OriginGroups,defaultCacheBehavior:DefaultCacheBehavior.{cachePolicy:CachePolicyId,\
functions:FunctionAssociations,lambdas:LambdaFunctionAssociations}}"
aws cloudfront get-cache-policy --id <cache-policy-id>   # key normalization / query-string handling
# Cache-hit ratio:
aws cloudwatch get-metric-statistics --namespace AWS/CloudFront --metric-name CacheHitRate \
  --dimensions Name=DistributionId,Value=<dist-id> Name=Region,Value=Global \
  --start-time <24h-ago> --end-time <now> --period 3600 --statistics Average --region us-east-1
# S3 origin (CDN6): if an origin's DomainName is an S3 bucket (…s3[.-]…amazonaws.com), the
# segment/manifest keys should be spread across prefixes — S3 scales to ~5,500 GET/s per
# partitioned prefix (no limit on number of prefixes), and a cache-miss thundering herd to
# one prefix can 503. Prefix layout is a design check (not fully API-discoverable) — confirm
# from key naming / S1 context. Keep Origin Shield (CDN2) on to collapse misses.

# MediaTailor SSAI (CDN7): if ads are inserted server-side, read playback configurations and
# prefetch schedules. The MediaTailor service itself scales; the LSE risk is (a) a scheduled
# ad break with no PrefetchSchedule (viewer-spike-aligned ADS surge), (b) a slow ADS with no
# player slate/fallback, and (c) origin/CDN wiring that defeats the CDN7 cache-hit discipline.
aws mediatailor list-playback-configurations \
  --query "Items[].{name:Name,ads:AdDecisionServerUrl,cdn:CdnConfiguration,origin:VideoContentSourceUrl,manifest:LogConfiguration}"
aws mediatailor get-playback-configuration --name <config-name>
aws mediatailor list-prefetch-schedules --playback-configuration-name <config-name> \
  --query "Items[].{name:Name,start:Consumption.StartTime,end:Consumption.EndTime,retrieval:Retrieval.StartTime}"
# No PrefetchSchedule for a known scheduled break (halftime, timeout, programming window) +
# a tier-1 concurrency ramp = CDN7 risk. Pair with TST4 (ADS/VAST capacity + tracking beacons).

# Multi-CDN / client-side switching (CDN8) is almost always a *player-side* decision
# (player SDK, client-side manifest manipulation, or a URL-rewriter edge function) — not
# fully API-discoverable. Confirm from S1 (player architecture, CDN account posture).

# Low-latency HLS / CMAF (CDN9): read the latency commitment from S0; if sub-5s is required,
# verify chunked transfer encoding support on the behavior and that MediaPackage endpoints or
# upstream origin publish partial segments / #EXT-X-PART tags. Grade largely from S1.
```

## NET — Networking capacity

```bash
aws ec2 describe-nat-gateways --filter Name=state,Values=available \
  --query "NatGateways[].{id:NatGatewayId,subnet:SubnetId}"
# NAT saturation vs ceilings (pull over the peak/rehearsal window; period 60-300s):
#   PeakPacketsPerSecond  -> leading indicator, ceiling ~10,000,000 pps
#   ActiveConnectionCount -> ~55,000 per unique destination
#   ErrorPortAllocation   -> any non-zero = at a connection ceiling for a destination
#   PacketsDropCount      -> rising + a PeakPacketsPerSecond ramp = clearest pre-warm trigger
#   BytesInFromDestination / BytesOutToDestination -> bandwidth
aws cloudwatch get-metric-statistics --namespace AWS/NATGateway \
  --metric-name PeakPacketsPerSecond --dimensions Name=NatGatewayId,Value=<id> \
  --start-time <peak-window> --end-time <now> --period 300 --statistics Maximum

aws ec2 describe-transit-gateway-attachments \
  --query "TransitGatewayAttachments[].{id:TransitGatewayAttachmentId,type:ResourceType}"
# TGW per-attachment throughput (AWS/TransitGateway, dimension TransitGatewayAttachment):
#   BytesIn / BytesOut -> convert to sustained bits/sec vs ~100 Gbps burst ceiling
#   PacketDropCountNoRoute / PacketDropCountBlackhole -> routing health; a rise
#     correlated with the event window (vs a pre-existing background pattern) = routing review
aws ec2 describe-vpc-endpoints --query "VpcEndpoints[].{id:VpcEndpointId,svc:ServiceName,type:VpcEndpointType}"
```

## DAT — Data & state stores

```bash
# DynamoDB throughput / warm throughput
aws dynamodb describe-table --table-name <t> \
  --query "Table.{mode:BillingModeSummary.BillingMode,prov:ProvisionedThroughput,warm:WarmThroughput}"
# WarmThroughput (ReadUnitsPerSecond/WriteUnitsPerSecond) = what the table can serve
# INSTANTLY, reflecting historical/previously-provisioned peak. Gate DAT1 on warm
# throughput vs projected peak, NOT billing mode: an on-demand table previously
# provisioned high already covers the peak. New on-demand floor = 12,000 RCU / 4,000 WCU.

# Amazon Keyspaces capacity mode + warm throughput (DAT6)
aws keyspaces list-keyspaces --query "keyspaces[].keyspaceName"
aws keyspaces list-tables --keyspace-name <ks> --query "tables[].tableName"
aws keyspaces get-table --keyspace-name <ks> --table-name <t> \
  --query "{status:status,mode:capacitySpecification.throughputMode,prov_read:capacitySpecification.readCapacityUnits,prov_write:capacitySpecification.writeCapacityUnits,warm:warmThroughput}"
# warmThroughput (ReadUnitsPerSecond/WriteUnitsPerSecond) = what the table can serve
# INSTANTLY, reflecting prior on-demand peak or previously-provisioned capacity. Gate
# DAT6 on warm throughput vs projected peak, NOT capacity mode: a PAY_PER_REQUEST table
# previously provisioned high already covers the peak. If warm throughput < peak,
# pre-warm or switch to PROVISIONED sized to peak. Corroborate the historical peak via
# CloudWatch ConsumedRead/WriteCapacityUnits (max over the trailing window).

# ElastiCache sizing + shard layout
aws elasticache describe-replication-groups \
  --query "ReplicationGroups[].{id:ReplicationGroupId,shards:NodeGroups[].NodeGroupId,status:Status}"
aws elasticache describe-serverless-caches
# Serverless pre-scaling check: compare the projected event spike multiplier/window
#   to reactive scaling (incremental, ~minutes). A steep step (e.g. >4x in <5 min)
#   needs a >=60-min pre-warm ahead of the ramp, not live scale-out (DAT2 + the
#   serverless pre-scaling rule in best-practices.md).

# RDS / Aurora -> prefer rds-operation-review
aws rds describe-db-clusters --query "DBClusters[].{id:DBClusterIdentifier,engine:Engine,\
members:DBClusterMembers[].{id:DBInstanceIdentifier,writer:IsClusterWriter}}"
aws rds describe-db-instances --query "DBInstances[].{id:DBInstanceIdentifier,class:DBInstanceClass,\
az:MultiAZ,role:ReadReplicaSourceDBInstanceIdentifier}"

# DRM license-server capacity (DAT7). The license server itself is almost always a
# third-party service (Verimatrix, EZDRM, Irdeto, Axinom) integrated via SPEKE; AWS can
# only read the SPEKE key-provider configuration on the packager side — the capacity
# commitment lives with the vendor. Read what AWS exposes, then confirm the rest from S1.
aws mediapackage list-channels     # classic MediaPackage
aws mediapackage describe-origin-endpoint --id <endpoint-id> \
  --query "{hls:HlsPackage.Encryption.SpekeKeyProvider,dash:DashPackage.Encryption.SpekeKeyProvider,\
cmaf:CmafPackage.Encryption.SpekeKeyProvider}"
aws mediapackagev2 list-channel-groups   # MediaPackage v2
aws mediapackagev2 get-origin-endpoint --channel-group-name <cg> --channel-name <c> --origin-endpoint-name <e> \
  --query "{hls:HlsManifests[].Encryption,dash:DashManifests[].Encryption,low:LowLatencyEncryptionMethod}"
# Grade DAT7 on: (1) SPEKE key provider URL present on event-critical endpoints,
# (2) vendor confirmation of capacity at projected peak license-request rate (S1),
# (3) license-renewal windows staggered so renewals don't cluster mid-event (S1),
# (4) player-side token caching (S1 / app code).

# IVS platforms — grade only the customer-managed portions (see applicability gate).
aws ivs list-channels           # low-latency streaming channels (Amazon IVS)
aws ivs list-recording-configurations
# aws ivs-realtime list-stages  # IVS Real-Time (sub-second) stages, when applicable
```

## TST / OBS / SUP — mostly evidence-based

These are largely verified from S1 context (load-test plans and results, FIS
experiment templates, runbooks, WAFR output, support engagement) rather than
live API reads. Where available, confirm programmatically:

```bash
# FIS experiment templates (chaos readiness)
aws fis list-experiment-templates \
  --query "experimentTemplates[].{id:id,desc:description,stop:stopConditions}"
aws fis list-experiments --query "experiments[].{id:id,state:state.status}"

# Alarm coverage per critical-path service + proven (OBS2 / OBS4). Map each alarm's
# namespace/dimensions back to a critical-path resource from S2; a critical service
# with no actionable alarm is a coverage gap. Check ActionsEnabled + non-empty
# AlarmActions — an alarm that notifies nobody is not coverage.
aws cloudwatch describe-alarms \
  --query "MetricAlarms[].{name:AlarmName,ns:Namespace,metric:MetricName,dim:Dimensions,state:StateValue,actions:AlarmActions,actionsEnabled:ActionsEnabled}"
aws cloudwatch describe-alarms --alarm-types CompositeAlarm \
  --query "CompositeAlarms[].{name:AlarmName,rule:AlarmRule,actions:AlarmActions}"
# THIRD-PARTY (OBS4): Datadog / New Relic / Grafana / Splunk / Dynatrace alarms are
# NOT readable via AWS access. If CloudWatch alarms are sparse/absent, do not infer a
# gap — check S1 context for a declared third-party platform and grade per the OBS4
# third-party rule in best-practices.md (N/A if asserted-but-unverifiable; FAIL only
# if no actionable alarm exists in any tool).

# Telemetry / analytics pipeline headroom (OBS6). If viewer QoE, CMCD, ad-tracking, or
# session heartbeats flow through Kinesis / Firehose / MSK, size the pipeline for the
# projected peak event beacon rate.
aws kinesis list-streams
aws kinesis describe-stream-summary --stream-name <name> \
  --query "StreamDescriptionSummary.{status:StreamStatus,mode:StreamModeDetails.StreamMode,shards:OpenShardCount}"
# For PROVISIONED streams: shard × 1,000 records/s and 1 MB/s write per shard caps throughput;
# for ON_DEMAND: AWS scales shards automatically but with a reactive lag (minutes). Confirm
# WriteProvisionedThroughputExceeded + GetRecords.IteratorAgeMilliseconds are flat under
# the rehearsal (TST1) — a rising IteratorAge during the ramp = consumers falling behind.
aws cloudwatch get-metric-statistics --namespace AWS/Kinesis \
  --metric-name WriteProvisionedThroughputExceeded --dimensions Name=StreamName,Value=<name> \
  --start-time <peak-window> --end-time <now> --period 60 --statistics Sum
aws firehose list-delivery-streams
aws firehose describe-delivery-stream --delivery-stream-name <name> \
  --query "DeliveryStreamDescription.{status:DeliveryStreamStatus,type:DeliveryStreamType,dest:Destinations}"
# For MSK, prefer msk-operations; otherwise:
aws kafka list-clusters-v2 \
  --query "ClusterInfoList[].{name:ClusterName,state:State,type:ClusterType}"
# CloudWatch-only telemetry (metrics/logs direct to CloudWatch, no streaming pipeline) -> OBS6 N/A.

# Live captions / accessibility path (SUP7). AWS can read whether a MediaLive channel
# includes caption outputs, but the vendor-side capacity (Ai-Media, EEG, Enco) and the
# end-to-end player test live in S1 — grade primarily from S1 context.
aws medialive list-channels \
  --query "Channels[].{id:Id,name:Name,state:State,outputs:EncoderSettings.OutputGroups[].Outputs[?CaptionDescriptionNames].{name:OutputName,caps:CaptionDescriptionNames}}"

# Open support cases near the event -> delegate to support-cases
```

Record the absence of load-test / FIS / runbook evidence as an N/A with the
reason "no evidence provided" — not as a PASS.
