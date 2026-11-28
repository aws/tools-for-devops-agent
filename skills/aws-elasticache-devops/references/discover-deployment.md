# Identify the deployment

Run this first. It tells you which kind of cache it is, which metrics path applies, and
which features its engine version supports.

## Calls

Run whichever applies (the operator may not say which kind of cache it is):

```
use_aws(service_name="elasticache", operation_name="describe_replication_groups",
        parameters={"ReplicationGroupId": "<id>"})
use_aws(service_name="elasticache", operation_name="describe_serverless_caches",
        parameters={"ServerlessCacheName": "<name>"})
use_aws(service_name="elasticache", operation_name="describe_cache_clusters",
        parameters={"CacheClusterId": "<id>", "ShowCacheNodeInfo": True})
```

Record: engine and version, serverless or node-based, `ClusterEnabled`, shards and
node roles per AZ, node type, `MultiAZ`/`AutomaticFailover`, parameter group name,
`LogDeliveryConfigurations`, and for serverless `CacheUsageLimits`.

## Metrics path

- **Node-based Valkey:** use the OpenTelemetry metrics and the classic metrics. OTel
  gives per-shard, per-command and error-type breakdowns:
  [query-otel-metrics.md](query-otel-metrics.md). Classic metrics cover what OTel has no
  equivalent for (`CurrItems`, `CurrVolatileItems`, latency p99, `ReplicationLag`,
  `CPUUtilization`, CPU credits, IAM expirations, `NetworkBaselineUsage*`) and the
  metric the customer's alarm fired on: [query-classic-metrics.md](query-classic-metrics.md).
- **Serverless (any engine), Redis OSS, Memcached:** OpenTelemetry metrics are not
  emitted. Use [query-classic-metrics.md](query-classic-metrics.md).
- **A gap in the OpenTelemetry path:** use the classic metric.

## Features by engine version

Check the engine version before recommending a feature.

| Feature | Available from |
|---|---|
| Slow log delivery | Valkey 7.x; Redis OSS 6.0 |
| Engine log delivery | Valkey 7.x; Redis OSS 6.2 |
| IAM authentication | Valkey 7.2; Redis OSS 7.0 |
| `CLUSTER SLOT-STATS` | Valkey 8.0, cluster mode enabled |
| `COMMANDLOG` | Valkey 8.1 |
| OpenTelemetry metrics | Node-based Valkey, any version, except replication groups on Outposts. Not Redis OSS, Memcached or serverless |
