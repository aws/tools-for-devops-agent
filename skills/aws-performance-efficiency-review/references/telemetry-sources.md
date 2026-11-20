# Telemetry sources and how to report a gap

Every source on the request path that the review could not read is a telemetry gap, whether the capability is off, the call was denied, or the namespace returned no data. The Telemetry gaps section of the report lists one row per gap with these columns: Capability to enable; What the review could then measure (a concrete metric or dimension, not "better visibility"); Cost direction (adds cost, neutral, or included) with the pricing page link and never a price; Change needed (the enable step for the customer and the read permission for the agent). Each gap also carries a PERF ID from `well-architected-mapping.md` so it can be a Finding.

Rank gaps by how much of the open question they would close: a gap on the suspect hop first, then gaps on other path members, then account-wide tooling. Do not recommend a capability the path does not use (no Lambda Insights without a Lambda hop).

Cost direction words: **included** means the capability has no charge of its own; **adds cost** means it bills by ingested metrics, logs, traces or observations; **neutral** means an existing charge moves rather than grows. Always link the pricing page: CloudWatch https://aws.amazon.com/cloudwatch/pricing/, X-Ray https://aws.amazon.com/xray/pricing/, Lambda https://aws.amazon.com/lambda/pricing/, Bedrock https://aws.amazon.com/bedrock/pricing/, Compute Optimizer https://aws.amazon.com/compute-optimizer/pricing/, Support plans https://aws.amazon.com/premiumsupport/plans/, CloudWatch Omni https://aws.amazon.com/cloudwatch/omni/pricing/.

## Request path

- **CloudWatch Application Signals.**
  - Measures: per service and operation `Latency` (p50, p90, p99), `Fault`, `Error` in namespace `ApplicationSignals`, per-dependency latency, SLO attainment.
  - Off when: `application-signals.ListServices` returns no service for the account and Region in the window.
  - Benefit: Step 2 path mapping and Step 3 RED per hop without inference from configuration; SLOs give the target for Step 1.
  - Cost: adds cost (Application Signals requests and spans, CloudWatch pricing).
  - Enable: instrument with the CloudWatch agent or ADOT and turn on Application Signals in the account; read with `application-signals:ListServices`, `GetService`, `ListServiceDependencies`, `ListServiceLevelObjectives`, `GetServiceLevelObjective` and `cloudwatch:GetMetricData` (in the managed policy).
  - PERF ID: PERF05-BP02
- **AWS X-Ray.**
  - Measures: service graph with per-edge latency histograms and error rates, trace samples with subsegment timings.
  - Off when: `xray.GetServiceGraph` returns no nodes for the window.
  - Benefit: confirms which hop holds the time inside a request and whether a cache, database or external call is on the path (the cache rule in `diagnosis-rules.md` needs it).
  - Cost: adds cost (traces recorded and retrieved, X-Ray pricing).
  - Enable: X-Ray SDK or ADOT in the service, active tracing on Lambda and API Gateway; read with `xray:GetServiceGraph`, `GetTraceSummaries`, `BatchGetTraces`.
  - PERF ID: PERF05-BP02
- **CloudWatch Network Monitoring performance monitors.**
  - Measures: per-path latency, a network impact score and traffic volume for the paths a VPC's flows take, within and across Availability Zones, across Regions and to AWS services, with no agent.
  - Off when: no performance monitor exists for the VPC (list them with the Network Monitoring console or API; verify the metric namespace in the documentation before querying).
  - Benefit: rules the AWS network path in or out before blaming the application on a cross-AZ or cross-Region hop.
  - Cost: adds cost (CloudWatch pricing, Network Monitoring section).
  - Enable: create a performance monitor for the VPC; read with `cloudwatch:GetMetricData`.
  - Doc: https://aws.amazon.com/about-aws/whats-new/2026/11/cloudwatch-network-path-monitoring/
  - PERF ID: PERF04-BP07

## Compute

- **CloudWatch agent memory and disk on EC2.**
  - Measures: `mem_used_percent`, `disk_used_percent`, swap and per-process metrics in namespace `CWAgent`.
  - Off when: `cloudwatch.ListMetrics` for `CWAgent` with the `InstanceId` returns nothing.
  - Benefit: memory saturation becomes measurable; Compute Optimizer EC2 recommendations then include memory instead of CPU and network only.
  - Cost: adds cost (custom metrics, CloudWatch pricing).
  - Enable: install and configure the CloudWatch agent on the instances; read with `cloudwatch:GetMetricData`.
  - PERF ID: PERF02-BP03
- **Container Insights (ECS, EKS) and enhanced observability or OTel Container Insights (EKS).**
  - Measures: task, pod, node and container CPU, memory, network, restarts and desired versus running counts (`ECS/ContainerInsights`, `ContainerInsights`; OTel Container Insights adds Kubernetes labels and PromQL).
  - Off when: those namespaces return no data for the cluster.
  - Benefit: container-level USE instead of service averages; a single degraded task or pod becomes visible (Step 4.2).
  - Cost: adds cost (per metric or per observation, CloudWatch pricing).
  - Enable: cluster setting `containerInsights` on ECS, the `amazon-cloudwatch-observability` add-on on EKS; read with `cloudwatch:GetMetricData`, `logs:StartQuery`.
  - Doc: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html
  - PERF ID: PERF02-BP03
