# Classic AWS/ElastiCache CloudWatch metrics

Use for serverless caches, Redis OSS, Memcached, and gaps in the OpenTelemetry path.

## Querying

Dimension names differ by deployment, so use a `SEARCH` expression rather than
guessing dimensions. It returns one series per node:

```
use_aws(service_name="cloudwatch", operation_name="get_metric_data", parameters={
  "StartTime": "<window start>", "EndTime": "<window end>",
  "MetricDataQueries": [
    {"Id": "cpu", "Expression": "SEARCH('{AWS/ElastiCache,CacheClusterId,CacheNodeId} MetricName=\"EngineCPUUtilization\" \"<replication-group-id>\"', 'Maximum', 60)"},
    {"Id": "evict", "Expression": "SEARCH('{AWS/ElastiCache,CacheClusterId} MetricName=\"Evictions\" \"<replication-group-id>\"', 'Sum', 60)"}
  ]})
```

- Node-based: each node is a cache cluster named `<group>-<shard>-<node>` (cluster mode
  enabled) or `<group>-<node>`. Host-level metrics (CPU, memory, network) also carry
  `CacheNodeId`; engine metrics carry only `CacheClusterId`. If a `SEARCH` with
  `CacheNodeId` returns nothing, drop that dimension.
- Serverless: sources disagree on the dimension name (`clusterId` or
  `ServerlessCacheName`), so search the namespace without a dimension schema:
  `SEARCH('{AWS/ElastiCache} MetricName="ThrottledCmds" "<cache-name>"', 'Sum', 60)`.
  If a search returns nothing, call `cloudwatch list_metrics` on `AWS/ElastiCache` to
  see the real dimensions before concluding that the metric is absent.
- Use `Maximum` for CPU, memory and lag per node, and `Sum` with a 60-second period for
  counts. Query the incident window and a baseline window of the same length.

## Metrics by question

| Question | Node-based metrics | Serverless metrics |
|---|---|---|
| Engine saturated? | `EngineCPUUtilization` (per node, Max), `CPUUtilization` | `ElastiCacheProcessingUnits`, `ThrottledCmds` |
| One shard hot? | Compare `EngineCPUUtilization`, `GetTypeCmds`, `SetTypeCmds`, `NetworkBytesIn` across nodes | n/a (managed) |
| Slow commands? | `*BasedCmdsLatency` per family (µs) vs `*BasedCmds`; `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency` (µs) | `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency`, `*BasedCmdsECPUs` |
| Memory full? | `DatabaseMemoryUsagePercentage`, `DatabaseMemoryUsageCountedForEvictPercentage`, `BytesUsedForCache`, `CurrItems` | `BytesUsedForCache` vs `CacheUsageLimits.DataStorage` |
| Evicting or expiring? | `Evictions`, `Reclaimed` (expired keys), `CacheHits`, `CacheMisses`, `CacheHitRate` | `Evictions`, `CacheHitRate` |
| Fragmentation or swap? | `MemoryFragmentationRatio`, `SwapUsage`, `FreeableMemory` | n/a |
| Connections? | `CurrConnections`, `NewConnections`, `RejectedConnections` | `CurrConnections`, `NewConnections` |
| Replication? | `ReplicationLag` (seconds), `ReplicationBytes`, `SaveInProgress`, `IsMaster`, `MasterLinkHealthStatus` | n/a (managed) |
| Network limits? | `NetworkBandwidthInAllowanceExceeded`, `NetworkBandwidthOutAllowanceExceeded`, `NetworkPacketsPerSecondAllowanceExceeded`, `NetworkConntrackAllowanceExceeded` | n/a |
| Underscaled? | `TrafficManagementActive` = 1 | `ThrottledCmds` > 0 |
| Auth failures? | `AuthenticationFailures`, `CommandAuthorizationFailures`, `KeyAuthorizationFailures`, `IamAuthenticationExpirations`, `IamAuthenticationThrottling` | same |
| Latency percentiles (timeout comparison)? | `SuccessfulReadRequestLatency`, `SuccessfulWriteRequestLatency` with `p99` and `Maximum` (µs) | same |
| Burstable nodes? | `CPUCreditBalance`, `CPUCreditUsage` (only relevant when CPU is high) | n/a |

Memcached: `CPUUtilization`, `Evictions`, `CurrConnections`, `GetHits`, `GetMisses`,
`CurrItems`, `BytesUsedForCacheItems`, `SwapUsage`. No replication or persistence.

Metrics are empty until a cache serves traffic; a serverless cache with no traffic
emits nothing. That is not a fault.
