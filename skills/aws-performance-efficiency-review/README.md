# AWS Performance Efficiency Review

A skill for AWS DevOps Agent that finds where an application spends its time, which resource limits it, and what to change. It follows the request path across dependencies, uses the USE and RED methods to locate the bottleneck, checks right-sizing with AWS Compute Optimizer, and maps every finding to the Performance Efficiency pillar of the AWS Well-Architected Framework.

> **Disclaimer:** This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

## What it does

- Maps the request path from the entry point (load balancer, API Gateway, function URL) to its deepest dependency, using the Agent Space topology, CloudWatch Application Signals and AWS X-Ray, with configuration inference as a fallback.
- Measures p50, p90 and p99 latency, request rate and errors at each hop, and computes each hop's share of end-to-end latency.
- Checks the slowest hop's resources for utilization, saturation and errors: CPU, memory, IOPS, connections, concurrency, throttles, queue age, cache hit ratio.
- Correlates latency changes with deployments, configuration changes and traffic.
- Runs service-specific checks: RDS Performance Insights top waits and SQL, scaling configuration, Lambda concurrency and timeouts, DynamoDB throttling, ElastiCache evictions, NAT gateway port allocation.
- Reads Compute Optimizer recommendations and separates hot-path findings (performance) from off-path findings (cost).
- Produces a report: verdict, request path, bottleneck with evidence, findings mapped to Well-Architected best-practice IDs, ranked recommendations with cost direction and a verification metric, and telemetry gaps.

The skill only reads. It does not change resources, run code, or connect to databases.

## Agent types

- **Chat tasks:** performance reviews, right-sizing questions, "will this scale for the peak".
- **Incident RCA:** investigations where the symptom is latency, timeouts, throttling, backlog or saturation.

If you also want a custom agent to load this skill, select **All agents** as the agent type when you import it.

## Prerequisites

- An AWS DevOps Agent Space with the application's accounts associated.
- For the best results: CloudWatch Application Signals or AWS X-Ray on the services in the request path, RDS Performance Insights or Database Insights on databases, the CloudWatch agent publishing memory on EC2, Container Insights on ECS and EKS, and Compute Optimizer opted in. The skill works without them and reports each missing source as a telemetry gap.

### IAM permissions

The DevOps Agent role needs **read-only** permissions for the review to produce complete results.

#### Required: eight actions to add

`AIDevOpsAgentAccessPolicy` (default version v12) covers every action this skill uses except these eight, which must be added:

```
compute-optimizer:GetEnrollmentStatus
compute-optimizer:GetEC2InstanceRecommendations
compute-optimizer:GetAutoScalingGroupRecommendations
compute-optimizer:GetEBSVolumeRecommendations
compute-optimizer:GetLambdaFunctionRecommendations
compute-optimizer:GetECSServiceRecommendations
compute-optimizer:GetRDSDatabaseRecommendations
lambda:GetFunctionConcurrency
```

Deploy them with the `EnableAwsPerformanceEfficiencyReview` parameter in
[cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml).
**Each Agent Space has its own IAM role, so apply this to the role of every space where the skill is installed.** Use one stack per role:

```bash
aws cloudformation deploy \
  --template-file cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml \
  --stack-name devops-agent-skill-policies-<role-suffix> \
  --parameter-overrides ExistingRoleName=<DevOpsAgentRole-AgentSpace-XXXX> \
      EnableAwsPerformanceEfficiencyReview=true \
  --capabilities CAPABILITY_NAMED_IAM --region <region>
```

Most of the template's other `Enable*` parameters default to `true`. Set the ones you do not want to `false`, or you will also attach the other skills' policies, some of which grant write actions such as `servicequotas:RequestServiceQuotaIncrease`.

**The skill still runs without these eight.** For a denied call it names the missing permission, uses a fallback, and reports the gap. What you lose is the Compute Optimizer right-sizing input and the Lambda reserved-concurrency value.

#### Full action list (reference)

```
cloudwatch:GetMetricData
cloudwatch:ListMetrics
cloudwatch:DescribeAlarms
cloudwatch:GetInsightRuleReport
logs:StartQuery
logs:GetQueryResults
logs:FilterLogEvents
xray:GetServiceGraph
xray:GetTraceSummaries
xray:BatchGetTraces
application-signals:ListServices
application-signals:GetService
application-signals:ListServiceDependencies
application-signals:ListServiceLevelObjectives
application-signals:GetServiceLevelObjective
compute-optimizer:GetEnrollmentStatus
compute-optimizer:GetEC2InstanceRecommendations
compute-optimizer:GetAutoScalingGroupRecommendations
compute-optimizer:GetEBSVolumeRecommendations
compute-optimizer:GetLambdaFunctionRecommendations
compute-optimizer:GetECSServiceRecommendations
compute-optimizer:GetRDSDatabaseRecommendations
pi:GetResourceMetrics
pi:DescribeDimensionKeys
elasticloadbalancing:Describe*
ec2:DescribeInstances
ec2:DescribeInstanceCreditSpecifications
ec2:DescribeVolumes
autoscaling:DescribeAutoScalingGroups
autoscaling:DescribeScalingActivities
autoscaling:DescribePolicies
ecs:DescribeServices
ecs:DescribeTaskDefinition
eks:DescribeCluster
lambda:GetFunctionConfiguration
lambda:GetFunctionConcurrency
lambda:ListEventSourceMappings
lambda:GetEventSourceMapping
lambda:ListProvisionedConcurrencyConfigs
cloudtrail:LookupEvents
rds:DescribeDBInstances
rds:DescribeDBClusters
rds:DescribeDBParameters
rds:DescribeEvents
dynamodb:DescribeTable
elasticache:DescribeReplicationGroups
elasticache:DescribeCacheClusters
sqs:GetQueueAttributes
sqs:ListQueues
servicequotas:GetServiceQuota
servicequotas:ListServiceQuotas
```

