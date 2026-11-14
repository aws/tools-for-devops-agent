# Classic AWS/ElastiCache CloudWatch metrics

Use for serverless caches, Redis OSS, Memcached, and gaps in the OpenTelemetry path.

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
  enabled) or `<group>-<node>`, published under the `CacheClusterId` dimension. If the
  same node appears twice (with and without `CacheNodeId`), use one of the two series.
- Serverless: the dimension is `clusterId` (the serverless cache name):
  `SEARCH('{AWS/ElastiCache,clusterId} MetricName="ThrottledCmds" "<cache-name>"', 'Sum', 60)`.
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
