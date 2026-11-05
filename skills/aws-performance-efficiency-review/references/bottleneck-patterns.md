# Bottleneck patterns and starting thresholds

Thresholds here are investigation starting points, not service limits. A value past a threshold makes a resource a suspect; the bottleneck is confirmed only when its timing lines up with the user-facing latency. Always state the threshold you applied.

## USE and RED in one line each

- **USE (resources):** Utilization (how busy), Saturation (how much work is queued or refused), Errors.
- **RED (services):** Rate (requests per second), Errors, Duration (latency distribution).

Start with RED on the request path to find the slow hop, then USE on that hop's resources to find why.

## Starting thresholds

| Resource | Signal | Suspect when |
|---|---|---|
| EC2 / ECS / EKS CPU | CPU utilization p90 | above 80% sustained for 15 minutes or more |
| Burstable EC2 | CPUCreditBalance | near zero while CPU is capped at baseline |
| Memory (agent or Container Insights) | memory utilization | above 85%, or any swap, or container restarts for OOM |
| EBS | VolumeQueueLength | sustained above 1 per 1,000 provisioned IOPS (heuristic) or rising with latency |
| EBS gp2 / st1 / sc1 | BurstBalance | below 20% |
| RDS / Aurora | DBLoad | above the instance vCPU count |
| RDS / Aurora | DatabaseConnections | above 80% of `max_connections` |
| RDS / Aurora | ReadLatency / WriteLatency | above 20 ms (heuristic for SSD-backed storage) |
| RDS / Aurora | FreeableMemory, SwapUsage | low freeable memory together with non-zero swap |
| ElastiCache | EngineCPUUtilization | above 80% |
| ElastiCache | hit ratio | below 80% for a read-through cache, or falling |
| ElastiCache | Evictions | any sustained evictions on a cache sized to hold the working set |
| DynamoDB | ThrottledRequests / ThrottleEvents | any sustained non-zero value on the hot path |
| Lambda | Duration p99 | above 80% of the configured timeout; then read MemorySize (or the REPORT line `Memory Size`) |
| Lambda | Throttles | any non-zero value on the hot path |
| SQS | ApproximateAgeOfOldestMessage | growing over the window, or above the processing SLA |
| ALB | RejectedConnectionCount, TargetConnectionErrorCount | any non-zero value |
| NAT gateway | ErrorPortAllocation | any non-zero value |

## Patterns: symptom to likely cause