Why some of these actions are listed:

- `ec2:DescribeInstanceCreditSpecifications`: burstable-credit checks.
- `logs:StartQuery`, `logs:GetQueryResults`: Logs Insights queries for per-request timings.
- `sqs:GetQueueAttributes`, `sqs:ListQueues`: queue mapping and visibility-timeout checks.
- `cloudwatch:GetInsightRuleReport`: Contributor Insights top-N contributors.
- `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas`: quota checks.
- `autoscaling:DescribeAutoScalingGroups`: also used for the Auto Scaling group-at-maximum check.
- `lambda:ListEventSourceMappings` and `lambda:GetEventSourceMapping`: map a queue or stream to its consuming function in Step 2, and read the mapping's maximum concurrency and batch settings for the effective-concurrency check.
- `lambda:ListProvisionedConcurrencyConfigs`: read provisioned concurrency for the Lambda deep check and the cold-start and masking-fix rules.
- `ec2:DescribeVolumes`: read volume type, size, provisioned IOPS and provisioned throughput for the storage hidden-limits checks (gp2 burst baseline, gp3 provisioned limits).
- `cloudtrail:LookupEvents`: read configuration-change events in the window for the change rule-out (timing, scope, history), and as a fallback source for a configuration value when a describe call fails.

All of them are read-only. If the agent role uses a custom policy instead of `AIDevOpsAgentAccessPolicy`, grant the full list above.

## Example prompts

Chat:

- "Run a performance review of the orders service for the last 14 days."
- "Where does the latency in the inventory API come from?"
- "Are the instances behind the web load balancer right-sized?"
- "Will the payment service handle three times today's peak traffic?"

Investigation:

- "p99 latency on the orders API went above 2 seconds at 14:00 UTC. Find the cause."
- "Requests to the inventory service started timing out after this morning's deployment."

## Files

```
aws-performance-efficiency-review/
├── SKILL.md                               # Workflow the agent follows
├── references/
│   ├── metrics-by-service.md              # Metric names, dimensions, statistics, deep checks per service
│   ├── bottleneck-patterns.md             # Starting thresholds and symptom-to-cause patterns
│   ├── hidden-limits.md                   # Limits that look like headroom (credits, burst, allowances, caps)
│   ├── logs-and-statistics.md             # Logs Insights patterns; baselines, SLOs, async RED, Little's law
│   ├── diagnosis-rules.md                 # Confidence labels, differential, magnitude arithmetic, twins, masking fixes
│   ├── report-and-delegation.md           # Report template, hygiene, sub-agent task text
│   └── well-architected-mapping.md        # PERF01 to PERF05 best-practice IDs and typical findings
├── evals/
│   ├── evals.json                         # Chat, investigation and negative test cases with assertions
│   ├── additional-permissions.json        # Extra read permissions for the functional test spaces
│   ├── structure/                         # skill-eval structure results
│   ├── best-practices/                    # skill-eval best-practices results
│   └── functional/                        # skill-eval functional results (with and without the skill)
├── README.md
└── CHANGELOG.md
```

## References

- [Performance efficiency pillar, AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/performance-efficiency.html)
- [AWS DevOps Agent Skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)
- [AWS Compute Optimizer User Guide](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html)
- [CloudWatch Application Signals](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Monitoring-Sections.html)
- [AWS X-Ray Developer Guide](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)
- [Amazon RDS Performance Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.html)

## Further reading

Public methodology and documentation behind the analysis rules.

Methodology:

- Google SRE book, service level objectives and error budgets: https://sre.google/sre-book/service-level-objectives/
- Google SRE workbook, alerting on SLOs (burn-rate alerting): https://sre.google/workbook/alerting-on-slos/
- Brendan Gregg, the USE method: https://www.brendangregg.com/usemethod.html
- Tom Wilkie, the RED method (monitoring microservices): https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
- Performance efficiency pillar, AWS Well-Architected Framework: https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html

Amazon Builders' Library (overload, retries, health checks, queues, caching):

- Timeouts, retries, and backoff with jitter: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- Using load shedding to avoid overload: https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/
- Avoiding fallback in distributed systems: https://aws.amazon.com/builders-library/avoiding-fallback-in-distributed-systems/
- Implementing health checks: https://aws.amazon.com/builders-library/implementing-health-checks/
- Avoiding insurmountable queue backlogs: https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/
- Caching challenges and strategies: https://aws.amazon.com/builders-library/caching-challenges-and-strategies/

AWS documentation for the metrics and limits the references cite (confirm figures and names here, not from memory):

- CloudWatch statistics definitions (percentiles and trimmed-mean statistics): https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Statistics-definitions.html
- CloudWatch Contributor Insights: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContributorInsights.html
- CloudWatch Metrics Insights: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/query_with_cloudwatch-metrics-insights.html
- CloudWatch Synthetics: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Synthetics_Canaries.html
- CloudWatch RUM: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-RUM.html
- AWS usage metrics: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Usage-Metrics.html
- Service Quotas user guide: https://docs.aws.amazon.com/servicequotas/latest/userguide/intro.html
- Amazon EC2 Auto Scaling group metrics: https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-cloudwatch-monitoring.html
- Lambda function memory configuration (memory sets CPU share; 1,769 MB is one vCPU): https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html
- Lambda function metrics (`Duration` does not include cold start time): https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html
