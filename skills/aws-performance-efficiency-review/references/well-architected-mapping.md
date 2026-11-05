# Well-Architected Performance Efficiency mapping

Map every finding to one best-practice ID. Source: [Performance efficiency pillar](https://docs.aws.amazon.com/wellarchitected/latest/framework/performance-efficiency.html), Well-Architected Framework (latest version).

## PERF 1. Architecture selection

How do you select appropriate cloud resources and architecture for your workload?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF01-BP01 | Learn about and understand available cloud services and features | Self-managed component on the hot path where a managed or purpose-built service fits the access pattern |
| PERF01-BP02 | Use guidance from your cloud provider or an appropriate partner to learn about architecture patterns and best practices | Synchronous chain where a queue or event pattern would decouple a slow dependency; retries amplifying load across layers (work amplification) with no backpressure or decoupling |
| PERF01-BP03 | Factor cost into architectural decisions | Recommendation raises cost; state the trade-off |
| PERF01-BP04 | Evaluate how trade-offs impact customers and architecture efficiency | Consistency or durability settings that add latency without a stated requirement; no load shedding, so goodput collapses under overload |
| PERF01-BP05 | Use policies and reference architectures | Inconsistent configuration across similar services |
| PERF01-BP06 | Use benchmarking to drive architectural decisions | Instance family or architecture chosen without a comparison |
| PERF01-BP07 | Use a data-driven approach for architectural choices | Sizing not based on observed metrics |

## PERF 2. Compute and hardware

How do you select and use compute resources in your workload?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF02-BP01 | Select the best compute options for your workload | Compute type mismatched to the workload shape (for example, steady load on Lambda at high concurrency, or spiky load on fixed EC2) |
| PERF02-BP02 | Understand the available compute configuration and features | Burstable instance with exhausted credits; older generation family; Lambda memory set low, which also limits its CPU |
| PERF02-BP03 | Collect compute-related metrics | Memory not published for EC2; Container Insights off |
| PERF02-BP04 | Configure and right-size compute resources | Compute Optimizer Underprovisioned on the hot path; Overprovisioned off the hot path |
| PERF02-BP05 | Scale your compute resources dynamically | Auto Scaling at maximum during the peak; no scaling policy; target too high; ECS desired below demand; queue or stream consumers that do not scale with backlog; a single degraded member in a shared-queue consumer fleet that the aggregate hides; scaling on CPU when users feel latency or queue age; Auto Scaling group pinned at GroupMaxSize; slow scaling against a sudden spike |
| PERF02-BP06 | Use optimized hardware-based compute accelerators | Compute-bound ML or media work on general-purpose CPUs |

## PERF 3. Data management

How do you store, manage, and access data in your workload?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF03-BP01 | Use a purpose-built data store that best supports your data access and storage requirements | Key-value access on a relational database at high rate; analytics queries on the transactional primary |
| PERF03-BP02 | Evaluate available configuration options for data store | EBS or RDS storage at its IOPS or throughput limit; gp2 burst exhausted; DynamoDB capacity mode wrong for the traffic shape |
| PERF03-BP03 | Collect and record data store performance metrics | Performance Insights or Database Insights disabled; no slow query log |
| PERF03-BP04 | Implement strategies to improve query performance in data store | Top SQL by load dominates DBLoad; read traffic on the writer that a replica could serve |
| PERF03-BP05 | Implement data access patterns that utilize caching | No cache in front of repeated reads; low hit ratio; evictions; cold-cache latency spikes after a restart or deploy; bimodal latency from cache hit versus miss |

## PERF 4. Networking and content delivery

How do you select and configure networking resources in your workload?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF04-BP01 | Understand how networking impacts performance | Chatty cross-AZ or cross-Region calls on the hot path |
| PERF04-BP02 | Evaluate available networking features | Static or cacheable content served from origin without a CDN; traffic to AWS services through NAT instead of VPC endpoints |
| PERF04-BP03 | Choose appropriate dedicated connectivity or VPN for your workload | Hybrid dependency on the hot path over the internet or a saturated link |
| PERF04-BP04 | Use load balancing to distribute traffic across multiple resources | Uneven target load; rejected connections; unhealthy targets during peaks; a single degraded instance or Availability Zone the aggregate hides; a shallow health check passing while a dependency behind the target fails |
| PERF04-BP05 | Choose network protocols to improve performance | No connection reuse (high new-connection rate); protocol choice adds round trips |
| PERF04-BP06 | Choose your workload's location based on network requirements | Users far from the serving Region with no edge or multi-Region option |
| PERF04-BP07 | Optimize network configuration based on metrics | NAT port allocation errors; network allowance exceeded on instances or cache nodes |

## PERF 5. Process and culture

How do your organizational practices and culture contribute to performance efficiency in your workload?

| ID | Best practice | Typical findings |
|---|---|---|
| PERF05-BP01 | Establish key performance indicators (KPIs) to measure workload health and performance | No latency objective or SLO defined; no error budget or burn rate derived from the SLO |
| PERF05-BP02 | Use monitoring solutions to understand the areas where performance is most critical | No tracing or Application Signals on the hot path; no percentile alarms; metrics not broken down per operation, instance, Availability Zone or caller; no client-side view (Synthetics or RUM) |
| PERF05-BP03 | Define a process to improve workload performance | Repeated regressions after deployments with no performance check; no performance regression gate in CI/CD |
| PERF05-BP04 | Load test your workload | Capacity for a known peak unverified; no stress, soak or spike test to find the breaking point, slow leaks or spike behaviour |
| PERF05-BP05 | Use automation to proactively remediate performance-related issues | Manual scaling ahead of events; raw-threshold alarms instead of SLO burn-rate and per-fault-boundary alarms; alarms without a runbook |
| PERF05-BP06 | Keep your workload and services up-to-date | Older engine versions or instance generations with known performance improvements available |
| PERF05-BP07 | Review metrics at regular intervals | No recurring performance review |

## Design principles

Name a design principle in the recommendation rationale when it applies:

- **Democratize advanced technologies:** consume a managed service instead of running the technology yourself.
- **Go global in minutes:** deploy closer to users to cut latency.
- **Use serverless architectures:** remove server management for compute and storage tiers where the access pattern fits.
- **Experiment more often:** compare instance types, storage or configurations with a quick test instead of guessing.
- **Consider mechanical sympathy:** choose the approach that matches the data access pattern and how the service works.