- **Lambda Insights.**
  - Measures: `cpu_total_time`, `init_duration`, `memory_utilization`, `used_memory_max`, `total_memory`, `rx_bytes`, `tx_bytes`, `tmp_used` in namespace `LambdaInsights` (dimension `function_name`), plus per-invocation embedded metric records.
  - Off when: `LambdaInsights` returns no data for the function.
  - Benefit: CPU time per invocation separates CPU-bound from wait-bound work for the memory-sets-CPU rule; `init_duration` quantifies cold starts without parsing `REPORT` lines.
  - Cost: adds cost (metrics and logs, CloudWatch pricing; the extension's execution time, Lambda pricing).
  - Enable: attach the Lambda Insights extension layer to the function; read with `cloudwatch:GetMetricData` and `logs:StartQuery`.
  - Doc: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights.html
  - PERF ID: PERF02-BP03
- **AWS Compute Optimizer.**
  - Measures: right-sizing findings and options for EC2, Auto Scaling groups, EBS, Lambda, ECS on Fargate, RDS and Aurora, with projected utilization.
  - Off when: `compute-optimizer.GetEnrollmentStatus` is not `Active`, or a recommendation call returns `OptInRequiredException`.
  - Benefit: Step 6 with 14 days of history and a performance-risk rating per option.
  - Cost: included; enhanced infrastructure metrics (longer history) adds cost (Compute Optimizer pricing).
  - Enable: opt in from the console or `compute-optimizer:UpdateEnrollmentStatus`; read with the seven `compute-optimizer:Get*` actions in the skill's add-on policy.
  - PERF ID: PERF02-BP04
- **AWS Trusted Advisor (performance pillar).**
  - Measures: account-level checks that flag over-used or under-used resources and configuration that hurts throughput.
  - Off when: `trustedadvisor:ListRecommendations` returns AccessDenied or a support-plan error.
  - Benefit: a second, independent list of suspects to confirm with the workload's own metrics (Step 5).
  - Cost: requires a Business Support+, Enterprise Support or Unified Operations plan (existing Business Support and Enterprise On-Ramp plans keep access until they end on 2027-01-01; see the Support plans page); no charge per call.
  - Enable: the support plan; read with `trustedadvisor:ListChecks`, `ListRecommendations`, `GetRecommendation`, `ListRecommendationResources` (the skill's add-on policy).
  - PERF ID: PERF01-BP02

## Data stores and caches

- **CloudWatch Database Insights (Standard and Advanced) for RDS and Aurora.**
  - Measures: database load by wait event and by tokenized SQL through `pi.GetResourceMetrics` and `pi.DescribeDimensionKeys`; Advanced mode adds per-query statistics, lock and execution-plan analysis, slow-query analysis with log export, and calling services from Application Signals (the rename from Performance Insights is explained in `metrics-by-service.md`).
  - Off when: `pi.GetResourceMetrics` returns `NotAuthorizedException` or no data for the instance.
  - Benefit: the top statement behind `DBLoad`, which is the only way to label a database cause Confirmed.
  - Cost: Standard mode is included up to 7 days of retention and adds cost beyond; Advanced mode adds cost (CloudWatch pricing, Database Insights section).
  - Enable: `DatabaseInsightsMode` on the instance or cluster; read with `pi:GetResourceMetrics`, `pi:DescribeDimensionKeys` (in the managed policy).
  - Doc: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights.html
  - PERF ID: PERF03-BP03
- **ElastiCache Insights and ElastiCache OpenTelemetry metrics (node-based Valkey).**
  - Measures: per-node engine and host metrics queried with PromQL, such as `valkey.memory.used`, `valkey.memory.max`, `valkey.commands.processed`, `valkey.command.calls` and `valkey.command.duration` by command, `process.cpu.time` for the main thread, `system.network.io` and the `system.network.io.rate` histogram.
  - Off when: the replication group is Redis OSS, Memcached or serverless (no OTel metrics), or a PromQL query returns no series.
  - Benefit: per-command latency and per-shard rates that the `AWS/ElastiCache` aggregates hide; one-second network bursts from the histogram.
  - Cost: the vended set at 60 seconds is included; detailed 15-second metrics and PromQL queries through the API add cost (CloudWatch pricing).
  - Enable: nothing for vended metrics; a resource metrics configuration for detailed ones; read through CloudWatch PromQL queries.
  - Doc: https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/otel-metrics.html
  - PERF ID: PERF03-BP03
- **CloudWatch Contributor Insights.**
  - Measures: top-N contributors (hottest key, noisiest caller, slowest host) from log groups or DynamoDB tables.
  - Off when: `cloudwatch.DescribeInsightRules` lists no rule for the resource.
  - Benefit: identifies the hot partition key behind DynamoDB throttles and the caller behind a retry storm.
  - Cost: adds cost (per rule and matched log events, CloudWatch pricing).
  - Enable: create a rule, or `UpdateContributorInsights` on the table; read with `cloudwatch:GetInsightRuleReport`.
  - PERF ID: PERF05-BP02

## AI and ML

- **Amazon Bedrock model invocation logging and `AWS/Bedrock` metrics.**
  - Measures: the `AWS/Bedrock` metrics listed in `metrics-by-service.md` are published without enabling anything; invocation logging adds per-request logs with input and output token counts, latency and the full request and response to CloudWatch Logs or S3.
  - Off when: `bedrock.GetModelInvocationLoggingConfiguration` returns no configuration.
  - Benefit: per-request token counts and model identifiers to compute output tokens per second per caller and to split quota use by application.
  - Cost: metrics included; logging adds cost (CloudWatch Logs or S3 pricing).
  - Enable: `bedrock:PutModelInvocationLoggingConfiguration` with a destination in the same account and Region; read with `logs:StartQuery` and `cloudwatch:GetMetricData`.
  - Doc: https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html
  - PERF ID: PERF05-BP02
- **SageMaker AI Insights and inference component metrics.**
  - Measures: the CloudWatch dashboard (Performance, Capacity, Reliability) built on SageMaker detailed observability and OpenTelemetry metrics; `/aws/sagemaker/InferenceComponents` publishes `CPUUtilizationNormalized`, `MemoryUtilizationNormalized`, `GPUUtilizationNormalized`, `GPUMemoryUtilizationNormalized`.
  - Off when: no series in `/aws/sagemaker/InferenceComponents` (endpoint has no inference components) or no OTel series for the endpoint.
  - Benefit: separates a GPU-bound model from a CPU-bound pre-processing step; capacity per instance for the invocations-per-instance check.
  - Cost: adds cost (OTel metrics, CloudWatch pricing).
  - Enable: inference component metrics need nothing (`EnableEnhancedMetrics` for per-container and per-GPU dimensions); SageMaker AI Insights needs `EnableDetailedObservability` on the endpoint configuration and OTel enrichment in the account. Read with `cloudwatch:GetMetricData`.
  - Doc: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/SageMaker-Insights.html
  - PERF ID: PERF02-BP03
- **Accelerated Compute Insights (NVIDIA GPUs on EKS).**
  - Measures: DCGM metrics (`DCGM_FI_DEV_GPU_UTIL`, framebuffer memory, temperature, power, `DCGM_FI_PROF_*` profiling) resolved to the pod and container that used the accelerator, stored as CloudWatch OpenTelemetry metrics and queried with PromQL; inference workloads are detected from engine metrics such as `vllm:num_requests_running`.
  - Off when: the `amazon-cloudwatch-observability` add-on is below v7.0.0 or OTel Container Insights is not enabled (no DCGM series).
  - Benefit: GPU utilization and memory per inference pod for the USE reading of a GPU hop.
  - Cost: no charge for the feature; adds cost for the OTel metrics ingested (CloudWatch pricing).
  - Enable: the add-on with OTel Container Insights; read through CloudWatch PromQL queries.
  - Doc: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Accelerated-Compute-Insights.html
  - PERF ID: PERF02-BP06
- **Amazon Bedrock AgentCore observability.**
  - Measures: runtime metrics in namespace `AWS/Bedrock-AgentCore` (invocations, throttles, system and user errors, `Latency` to the last token, `OverheadLatency` for the platform share, `SessionCount`, `ActiveSessionCount`), vended CPU and memory usage, and `InvokeAgentRuntime` spans with `latency_ms` and `error_type` once observability is enabled on the agent.
  - Off when: the metrics exist but spans are absent from the agent's log group, or CloudWatch Transaction Search is not enabled (a one-time setup the spans require).
  - Benefit: splits agent latency into platform overhead and the agent's own processing; spans show which tool or model call holds the time.
  - Cost: metrics included; spans and logs add cost (CloudWatch pricing).
  - Enable: observability on the agent runtime and Transaction Search; read with `cloudwatch:GetMetricData`, `logs:StartQuery`, `xray:GetTraceSummaries`.
  - Doc: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-runtime-metrics.html
  - PERF ID: PERF05-BP02

## Investigation experiences (not telemetry)

**CloudWatch investigations** and **Amazon CloudWatch Omni** (including its AI Inference Insights for vLLM on ECS and EKS) are investigation experiences that reason over telemetry the account already has; they add no metric, log or trace of their own. AWS DevOps Agent already fills that role for this review. List one of them as a gap only when the customer has no investigation workflow at all, rank it last, and never present it as the fix for a missing source. Cost: see the CloudWatch pricing page for investigations and the CloudWatch Omni pricing page for Omni; state the direction as adds cost. Docs: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Investigations.html, https://aws.amazon.com/cloudwatch/omni/, https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/omni-ai-inference-insights.html. PERF05-BP03.
