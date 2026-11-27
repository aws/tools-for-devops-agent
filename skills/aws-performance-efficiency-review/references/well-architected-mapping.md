# Well-Architected Performance Efficiency mapping

Map every finding to one best-practice ID. Source: the Performance Efficiency pillar pages of the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/performance-efficiency.html). IDs follow the Framework pages as of 2026-11-26, not the retired pillar whitepaper.

## PERF 1. Validate workload performance requirements

How do you validate and manage your workload's performance requirements?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF01-BP01 | Validate requirements align to business needs | No stated performance target behind the architecture; a self-managed component on the hot path where a managed or purpose-built service fits the access pattern; a synchronous chain where a queue or event pattern would decouple the slow step; inconsistent configuration across similar services with no requirement that explains it |
| PERF01-BP02 | Evaluate the trade-offs between performance and other non-functional requirements | A recommendation raises cost; state the trade-off. Consistency or durability settings that add latency without a stated requirement; no load shedding, so goodput collapses under overload |
| PERF01-BP03 | Derive and establish KPIs that validate adherence to your performance requirements | No latency objective or SLO defined; no error budget or burn rate derived from the SLO; a target expressed as an average instead of a percentile |
| PERF01-BP04 | Establish criteria for performance degradation alerts and tolerances | No percentile alarms; raw-threshold alarms instead of SLO burn-rate and per-fault-boundary alarms; alarms that fire on conditions nobody acts on |

## PERF 2. Compute and hardware

How do you select and use compute resources to meet performance requirements?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF02-BP01 | Select the best compute options for your workload | Compute type mismatched to the workload shape (for example, steady load on Lambda at high concurrency, or spiky load on fixed EC2); older generation family where a newer one is a drop-in; instance family or architecture chosen without a comparison |
| PERF02-BP02 | Collect compute-related metrics | Memory not published for EC2; Container Insights off; Lambda Insights not installed on a CPU-bound function; no GPU or inference component metrics for accelerated workloads |
| PERF02-BP03 | Configure and right-size compute resources | Compute Optimizer Underprovisioned on the hot path; Overprovisioned off the hot path; burstable instance with exhausted credits; Lambda memory set low, which also limits its CPU; sizing not based on observed metrics |
| PERF02-BP04 | Scale your compute resources dynamically | Auto Scaling at maximum during the peak; no scaling policy; target too high; ECS desired below demand; queue or stream consumers that do not scale with backlog; a consumer cap below the producer rate |
| PERF02-BP05 | Use optimized hardware-based compute accelerators | Compute-bound ML or media work on general-purpose CPUs; GPU utilization low while inference latency is high (input pipeline or batching, not the accelerator) |

## PERF 3. Data management

How do you select and manage data stores to meet performance requirements?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF03-BP01 | Use a purpose-built data store that best supports your data access and storage requirements | Key-value access on a relational database at high rate; analytics queries on the transactional store; session state in a database where a cache fits |
| PERF03-BP02 | Evaluate available configuration options for data store | EBS or RDS storage at its IOPS or throughput limit; gp2 burst exhausted; DynamoDB capacity mode wrong for the traffic shape; connection pool or parameter group left at defaults under load |
| PERF03-BP03 | Collect and record data store performance metrics | Database Insights disabled (the `pi` API returns no data); no slow query log; ElastiCache OpenTelemetry metrics unavailable because the engine version is too old |
| PERF03-BP04 | Implement strategies to improve query performance in data store | Top SQL by load dominates DBLoad; missing index on the hot query; read traffic on the writer that a replica could serve |
| PERF03-BP05 | Implement data access patterns that utilize caching | No cache in front of repeated reads; low hit ratio; evictions; cold-cache latency spikes after a restart or deploy; bimodal latency that follows the hit ratio |

## PERF 4. Networking and content delivery

How do you select and configure networking to meet performance requirements?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF04-BP01 | Understand how networking impacts performance | Chatty cross-AZ or cross-Region calls on the hot path |
| PERF04-BP02 | Evaluate available networking features | Static or cacheable content served from origin without a CDN; traffic to AWS services through NAT instead of VPC endpoints |
| PERF04-BP03 | Choose appropriate dedicated connectivity or VPN for your workload | Hybrid dependency on the hot path over the internet or a saturated link |
| PERF04-BP04 | Use load balancing to distribute traffic across multiple resources | Uneven target load; rejected connections; unhealthy targets during peaks; a single degraded instance or Availability Zone behind a passing health check |
| PERF04-BP05 | Choose network protocols to improve performance | No connection reuse (high new-connection rate); protocol choice adds round trips |
| PERF04-BP06 | Choose your workload's location based on network requirements | Users far from the serving Region with no edge or multi-Region option |
| PERF04-BP07 | Optimize network configuration based on metrics | NAT port allocation errors; network allowance exceeded on instances or cache nodes |

## PERF 5. Monitor, test, and improve workload performance

How do you monitor, test, and improve workload performance over time?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF05-BP01 | Use monitoring solutions to understand the areas where performance is most critical | No tracing or Application Signals on the hot path; metrics not broken down per operation, member or caller; a slow customer request that cannot be attributed to a component |
| PERF05-BP02 | Evaluate your workload performance | Capacity for a known peak unverified; no stress, soak or spike test to find the breaking point; repeated regressions after deployments with no performance check or regression gate in CI/CD; no investigation workflow for performance incidents |
| PERF05-BP03 | Use automation to proactively remediate performance-related issues | Manual scaling ahead of events; a known, low-risk remediation still done by hand; remediation automated without approval, rollback or verification |
| PERF05-BP04 | Keep your workload and services up-to-date | Older engine versions or instance generations with known performance improvements available; lifecycle events for in-use versions ignored |
| PERF05-BP05 | Review metrics at regular intervals | No recurring performance review; alarms, dashboards, baselines and thresholds set once and never revisited |

## Design principles

Name a design principle in the recommendation rationale when it applies:

- **Democratize advanced technologies:** consume a managed service instead of running the technology yourself.
- **Go global in minutes:** deploy closer to users to cut latency.
- **Use serverless architectures:** remove server management for compute and storage tiers where the access pattern fits.
- **Experiment more often:** compare instance types, storage or configurations with a quick test instead of guessing.
- **Consider mechanical sympathy:** choose the approach that matches the data access pattern and how the service works.
