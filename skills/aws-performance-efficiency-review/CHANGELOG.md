# Changelog

## [1.0.0] - 2026-11-03

### Added

- Initial release: a cross-service performance review for AWS workloads, aligned with the Performance Efficiency pillar of the AWS Well-Architected Framework, for DevOps Agent Chat tasks and Incident RCA.
- Chat intake: at most three questions (performance target, expected peak or growth, constraints) before investigating, never asked during an investigation; answers are used to size recommendations with explicit arithmetic.
- Request-path mapping from the Agent Space topology, CloudWatch Application Signals and AWS X-Ray, with configuration inference as a fallback, including asynchronous paths (queues, streams, schedules, batch).
- RED measurement per hop and USE saturation checks, with percentiles, matched baselines and re-baselining when rate or configuration changed inside the window.
- Differential diagnosis: competing explanations ruled in or out by timing, scope, history and magnitude, with worked magnitude checks (served rate under a concurrency cap, effective concurrency, work amplification, Lambda memory and CPU, cold starts).
- Control-twin comparison when a peer runs the same code, and per-member, per-Availability Zone and per-revision outlier detection for gray failures.
- Hidden-limit checks: burstable CPU credits, gp2 and gp3 storage performance, Lambda concurrency and memory-sets-CPU, SQS visibility timeout, DynamoDB partitions, ElastiCache network allowances, service quotas and Auto Scaling at maximum.
- Retry amplification and client-timeout sizing from the dependency's p99, ranked above raising downstream limits.
- Service deep checks for RDS and Aurora (Performance Insights), EC2, EBS, ECS, EKS, Lambda, DynamoDB, ElastiCache, SQS, Elastic Load Balancing, API Gateway and NAT gateway.
- AWS Compute Optimizer right-sizing, separated into hot-path and off-path findings, with a fallback to the workload's own metrics.
- Report template: assumptions, answer-first summary, request path, bottleneck with magnitude arithmetic, hypotheses table, findings, ranked recommendations with cost direction, verification metric and Well-Architected PERF ID; masking fixes labelled and kept separate; report hygiene (no account IDs, ARNs or IP addresses).
- Delegation blocks that carry the evidence, scope and ranking rules into sub-agent tasks.
- A step checklist under Instructions so the multi-step workflow can be tracked.
- Reference files: diagnosis rules, report and delegation, metrics by service, bottleneck patterns, hidden limits, logs and statistics, Well-Architected mapping.
