# Well-Architected Sustainability Pillar — Assessment Checklist

All 29 best practices across the six focus areas, with the evidence the agent should
collect for each and the severity rule to apply.

Status values: **MET** / **PARTIAL** / **NOT MET** / **N/A** / **NEEDS HUMAN INPUT**

Never mark a practice MET without evidence. If the agent cannot obtain evidence, the
status is NEEDS HUMAN INPUT, not MET.

Reference: [Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)

---

## SUS01 — Region Selection (1 best practice)

[SUS 1: How do you select Regions for your workload?](https://docs.aws.amazon.com/wellarchitected/latest/framework/a-region-selection.html)

### SUS01-BP01 — Choose Region based on both business requirements and sustainability goals

| | |
|---|---|
| **Evidence** | Region of every resource (Step 2 topology). Per-Region MTCO2e from `GetEstimatedCarbonEmissions` grouped by `REGION`. Per-Region resource footprint from Step 4. Derived per-Region emissions intensity = MTCO2e ÷ footprint. |
| **NOT MET** | Workload runs in a Region with materially higher emissions intensity than an alternative that satisfies all stated constraints. |
| **PARTIAL** | Some components could move; others are constrained. |
| **Severity** | MEDIUM |
| **Guard** | Do NOT recommend a Region change without first confirming data residency, sovereignty, latency, and service-availability constraints. If these are unknown, status is NEEDS HUMAN INPUT — state the opportunity and the questions that must be answered first. |

Regions AWS reports as powered by more renewable energy change over time; check
[AWS sustainability by Region](https://sustainability.aboutamazon.com/products-services/aws-cloud)
rather than relying on a cached list.

---

## SUS02 — Alignment to Demand (6 best practices)

[SUS 2: How do you align cloud resources to your demand?](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-02.html)

### SUS02-BP01 — Scale workload infrastructure dynamically

| | |
|---|---|
| **Evidence** | `autoscaling.DescribeAutoScalingGroups` (min/max/desired, policies), `application-autoscaling.DescribeScalableTargets`, ECS service desired vs running count, EKS Cluster Autoscaler / Karpenter presence, Lambda concurrency config, Aurora Serverless v2 ACU range. Utilization gap from Step 4.1. |
| **NOT MET** | Fixed-capacity compute (no scaling policy, or min = max) with a >40% provisioned-vs-utilized gap. |
| **PARTIAL** | Scaling configured but bounds too wide/narrow to track demand, or scaling on the wrong metric. |
| **Severity** | HIGH if gap > 40%; MEDIUM if 20–40% |

### SUS02-BP02 — Align SLAs with sustainability goals

| | |
|---|---|
| **Evidence** | Multi-AZ flags, replica counts, cross-Region DR resources, `Environment` tags. Compare redundancy level against the tier the tag implies. |
| **NOT MET** | Production-grade redundancy on resources tagged dev/test/staging, or multi-Region DR on a non-critical tier. |
| **Severity** | MEDIUM |
| **Guard** | Redundancy is a reliability decision. Flag the mismatch and the resource cost; do not recommend removing redundancy from anything that might be production. If `Environment` tags are absent, status is NEEDS HUMAN INPUT. |

### SUS02-BP03 — Stop the creation and maintenance of unused assets

| | |
|---|---|
| **Evidence** | Unattached EBS volumes (`ec2.DescribeVolumes` state=available), unassociated Elastic IPs, load balancers with zero `RequestCount` over 30 days, ASGs with desired=0, EBS snapshots with no source volume, stopped EC2 instances (still billing storage), unused AMIs, empty S3 buckets, idle NAT Gateways (`BytesOutToDestination` ≈ 0). |
| **NOT MET** | Any unused asset found. |
| **Severity** | HIGH — this is unambiguous waste with a trivial remediation path |

### SUS02-BP04 — Optimize geographic placement of workloads based on networking requirements

| | |
|---|---|
| **Evidence** | CloudFront distribution presence and cache hit ratio, Global Accelerator, `BytesDownloaded` by edge location vs origin Region, origin Region vs user geography if known. |
| **NOT MET** | Significant internet egress served directly from a distant origin with no edge caching, or low cache hit ratio on cacheable content. |
| **Severity** | MEDIUM |

### SUS02-BP05 — Optimize team member resources for activities performed

| | |
|---|---|
| **Evidence** | Not visible to the agent (concerns end-user devices and workstations). WorkSpaces / AppStream fleets in the account are partial evidence — check for idle or oversized fleets. |
| **Status** | NEEDS HUMAN INPUT, unless WorkSpaces/AppStream are present and idle |
| **Severity** | INFO, or MEDIUM if idle virtual desktop fleets found |

### SUS02-BP06 — Implement buffering or throttling to flatten the demand curve

| | |
|---|---|
| **Evidence** | SQS/SNS/Kinesis/EventBridge presence relative to the compute path. `RequestCount` or `Invocations` variance over 30 days (peak ÷ mean). API Gateway throttling and usage plans. Scaling headroom maintained for peaks. |
| **NOT MET** | Peak-to-mean ratio > 3 handled entirely by provisioned scaling headroom, with no queue or throttle in the path. |
| **Severity** | MEDIUM |

---

## SUS03 — Software and Architecture Patterns (5 best practices)

[SUS 3: How do you take advantage of software and architecture patterns?](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-03.html)

### SUS03-BP01 — Optimize software and architecture for asynchronous and scheduled jobs

| | |
|---|---|
| **Evidence** | Synchronous request paths and their `TargetResponseTime` / `Duration`; presence of queues, Step Functions, Batch; EventBridge schedule expressions and their timing relative to the workload's demand trough. |
| **NOT MET** | Long-running synchronous work that could be queued, or scheduled jobs running during peak demand when they could run in the trough. |
| **Severity** | MEDIUM |

### SUS03-BP02 — Remove or refactor workload components with low or no use

| | |
|---|---|
| **Evidence** | Per-resource utilization over 30 days: EC2 `CPUUtilization` + `NetworkIn`/`Out`, Lambda `Invocations`, ELB target group `RequestCount`, RDS `DatabaseConnections`, DynamoDB `ConsumedReadCapacityUnits`/`ConsumedWriteCapacityUnits`, ECS service task activity. |
| **NOT MET** | Any resource at < 5% utilization, or with zero traffic, over the full 30-day window. |
| **PARTIAL** | Resources at 5–20% utilization — consolidation candidates rather than removal candidates. |
| **Severity** | HIGH for zero/near-zero use; MEDIUM for consolidation candidates |
| **Guard** | Low utilization does not always mean removable — DR standby, seasonal, and compliance-retained resources are legitimately idle. Report as candidates requiring owner confirmation. |

### SUS03-BP03 — Optimize areas of code that consume the most time or resources

| | |
|---|---|
| **Evidence** | Rank workload components by derived vCPU-hours from Step 4.1. Lambda `Duration` p99 vs allocated memory. RDS Performance Insights top SQL if enabled. |
| **NOT MET** | Not directly assessable — the agent cannot profile code. |
| **Status** | INFO with the ranked component list, or MEDIUM if one component consumes a disproportionate share (> 50% of workload vCPU-hours) and warrants investigation. |
| **Guard** | Do not attempt code-level recommendations. Name where to look. |

### SUS03-BP04 — Optimize impact on customer devices and equipment

| | |
|---|---|
| **Evidence** | Not visible to the agent. Partial signals: CloudFront compression enabled, image/asset transformation at the edge, response payload sizes. |
| **Status** | NEEDS HUMAN INPUT |
| **Severity** | INFO, or LOW if CloudFront compression is off for compressible content |

### SUS03-BP05 — Use software patterns and architectures that best support data access and storage patterns

| | |
|---|---|
| **Evidence** | Storage type vs access pattern: EBS read/write IOPS ratio and throughput, S3 `GetRequests` vs `PutRequests` per bucket, DynamoDB vs RDS for key-value access, ElastiCache presence relative to repeated read patterns, RDS `BufferCacheHitRatio`. |
| **NOT MET** | Clear mismatch — e.g. provisioned block storage for append-only/write-once data, relational database for pure key-value access, no caching layer in front of a repeated-read path. |
| **Severity** | MEDIUM |

---

## SUS04 — Data Patterns (8 best practices)

[SUS 4: How do you take advantage of data management policies and patterns?](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-04.html)

### SUS04-BP01 — Implement a data classification policy

| | |
|---|---|
| **Evidence** | Tags on storage resources indicating classification, retention, or data owner. Macie presence. |
| **NOT MET** | No classification/retention tagging on storage resources. |
| **Severity** | LOW — governance gap; it blocks the other SUS04 practices from being automated |

### SUS04-BP02 — Use technologies that support data access and storage patterns

| | |
|---|---|
| **Evidence** | EBS volume types (`gp2` vs `gp3`, `io1` vs `io2`), S3 storage class distribution per bucket via CloudWatch `BucketSizeBytes` with `StorageType` dimension, EFS throughput/performance mode, Intelligent-Tiering enabled. |
| **NOT MET** | `gp2` volumes present (gp3 is more efficient at equal or better performance); S3 Standard holding data with a cold access pattern and no Intelligent-Tiering. |
| **Severity** | MEDIUM |

### SUS04-BP03 — Use policies to manage the lifecycle of your datasets

| | |
|---|---|
| **Evidence** | `s3.GetBucketLifecycleConfiguration` per bucket, CloudWatch Logs log group `retentionInDays`, EBS snapshot lifecycle (DLM) policies, RDS backup retention. |
| **NOT MET** | Buckets with no lifecycle configuration; log groups with `retentionInDays` unset (never expire); no snapshot lifecycle policy. |
| **Severity** | HIGH — typically the largest single storage finding, and cheap to remediate |

Log groups with infinite retention are extremely common and rarely intentional. Check
every log group in the workload.

### SUS04-BP04 — Use elasticity and automation to expand block storage or file system

| | |
|---|---|
| **Evidence** | EBS volume size vs used space (needs CloudWatch agent `disk_used_percent`, else note the gap), RDS `MaxAllocatedStorage` (storage autoscaling), EFS elastic throughput mode. |
| **NOT MET** | Statically oversized volumes, or RDS without storage autoscaling. |
| **Severity** | MEDIUM |
| **Note** | Without the CloudWatch agent, in-volume utilization is invisible. State this limitation rather than assuming volumes are right-sized. |

### SUS04-BP05 — Remove unneeded or redundant data

| | |
|---|---|
| **Evidence** | S3 versioning enabled without a noncurrent-version expiry rule, `NumberOfObjects` growth vs `BucketSizeBytes`, duplicate datasets across buckets/Regions, snapshot counts and ages, incomplete multipart uploads. |
| **NOT MET** | Versioning with no expiry, snapshot sprawl, or identifiable duplicate datasets. |
| **Severity** | HIGH |

Versioning without an expiry rule grows unboundedly and is invisible in the object count.

### SUS04-BP06 — Use shared file systems or storage to access common data

| | |
|---|---|
| **Evidence** | Per-instance EBS volumes holding what appears to be identical reference data (same size, same mount pattern across an ASG); absence of EFS/FSx/S3 shared read path. |
| **NOT MET** | Replicated copies of common data across instances. |
| **Severity** | MEDIUM |

### SUS04-BP07 — Minimize data movement across networks

| | |
|---|---|
| **Evidence** | S3 Cross-Region Replication rules, DynamoDB global tables, cross-Region RDS replicas, cross-AZ traffic from VPC Flow Logs or ELB metrics, NAT Gateway `BytesOutToDestination` vs available VPC endpoints, Transit Gateway `BytesIn`/`BytesOut`. |
| **NOT MET** | Cross-Region replication not required by residency or DR policy; substantial NAT Gateway traffic to AWS services that have a VPC endpoint; chatty cross-AZ traffic between tightly coupled components. |
| **Severity** | HIGH |

NAT Gateway traffic to S3/DynamoDB is the clearest case — a gateway VPC endpoint keeps
it on the AWS network at no cost. It's both a carbon and cost win, so it will show up in
cost tooling too; report it anyway.

### SUS04-BP08 — Back up data only when difficult to recreate

| | |
|---|---|
| **Evidence** | AWS Backup plans, RDS backup retention, snapshot schedules, and what they target. Identify backups of derived/reproducible data (caches, indexes, rebuild-able artifacts, log archives). |
| **NOT MET** | Backups of reproducible data, or retention far exceeding any stated policy. |
| **Severity** | MEDIUM |
| **Guard** | Never recommend reducing backups without the owner confirming the data is genuinely reproducible and that no compliance retention applies. |

---

## SUS05 — Hardware and Services (4 best practices)

[SUS 5: How do you select and use cloud hardware and services?](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-05.html)

### SUS05-BP01 — Use the minimum amount of hardware to meet your needs

| | |
|---|---|
| **Evidence** | The provisioned-vs-utilized vCPU-hour gap from Step 4.1, at fleet level. Memory utilization if the CloudWatch agent is present. |
| **NOT MET** | Gap > 50%. |
| **PARTIAL** | Gap 30–50%. |
| **Severity** | HIGH if > 50%; MEDIUM if 30–50% |
| **Guard** | Report at fleet/workload level. Refer per-instance sizing to [AWS Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html) — that is not this skill's job. |

### SUS05-BP02 — Use instance types with the least impact

| | |
|---|---|
| **Evidence** | Architecture and generation of every compute resource and managed instance class. Graviton eligibility per service from `references/graviton-migration.md`: engine version via `rds:DescribeOrderableDBInstanceOptions` and the ElastiCache, OpenSearch, and MSK minimums; Lambda `Architectures`, runtime, and layer `CompatibleArchitectures`; ECS `runtimePlatform`; EKS `amiType`; ECR image index; Compute Optimizer `migrationEffort` when opted in. Previous-generation families (t2, m4, c4, r4, m5, c5, r5 where a newer generation exists). |
| **NOT MET** | Eligible x86 resources exist and none of the workload runs on Graviton (the Pillar's anti-pattern "You are only using x86 instances"); previous-generation families in use. |
| **PARTIAL** | Some compute runs on Graviton, but eligible x86 resources remain. |
| **N/A** | Every x86 resource has no Graviton option (Windows, SQL Server, Oracle, Db2). |
| **Severity** | MEDIUM for quick wins (managed instance class change, Lambda `.zip`, confirmed multi-architecture images, Compute Optimizer `VeryLow`/`Low`) and previous-generation families. LOW for build changes and resources needing assessment. |
| **Metric** | Graviton share, Graviton-eligible x86 share, and current-generation share of vCPU-hours, reported separately |
| **Guard** | Quote AWS's Graviton energy statement attributed to AWS; never estimate a CO2e or percentage emissions saving, and never predict a change in the reported figure. Express impact as vCPU-hours/month moved to Graviton. A resource with no Graviton option is N/A, not NOT MET. |

### SUS05-BP03 — Use managed services

| | |
|---|---|
| **Evidence** | Self-managed software on EC2 that has a managed equivalent: Kafka (→ MSK), PostgreSQL/MySQL (→ RDS/Aurora), Redis (→ ElastiCache), Elasticsearch (→ OpenSearch), Airflow (→ MWAA), Prometheus/Grafana (→ AMP/AMG), container orchestration (→ ECS/EKS). Infer from instance tags, names, AMI names, and open ports. |
| **NOT MET** | Self-managed equivalent found running at low utilization. |
| **Severity** | MEDIUM |
| **Rationale** | Managed services run on shared infrastructure at higher aggregate utilization than a dedicated per-customer fleet, so the same work consumes less hardware overall. |
| **Metric** | Report the managed service ratio |

### SUS05-BP04 — Optimize your use of hardware-based compute accelerators

| | |
|---|---|
| **Evidence** | GPU instance families (p3/p4/p5, g4/g5/g6), Inferentia (inf1/inf2), Trainium (trn1/trn2), SageMaker endpoint instance types and `Invocations`. GPU utilization requires the CloudWatch agent with the NVIDIA plugin — note if unavailable. |
| **NOT MET** | GPU instances at low utilization; always-on inference endpoints with sparse traffic; x86/GPU inference where Inferentia or Graviton would serve the workload. |
| **N/A** | No accelerators in the workload. |
| **Severity** | HIGH for idle accelerators (highest per-hour footprint of any instance class); MEDIUM for suboptimal accelerator choice |

---

## SUS06 — Development and Deployment (5 best practices)

[SUS 6: How do your organizational processes support your sustainability goals?](https://docs.aws.amazon.com/wellarchitected/latest/framework/sus-06.html)

### SUS06-BP01 — Communicate and cascade your sustainability goals

| | |
|---|---|
| **Evidence** | Whether a business output metric and intensity KPIs exist for this workload (the Step 1 outcome). CloudWatch dashboards or custom metrics tracking efficiency. |
| **NOT MET** | No sustainability KPI defined for the workload. |
| **Severity** | MEDIUM — but promote to the **top recommendation** if Step 1 could not establish a business output metric, because without a denominator nothing else in this report is trackable over time. |

### SUS06-BP02 — Adopt methods that can rapidly introduce sustainability improvements

| | |
|---|---|
| **Evidence** | CloudFormation stacks / CDK / Terraform state covering the workload's resources, CodePipeline / CodeBuild presence, proportion of resources under IaC. |
| **NOT MET** | Workload not managed by IaC, or no deployment pipeline — efficiency changes then require manual work and won't happen. |
| **Severity** | LOW |

### SUS06-BP03 — Keep your workload up-to-date

| | |
|---|---|
| **Evidence** | AMI creation dates and whether newer versions exist, Lambda runtime deprecation status, RDS/ElastiCache/OpenSearch/EKS engine versions vs latest available, container base image ages. |
| **NOT MET** | EOL or deprecated runtimes/engines; AMIs substantially behind. |
| **Severity** | MEDIUM — newer versions are generally more efficient per unit of work, and EOL versions also carry security risk |

### SUS06-BP04 — Increase utilization of build environments

| | |
|---|---|
| **Evidence** | CodeBuild project usage patterns, self-hosted CI runners on EC2 and their utilization, non-production resources (tagged dev/test/staging) running outside business hours, Instance Scheduler presence. |
| **NOT MET** | Always-on build fleets or non-production environments running 168 h/week when they're used ~50. |
| **Severity** | HIGH |
| **Note** | Usually the fastest available win — a dev environment on a business-hours schedule cuts its running hours, and so its provisioned vCPU-hours, by roughly 70% with no architecture change and no production risk. |

### SUS06-BP05 — Use managed device farms for testing

| | |
|---|---|
| **Evidence** | AWS Device Farm usage; self-managed test device fleets are not visible to the agent. |
| **Status** | NEEDS HUMAN INPUT |
| **Severity** | INFO |

---

## Scoring Summary

| Focus Area | Best Practices | Agent-assessable | Needs human input |
|------------|----------------|------------------|-------------------|
| SUS01 Region Selection | 1 | 1 (with constraint caveats) | 0 |
| SUS02 Alignment to Demand | 6 | 5 | 1 (BP05) |
| SUS03 Software & Architecture | 5 | 3 | 2 (BP03 partial, BP04) |
| SUS04 Data Patterns | 8 | 8 | 0 |
| SUS05 Hardware & Services | 4 | 4 | 0 |
| SUS06 Development & Deployment | 5 | 4 | 1 (BP05) |
| **Total** | **29** | **~25** | **~4** |

Report the "needs human input" practices explicitly rather than silently omitting them.
A scorecard that appears to cover 29 of 29 when 4 were never assessable is misleading.
