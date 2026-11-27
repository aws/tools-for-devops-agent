# Changelog

## [1.0.0] - 2026-11-03

### Fixed

- Well-Architected PERF best-practice IDs now follow the current Framework pages (PERF01 validate requirements, PERF05 monitor, test and improve, PERF02 renumbered); the retired pillar whitepaper numbering is gone from the mapping and every citation.
- EBS volume deep dives are handed off to the `storage-ebs-operations` skill, the same way AI and ML hops are handed off.

### Added

- Initial release: a cross-service performance review for AWS workloads, aligned with the Performance Efficiency pillar of the AWS Well-Architected Framework, for DevOps Agent Chat tasks and Incident RCA.
- Chat intake: at most three questions (performance target, expected peak or growth, constraints) before investigating, never asked during an investigation; answers are used to size recommendations with explicit arithmetic.
- Request-path mapping from the Agent Space topology, CloudWatch Application Signals and AWS X-Ray, with configuration inference as a fallback, including asynchronous paths (queues, streams, schedules, batch).
- RED measurement per hop and USE saturation checks, with percentiles, matched baselines and re-baselining when rate or configuration changed inside the window.
- Differential diagnosis: competing explanations ruled in or out by timing, scope, history and magnitude, with worked magnitude checks (served rate under a concurrency cap, effective concurrency, work amplification, Lambda memory and CPU, cold starts).
- Control-twin comparison when a peer runs the same code, and per-member, per-Availability Zone and per-revision outlier detection for gray failures.
- Hidden-limit checks: burstable CPU credits, gp2 and gp3 storage performance, Lambda concurrency and memory-sets-CPU, SQS visibility timeout, DynamoDB partitions, ElastiCache network allowances, service quotas and Auto Scaling at maximum.
- Retry amplification and client-timeout sizing from the dependency's p99, ranked above raising downstream limits.
- Service deep checks for RDS and Aurora (Database Insights through the `pi` API), EC2, EBS, ECS, EKS, Lambda, DynamoDB, ElastiCache, SQS, Elastic Load Balancing, API Gateway and NAT gateway.
- AI and ML deep checks: Amazon Bedrock model invocation (arriving load as Invocations plus InvocationThrottles, output tokens per second to separate service-side slowdowns from longer answers, per-model tokens-per-minute and requests-per-minute quotas and Provisioned Throughput as hidden limits, cross-Region inference profiles), SageMaker AI real-time endpoints (ModelLatency against OverheadLatency, InvocationsPerInstance against measured per-instance capacity, instance-type quotas, serverless ModelSetupTime), GPU inference on EKS through Accelerated Compute Insights, and Bedrock AgentCore runtime metrics; a hand-off rule names `bedrock-operation-review`, `sagemaker-ai-ops-review`, `agentcore-ops-review` or `aiml-gpu-training-cluster-investigation` as the next step when the bottleneck is inside the model, the training job or the agent runtime.
- AWS Trusted Advisor (performance pillar) as a read-only evidence source next to Compute Optimizer: flagged resources on the request path are hypotheses to confirm with the workload's own metrics, off-path flags are reported separately, and the source is reported as unavailable on AccessDenied or without a Business or higher support plan (four `trustedadvisor` read actions added to the IAM add-on list).
- Telemetry gaps as structured output: every unreadable source on the request path is a row with the capability to enable, what the review could then measure, the cost direction with the pricing page link, and the enable and read permission changes; new reference `references/telemetry-sources.md` covers Application Signals, X-Ray, Database Insights, Container Insights, Lambda Insights, ElastiCache OpenTelemetry metrics, the CloudWatch agent, Contributor Insights, Compute Optimizer, Trusted Advisor, Network Monitoring performance monitors, SageMaker AI Insights, Accelerated Compute Insights, Bedrock invocation logging, AgentCore observability, and names CloudWatch investigations and CloudWatch Omni as investigation experiences rather than telemetry.
- "Performance Insights" renamed to "Database Insights (`pi` API)" throughout; the API calls are unchanged.
- AWS Compute Optimizer right-sizing, separated into hot-path and off-path findings, with a fallback to the workload's own metrics.
- Report template: assumptions, answer-first summary, request path, bottleneck with magnitude arithmetic, hypotheses table, findings, ranked recommendations with cost direction, verification metric and Well-Architected PERF ID; masking fixes labelled and kept separate; report hygiene (no account IDs, ARNs or IP addresses).
- Delegation blocks that carry the evidence, scope and ranking rules into sub-agent tasks.
- A step checklist under Instructions so the multi-step workflow can be tracked.
- Reference files: diagnosis rules, report and delegation, metrics by service, bottleneck patterns, hidden limits, logs and statistics, Well-Architected mapping, telemetry sources.
- Skill description names the AI entry points that users actually ask about ("is Bedrock the problem", "quota increase", slow or empty model calls, tokens per minute) so the chat deep-dive subagent selects the skill for model-invocation questions, not only for classic latency wording; observed on a Bedrock caller-timeout scenario where four chat runs in a row left the skill unread while the investigation path loaded it.