| Pattern in the data | Likely cause | Confirm with |
|---|---|---|
| Latency rises with request rate; CPU of the tier near 100% | Capacity: tier too small or not scaling | Auto Scaling activity, max size reached, ECS desired versus running |
| Latency step change at flat traffic | A change: deployment, configuration, query plan, dependency | Change history and deployments at the step time; per-edge latency before and after |
| p99 high, p50 normal | Tail effects: cold starts, garbage collection, lock contention, a slow subset of keys or queries, retries | Slow trace samples; Performance Insights wait events. For cold starts, compute init share x mean `Init Duration` and compare it with the shift in caller-observed end-to-end latency; Lambda `Duration` excludes init time, so a `Duration` p50 shift cannot come from initialization (see `diagnosis-rules.md`, Cold starts); a whole-distribution shift is not a tail effect |
| Periodic latency spikes | Batch jobs, cron, backups, cache expiry at the same time (thundering herd), scaling cooldown | Align spikes with scheduled events and backup windows |
| Database DBLoad above vCPU, waits dominated by CPU | Expensive queries or missing indexes | Top `db.sql_tokenized` by load |
| DBLoad high: is it one costly statement per request or many small ones (N+1)? | One expensive statement versus N+1 chatty access | Load check: average active sessions ≈ request rate × per-request database time. If one statement's time accounts for the load, it is one expensive statement per request; if the load only adds up across many small statements per request, it is N+1 |
| Memory looks pinned at ~100 | Likely a unit error, not saturation | Check the unit first: a megabyte metric (for example `ECS/ContainerInsights` `MemoryUtilized`) read as a percent. Divide by the reserved amount, or use the percent metric, before calling it saturated |
| Database waits dominated by I/O | Storage throughput or IOPS limit, working set larger than memory | ReadIOPS against the limit; BufferCacheHitRatio; FreeableMemory |
| Database waits dominated by locks | Contention on hot rows or long transactions | Lock wait events; top statements |
| Connections near maximum, latency rising | No connection pooling, or a connection leak | NewConnections churn; RDS Proxy absent |
| Connection pool, thread pool or concurrency limit pinned at its maximum while the dependency behind it is slow | A consequence of the slow dependency, not an independent cause (Little's law: in-flight = rate x latency). It is an independent cause only if it saturates before the dependency slows down | Compare when the limit was reached against when dependency latency rose; in-flight ≈ rate x latency |
| Cache misses rising with database load | Cache too small, TTL too short, or a key pattern that defeats caching | First confirm the cache exists in configuration or code (a field name is not proof); then evictions and hit ratio over time |
| Burstable instance fine for hours then slow | CPU credits exhausted | CPUCreditBalance reaching zero at the onset |
| Lambda throttles during a peak | Reserved or account concurrency limit, or callers retrying into the limit | ConcurrentExecutions at the limit; effective concurrency = completion rate x duration; attempts per originating request (if above 1, see Retry amplification in `diagnosis-rules.md`) |
| Queue age grows while consumers look idle | Consumer concurrency capped, or a downstream dependency throttles consumers | Consumer metrics and its own dependencies |
| High latency on cross-AZ or cross-Region calls | Placement: chatty calls crossing zones or Regions on the hot path | Topology placement; per-edge latency in traces |
| NAT gateway port allocation errors | Many connections to one destination through one NAT gateway | ErrorPortAllocation timing against the error spike |
| Downstream latency rises, then the caller's request count to it climbs above what clients sent | Retry storm: retries amplify load across layers (work amplification). When the magnitude test passes, the caller's timeout and retry policy is the cause; raising the downstream limit is masking | Retry counts and client timeout against the dependency's p99 at single-attempt load (a busy-window p99 can be inflated by retries); attempts per originating request above 1, plus the magnitude test: originating rate x 1 attempt fits capacity while the amplified attempt rate exceeds it (`diagnosis-rules.md`, Retry amplification) |
| One instance, task, Availability Zone, or code revision has far worse latency or errors than its peers while the aggregate looks fine | Single-member or single-AZ gray failure | Break the metric down per member and compare with peers (median with IQR or MAD, or top contributor share); a passing shallow health check does not clear it |
| Latency spikes at startup, after a deploy, or after a cache flush, then settles | Cache cold start or cold tier (empty cache, JIT warmup, failover path, rarely used fallback) | Align the spike with restart, deploy or cache-expiry time; hit ratio climbing as the spike fades |
| Per-instance utilization high, latency rising, no new instances launching | Auto Scaling group at its maximum size | GroupInServiceInstances at GroupMaxSize; scaling activities show no further launches (see `hidden-limits.md`) |
| Callers see throttling or added latency while the resource itself is not saturated | A service quota or account limit reached | AWS/Usage against the applied Service Quotas value; throttle errors in logs (see `hidden-limits.md`) |
| Aggregate error rate looks low but a single operation, caller or member has a high error rate | Deflated aggregate: a healthy majority masks a degraded slice | Break error rate down by operation, caller, member and AZ before trusting the total |
| Many callers' 4xx rise together at the same time | Misattributed client errors: a shared change (a new validation, an auth or schema change) is blamed on clients | Group 4xx by caller and by operation; a synchronized rise across unrelated callers points to a server-side change, not the clients |
| Tier scales on CPU but users feel latency or queue age | Scaling signal mismatch: CPU does not track the user-facing metric | Compare CPU against latency or queue age over the window; target tracking can scale on latency or backlog instead |
| Client timeout is below the dependency's p99 | Timeouts fire on normal tail latency and trigger retries | Compare the configured client timeout with the dependency's measured p99 at single-attempt load; size the caller's client timeout from that p99, inside the caller's own deadline (this is the fix, not masking) |
| Lambda Duration near the timeout, low memory used, a same-code twin with more memory is healthy | CPU share too small for the work (memory sets CPU) | Memory ratio against the measured compute-time ratio; predicted post-change duration (see `diagnosis-rules.md`, Lambda memory and CPU) |
| Only one of two peers is degraded after a change applied to both | The change is not the cause (ruled out by scope) | Diff configuration and request shape between the peers instead |

## Overload and dependency behaviour

- **Work amplification.** A retry at each layer multiplies the request count downstream, so a slow dependency can be hit by several times the client request rate. The server sees more requests than clients sent. Check retry policy, retry counts and backoff; a client timeout set below the dependency's p99 makes normal tail latency look like failure and drives retries. Map to PERF01-BP02 (decouple with a queue or event) and PERF04-BP05 (connection reuse and protocol choice).
- **Concurrency and goodput.** Once a resource saturates, latency grows with concurrency and useful completed work (goodput) falls below raw throughput as timeouts and retries waste capacity. Load shedding (rejecting or degrading excess work early) protects goodput. Map to PERF02-BP05 (scale dynamically) and PERF01-BP04 (trade-offs).
- **Scaling lag and signal.** Auto Scaling reacts slowly to a sudden spike because instances take time to launch and warm, so a spike test matters for event-driven peaks. Scaling on CPU misses a tier whose users feel latency or queue age; target tracking can scale on a latency or backlog metric instead. Map to PERF02-BP05.
- **Modal behaviour.** Some slow paths appear only in a state the steady state never exercises: a cold cache, a rarely used fallback, a failover path, or first use after a deploy. Name the mode and when it triggers rather than treating the slow sample as random.

## When the evidence is incomplete

Say which link in the chain is unverified and what would close it, for example: "Database CPU and latency rose at the same minute as the deployment, but no traces exist to confirm the new code path calls the database more often. Enable X-Ray or Application Signals on the service, or compare query counts in Performance Insights before and after the deployment."
