# Classic AWS/ElastiCache CloudWatch metrics

Use for serverless caches, Redis OSS, Memcached, gaps in the OpenTelemetry path, and the
metrics that OpenTelemetry has no equivalent for (`CurrItems`, `CurrVolatileItems`,
latency percentiles, `ReplicationLag`, `CPUUtilization`, CPU credits, IAM expirations,
`NetworkBaselineUsage*`).

## Querying

Use a `SEARCH` expression on the namespace with the cache ID as a search term, so that
you get one series per node without listing nodes or guessing dimension sets:

```
use_aws(service_name="cloudwatch", operation_name="get_metric_data", parameters={
  "StartTime": "<window start>", "EndTime": "<window end>",
  "MetricDataQueries": [
    {"Id": "cpu", "Expression": "SEARCH('{AWS/ElastiCache} MetricName=\"EngineCPUUtilization\" \"<replication-group-id>\"', 'Maximum', 60)"},
    {"Id": "evict", "Expression": "SEARCH('{AWS/ElastiCache} MetricName=\"Evictions\" \"<replication-group-id>\"', 'Sum', 60)"}
  ]})
```

- Node-based: each node is a cache cluster named `<group>-<shard>-<node>` (cluster mode
  enabled) or `<group>-<node>`, published under the `CacheClusterId` dimension.
- Serverless: the dimension is `clusterId` (the serverless cache name):
  `SEARCH('{AWS/ElastiCache} MetricName="ThrottledCmds" "<cache-name>"', 'Sum', 60)`.
- If a search returns nothing, call `cloudwatch list_metrics` on `AWS/ElastiCache` to
  see the real dimensions before concluding that the metric is absent. A cache that
  serves no traffic can have no datapoints for traffic metrics.
- Use `Maximum` for CPU, memory and lag per node, and `Sum` with a 60-second period for
  counts. Node metrics are published every 60 seconds; CPU credit metrics every
  5 minutes. Query the incident window and a baseline window of the same length.

## Metrics by question

| Question | Node-based metrics | Serverless metrics |
|---|---|---|
| Engine saturated? | `EngineCPUUtilization` (per node, Max), `CPUUtilization`, `ProcessedCommands` | `ElastiCacheProcessingUnits`, `ThrottledCmds` |
| One shard hot? | Compare `EngineCPUUtilization`, `GetTypeCmds`, `SetTypeCmds`, `NetworkBytesIn` across nodes | n/a (managed) |
| Slow commands? | `*BasedCmdsLatency` per family (µs, CPU time per call) vs `*BasedCmds`; `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency` (µs) | `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency`, `*BasedCmdsECPUs` |
| Errors? | `ErrorCount` (failed commands, no type) | n/a |
| Memory full? | `DatabaseMemoryUsagePercentage`, `DatabaseMemoryUsageCountedForEvictPercentage`, `BytesUsedForCache`, `UsedMemoryDataset`, `CurrItems`, `CurrVolatileItems` | `BytesUsedForCache` vs `CacheUsageLimits.DataStorage`, `CurrItems`, `CurrVolatileItems` |
| Evicting or expiring? | `Evictions`, `Reclaimed` (expired keys), `CacheHits`, `CacheMisses`, `CacheHitRate` | `Evictions`, `CacheHits`, `CacheMisses`, `CacheHitRate` |
| Fragmentation or swap? | `AllocatorFragmentationRatio`, `MemoryFragmentationRatio`, `SwapUsage`, `MajorPageFaults`, `FreeableMemory` | n/a |
| Connections? | `CurrConnections`, `NewConnections`, `RejectedConnections`, `BlockedConnections` | `CurrConnections`, `NewConnections` |
| Replication? | `ReplicationLag` (seconds), `ReplicationBytes`, `SaveInProgress`, `IsMaster` | n/a (managed) |
| Network limits? | `NetworkBandwidthInAllowanceExceeded`, `NetworkBandwidthOutAllowanceExceeded`, `NetworkPacketsPerSecondAllowanceExceeded`, `NetworkConntrackAllowanceExceeded`, `NetworkBaselineUsageInPercentage`, `NetworkBaselineUsageOutPercentage` | `NetworkBytesIn`, `NetworkBytesOut` |
| Underscaled? | `TrafficManagementActive` = 1 | `ThrottledCmds` > 0 |
| Auth failures? | `AuthenticationFailures`, `CommandAuthorizationFailures`, `KeyAuthorizationFailures`, `ChannelAuthorizationFailures`, `IamAuthenticationExpirations`, `IamAuthenticationThrottling` | same, except `ChannelAuthorizationFailures` |
| Server latency percentiles? | `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency` with `p99` and `Maximum` (µs). They measure the engine's response time; the client's network round trip and processing are not included | same |
| Burstable nodes? | `CPUCreditBalance`, `CPUCreditUsage` (only relevant when CPU is high) | n/a |

`MasterLinkHealthStatus` is about online migration from Valkey or Redis OSS on EC2, not
about replicas. For a replica's link, use OTel `valkey.replication.link_healthy`.

Memcached: `CPUUtilization`, `Evictions`, `CurrConnections`, `GetHits`, `GetMisses`,
`CurrItems`, `BytesUsedForCacheItems`, plus host metrics such as `SwapUsage` and
`FreeableMemory`. No replication or persistence.

## Reading the metrics

- `EngineCPUUtilization` is the engine's single main thread. `CPUUtilization` is the
  whole host and stays low on nodes with 4 or more vCPUs while the engine is saturated.
  On nodes with 2 or fewer vCPUs (for example `t4g.small`), judge saturation with
  `CPUUtilization` against `90 / vCPU count` (AWS guidance: 45% on 2 vCPUs).
- `TrafficManagementActive = 1` means ElastiCache is managing traffic because more
  commands arrive than the engine can process; sustained, it indicates an underscaled
  node.
- `SuccessfulReadRequestLatency`/`SuccessfulWriteRequestLatency` support any percentile
  between p0 and p100 (for example `p99`) and have no OpenTelemetry equivalent. They
  measure the time the engine takes to respond, so the client's network round trip, TLS
  and its own processing are not in them. Never compare a client timeout with them
  alone. Pipelining with `CLIENT REPLY` enabled can inflate them; AWS recommends
  pipelining with `CLIENT REPLY OFF`
  ([source](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/CacheMetrics.WhichShouldIMonitor.html#metrics-latency),
  "Latency" section).
- `CurrConnections` includes 4 to 6 connections that ElastiCache uses for monitoring.
- A hit ratio over very few lookups is not meaningful (it jumps to 0% or 100%); quote the
  lookup rate with it.

## Units and retention

- Request latency and slow log durations are in microseconds; `ReplicationLag` is in
  seconds; memory percentages are 0-100.
- CloudWatch keeps 1-minute datapoints for 15 days and 5-minute datapoints for 63 days.
  For older incidents, use a 300-second period.
