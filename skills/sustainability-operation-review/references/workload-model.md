# Workload Model — Topology Layers, Shapes, and Data Sources

Read this file at Step 2. It defines how to classify the topology, how to detect the workload
shape that decides which KPIs apply, and which data sources the review may use.

## Step 2: Discover Workload Topology

Use the topology data available in the Agent Space to enumerate the workload. This is
the capability that makes this skill possible — it produces a workload *boundary*,
which flat inventory tools (Config, Resource Groups, tag queries) do not.

Walk the topology from the entry point and record every resource, its type, Region,
and its relationships. Classify each into a layer:

| Layer | Resource types to capture |
|-------|---------------------------|
| Entry / edge | CloudFront distributions, ALB/NLB, API Gateway, Global Accelerator |
| Compute | EC2 instances, ASGs, ECS services/tasks, EKS nodegroups, Lambda functions, Fargate tasks, Batch queues |
| Storage | EBS volumes, S3 buckets, EFS/FSx file systems, instance store |
| Database | RDS/Aurora, DynamoDB tables, ElastiCache, OpenSearch, Redshift |
| Network | NAT Gateways, VPC endpoints, Transit Gateway attachments, VPC peering, cross-Region links |
| Async / batch | SQS queues, SNS topics, EventBridge rules, Step Functions, scheduled jobs |
| AI / ML | SageMaker endpoints, training and tuning jobs, notebook instances, Studio apps, HyperPod clusters; Bedrock models in use and provisioned throughput; GPU/Inferentia/Trainium instances and nodes |

Record the **Region of every resource** — Region is the single largest customer-controllable
lever on carbon intensity (SUS01-BP01), and cross-Region relationships drive SUS04-BP07.

If topology is unavailable or incomplete for part of the workload, use
`resourcegroupstaggingapi.GetResources` and service-level `Describe*` calls to fill
gaps, and state the coverage limitation in the report.

## Step 3: Determine Workload Shape

The workload shape determines which KPIs are meaningful. Do not apply all KPIs to all
workloads — an unused KPI is noise.

| Shape | Detection signal | Primary KPIs | Key SUS focus |
|-------|------------------|--------------|---------------|
| **Request-response** | Entry point with steady `RequestCount`; long-running compute | vCPU-hours per 1M requests; GB provisioned per 1M requests | SUS02 (scale to demand), SUS03 (utilization) |
| **Batch / scheduled** | EventBridge/Batch/Step Functions triggers; bursty compute; low idle utilization | vCPU-hours per job; job duration vs allocated capacity | SUS03-BP01 (async/scheduled), SUS02-BP06 (flatten demand) |
| **Streaming / event-driven** | Kinesis/MSK/SQS with continuous throughput | vCPU-hours per 1M records; GB transferred per 1M records | SUS02-BP06 (buffering), SUS04-BP07 (data movement) |
| **Storage-heavy** | Storage GB dominates footprint; low compute | GB-months per unit of work, weighted by storage class | SUS04 (data patterns), especially BP03 lifecycle, BP05 redundant data |
| **ML / accelerated** | GPU/Inferentia/Trainium instance families, SageMaker endpoints or jobs, Bedrock token volume | Accelerator-hours per training run / per 1M inferences; tokens per unit of work | SUS05-BP04 (accelerators), SUS02-BP01, SUS03-BP03 |
| **Mixed** | More than one of the above with no dominant pattern | Report per-component KPIs; do not aggregate into one number | All |

State the detected shape and the evidence for it in the report.

**AI/ML trigger.** If the shape is ML / accelerated, or the `AWS/Bedrock` CloudWatch namespace
shows `Invocations` for a workload of any shape, read `references/ai-ml-workloads.md` before
Step 4. It adds the AI/ML inputs, KPIs, and the mapping from the Machine Learning Lens and
Generative AI Lens to the SUS best practices used in Step 7.

## Data Source Boundaries

This skill uses:
- `sustainability:GetEstimatedCarbonEmissions`, `sustainability:GetEstimatedCarbonEmissionsDimensionValues`
- `sustainability:GetEstimatedWaterAllocation`, `sustainability:GetEstimatedWaterAllocationDimensionValues`
- A user-provided carbon or water CSV export (AWS Sustainability console Reports, or a Data
  Exports carbon export), when attached or requested — an alternative to the matching actions
  above for the metric it covers, not an addition to them (Step 5.0)
- Agent Space topology data
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`
- Service `Describe*` / `List*` calls for configuration (ec2, s3, rds, ecs, eks, lambda, elasticloadbalancing, elasticache, dynamodb)
- For AI/ML workloads only: `sagemaker:Describe*` / `List*`, `bedrock:List*` / `Get*`,
  `application-autoscaling:DescribeScalableTargets`, `application-autoscaling:DescribeScalingActivities`,
  `logs:DescribeLogGroups`, `ecr:DescribeRepositories`, `ecr:GetLifecyclePolicy`,
  `scheduler:ListSchedules`, `events:ListRules`, and the `AWS/SageMaker`,
  `/aws/sagemaker/Endpoints`, `/aws/sagemaker/TrainingJobs`, and `AWS/Bedrock` CloudWatch namespaces
- For SUS05-BP02 Graviton eligibility: `rds:DescribeOrderableDBInstanceOptions`,
  `es:ListInstanceTypeDetails`, `elasticmapreduce:ListSupportedInstanceTypes`,
  `lambda:GetLayerVersion`, `ecs:DescribeTaskDefinition`, `eks:DescribeNodegroup`,
  `ec2:DescribeImages`, `ecr:DescribeImages`; optionally `ecr:BatchGetImage` to confirm arm64
  in an image index, and `compute-optimizer:GetEnrollmentStatus`,
  `GetEC2InstanceRecommendations`, `GetAutoScalingGroupRecommendations`,
  `GetRDSDatabaseRecommendations` for migration-effort ratings
- `ce:GetCostAndUsage` — only for the divergence check in Step 6.1, not for recommendations
- `resourcegroupstaggingapi:GetResources` — topology gap-filling

Read-only throughout. This skill never calls `Modify*`, `Delete*`, `Terminate*`, or
`Create*`. Every recommendation is for a human to action.

Explicitly out of scope: individual instance right-sizing, and code-level profiling.
