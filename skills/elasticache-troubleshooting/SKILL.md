---
name: elasticache-troubleshooting
description: Root-cause analysis for Amazon ElastiCache incidents (Valkey, Redis OSS
  and Memcached; serverless and node-based) using read-only AWS APIs. Use when
  investigating ElastiCache latency or timeouts, high engine CPU, one hot shard,
  memory pressure, evictions, OOM write failures, a dropping hit rate, connection
  errors or spikes, replication lag or stale reads, failovers, serverless throttling,
  or engine error replies such as OOM, MOVED, CROSSSLOT, READONLY, NOAUTH, WRONGPASS,
  LOADING or CLUSTERDOWN. Uses ElastiCache OpenTelemetry metrics through PromQL for
  node-based Valkey, classic AWS/ElastiCache CloudWatch metrics otherwise, plus
  ElastiCache events, parameter groups and delivered slow logs. Do not use for
  creating or sizing caches, data modeling, migrations or cost reports.
metadata:
  author: PopaCarlaDiana
  version: "1.0.0"
  summary: "Root-cause analysis for ElastiCache incidents from OpenTelemetry and CloudWatch metrics, events and logs."
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.aws-services: "Amazon ElastiCache, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Databases, Observability"
---

# Amazon ElastiCache troubleshooting

Name the root cause of an ElastiCache incident from evidence, rule out the lookalike
cause that produces the same symptom, and give the operator a fix.

## Rules

- **Read-only.** Never run `modify-*`, `reboot-*`, `test-failover`, scaling, snapshot
  or delete operations, and never create a resource metrics configuration (it is
  billed). Present every change as a recommendation for the operator to run, with
  its impact. Do not offer to apply it yourself.
- **No data-plane access.** The cache endpoint is inside the customer's VPC. Do not
  try to connect. When engine-side data would settle the question (for example,
  naming a hot key), recommend the operator-run command from
  `references/engine-followups.md` and say which result confirms the hypothesis.
- **Evidence over symptoms.** Every finding quotes the metric, the node or shard, the
  value and the time, compared with a baseline window of the same length before the
  onset.

## Step 1: Identify the deployment

Run whichever applies (the customer may not say which kind of cache it is):

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

Choose the metrics path:

| Deployment | Metrics |
|---|---|
| Node-based **Valkey** | OpenTelemetry metrics via PromQL first: read `references/otel-promql.md`. Use classic metrics only for gaps |
| Serverless (any engine), Redis OSS, Memcached | Classic `AWS/ElastiCache` metrics: read `references/classic-metrics.md` |

**Node-based Valkey: run the OpenTelemetry queries yourself, whatever your role.**

1. Load the `exploring-metrics` skill and its `cloudwatch-promql` reference now. Loading
   them makes the PromQL tools (`list_prometheus_metadata`, `get_prometheus_metrics`)
   available to you, including when you are a context-gathering or research sub-agent.
2. Run the workflow in `references/otel-promql.md` (metadata check, triage batch over
   the incident and baseline windows) with those tools.
3. Only if the PromQL tools are still not in your tool list after step 1, and you can
   start a sub-agent, delegate a metrics task. Include the text "Load the
   exploring-metrics skill and its cloudwatch-promql reference, then query the ElastiCache
   for Valkey OpenTelemetry metrics with PromQL", plus the *Query rules*, *Triage batch*
   and *Interpretation* sections of `references/otel-promql.md`, the replication group ID,
   account, region and both windows.

Do not report OpenTelemetry metrics as unavailable unless one of these happened, and
quote which one as a gap: `list_prometheus_metadata` returned no series or an error, or
the PromQL tools were missing after you loaded `exploring-metrics` and you could not
delegate.

## Step 2: Events and changes at the onset

```
use_aws(service_name="elasticache", operation_name="describe_events",
        parameters={"SourceType": "replication-group", "SourceIdentifier": "<id>",
                    "StartTime": "<onset - 2h>", "EndTime": "<now>"})
```

Use `serverless-cache` or `cache-cluster` as the source type when that applies (events
are kept 14 days). Look for `FailoverComplete`, `CacheNodeReplaceStarted`/`Complete`,
`CacheClusterScalingComplete`/`Failed`, `SnapshotComplete` and, on serverless,
`Cache Limit Approaching` (one slot near its 32 GB limit). Also
look up CloudTrail for `ModifyReplicationGroup`, `ModifyCacheParameterGroup`,
`ModifyServerlessCache`, `TestFailover` and security group changes in the window.
A failover, node replacement, reboot, scaling action, snapshot or parameter change
that lines up with the onset is the leading hypothesis. Confirm it with metrics.

## Step 3: Separate the cause from its lookalikes

**Anchor on the reported symptom and onset.** Start with the row for the symptom the
operator reported, even if another anomaly looks bigger. A change that *ended* before the
onset (traffic stopping, a load going away) does not cause symptoms that start after it.
Traffic that stops on every node with no errors and no events means the clients stopped,
not that the cache failed. If the window just before the onset contains a different
anomaly, say so, report it separately, and choose an earlier steady-state window as the
baseline.

Use the row that matches the symptom. The cause is confirmed only when its evidence
is present **and** the lookalike's evidence is absent.

| Symptom | Cause | Discriminating evidence | Lookalike to rule out |
|---|---|---|---|
| Writes fail, `OOM` errors | Memory full and nothing evictable: `noeviction`, or a `volatile-*` policy with no keys that have a TTL | Memory at ~100% of maxmemory, **evictions = 0** (quote it), `OOM` error replies, the policy value, and `CurrVolatileItems` (keys with a TTL) | Eviction policy working (evictions > 0, no `OOM`). Fix: if `CurrVolatileItems` is 0, `volatile-lru` frees nothing, so recommend `allkeys-lru` for a pure cache, deleting keys, or more capacity |
| Keys disappear, hit rate drops | Evictions: working set larger than memory | Evictions > 0 and rising while memory sits at max; expirations flat | TTL expiry (expirations up, evictions 0); cold cache after a failover or node replacement (event, item count drop) |
| Latency up, every shard | Engine saturation | Main-thread CPU ≥ 90% (`EngineCPUUtilization`), throughput up, **per-command latency flat** vs baseline | Expensive commands (next row); network allowance exceeded; swap |
| Latency spikes, periodic | Expensive O(N) commands (`KEYS`, `HGETALL`/`SMEMBERS`/`LRANGE` on big keys, `SORT`, scripts) | One command's average latency far above the others; matching slow log entries at the spike times | Saturation (all commands slow together) |
| Latency or CPU on **one shard** | Key-distribution skew: hot key, shared hash tag, or one growing key | One node ≥ 1.5x the median in throughput or engine CPU; the command family that dominates on it names the data type. To name the key, recommend `CLUSTER SLOT-STATS ORDERBY CPU-USEC LIMIT 10` then `CLUSTER GETKEYSINSLOT` (Valkey 8+, cluster mode); `--hotkeys`/`OBJECT FREQ` only under an LFU policy; never `MONITOR` on a primary | Undersized node type: all nodes within ~15 points of each other. Fix skew with client-side caching or by splitting the key; scaling up or adding shards does not fix one hot key |
| One shard's memory high | Hash-tag concentration or a big key in one slot | Memory spread > 15 points between primaries, stable for hours | Uniform memory pressure (all primaries within ~10 points) |
| Memory grows faster than key count | Big keys | Bytes per item (`BytesUsedForCache` / `CurrItems`) rising; `NetworkBytesOut` spikes on one node with engine CPU; slow log shows `HGETALL`/`LRANGE`/`SMEMBERS` | Many small keys: bytes per item flat |
| Latency up, engine CPU low | Client side: connection pool too small (requests queue in the client), or network | Engine CPU and per-command latency normal while the application sees latency; network allowance exceeded on the node | Engine saturation (CPU high) |
| Connection errors or timeouts | `maxclients` reached | Connected clients near the limit (65,000 on most node types), rejected connections > 0 | Connection churn |
| Connection timeouts, CPU up | Connection churn: no pooling, a new TLS connection per request | New connections per second very high (`NewConnections`; OTel `rate(valkey.connections.received)`) while current connections stay flat; handshake commands (`HELLO`, `CLIENT SETINFO`, `AUTH`, `PING`) at a high rate with no data commands; no rejections | `maxclients` (rejections > 0); security group change (CloudTrail, connections drop to 0) |
| Stale reads from replicas | Replication lag | `ReplicationLag` (seconds) up on replicas. Cause: a snapshot (`SaveInProgress`, snapshot event), a write burst on the primary, or a broken link (`MasterLinkHealthStatus`/`link_healthy` = 0, full resync) | Application reading through a cache layer with its own TTL |
| Brief outage, then errors | Failover or maintenance | Failover/replacement event at the onset; node role flip (`IsMaster` / `is_primary`). If errors persist **after** failover completes, the client is the cause: cached DNS, a pinned node endpoint, or a cluster client without topology refresh | Network or client-side failure (no event, no role change) |
| Serverless commands throttled | ECPU usage limit reached | `ThrottledCmds` > 0 while `ElastiCacheProcessingUnits` sits at `CacheUsageLimits.ECPUPerSecond.Maximum` | Client timeouts without throttling |
| A specific engine error reply | See `references/error-strings.md` | | |

Stop conditions: if engine CPU stays below 60% and connections are stable, the cause is
not capacity or connections; look at commands and the slow log. If evictions are 0 and
memory is below 70%, eviction is not the cause.

## Step 4: Configuration and logs

- **Parameters** that decide behaviour (node-based only):
  `use_aws(service_name="elasticache", operation_name="describe_cache_parameters",
  parameters={"CacheParameterGroupName": "<pg>", "Source": "user"})`. Check
  `maxmemory-policy`, `reserved-memory-percent`, `timeout`, `slowlog-log-slower-than`.
  A default group (`default.*`) uses `volatile-lru`.
- **Slow log**: if `LogDeliveryConfigurations` sends `slow-log` to CloudWatch Logs,
  run a Logs Insights query on that log group over the window (JSON format):
  ```
  fields Command, `Duration (us)`, ClientAddress, CacheClusterId
  | parse Command /^(?<cmd>\S+)/
  | stats count(*) as n, max(`Duration (us)`) as max_us, avg(`Duration (us)`) as avg_us by cmd, CacheClusterId
  | sort max_us desc | limit 20
  ```
  Durations are in **microseconds** (above 100,000 means the engine thread was blocked).
  Delivered logs **redact key names**, so name the command, the node and the client
  address, and recommend `SLOWLOG GET` to the operator for the key.

## Output

Always give all five parts, even when the cause looks obvious.

1. **Root cause**: one sentence naming the mechanism, not the symptom.
2. **Evidence**: metric, node/shard, value and time, against the baseline. The onset is
   the first datapoint of the failure signal (for example the first `OOM` errors), not
   when the symptom was reported.
3. **Ruled out**: the lookalike and the evidence that excludes it.
4. **Remediation**: an immediate mitigation and a durable fix, both for the operator
   to run.
5. **Gaps**: what could not be verified, with the command that would verify it.

## Gotchas

- `EngineCPUUtilization` is the engine's single main thread. `CPUUtilization` is the
  whole host and stays low on nodes with 4 or more vCPUs while the engine is saturated.
  On nodes with 2 or fewer vCPUs (for example `t4g.small`), judge saturation with
  `CPUUtilization` against `90 / vCPU count`. `TrafficManagementActive = 1` means the
  node is underscaled.
- `SuccessfulReadRequestLatency`/`SuccessfulWriteRequestLatency` support percentiles: request
  `p99` through `ExtendedStatistics` in `get_metric_data`/`get_metric_statistics`.
- Units: request latency metrics and slow log durations are microseconds;
  `ReplicationLag` is seconds; memory percentages are 0-100.
- Group-level aggregates hide skew. Always break down by node or shard.
- Serverless has no OpenTelemetry metrics and no parameter groups, and evicts only
  keys that have a TTL.
- In cluster mode, a low steady `MOVED` rate is normal. Writes sent to a replica return
  `MOVED`, not `READONLY`.
- Cluster-aware clients connect to each node endpoint after discovery through the
  configuration endpoint. Connections on node endpoints are normal, not a misconfiguration.
- Mention an earlier episode outside the incident window only with facts you verified, and
  keep it separate from the root cause.
- A high rate of `HELLO`/`CLIENT SETINFO`/`AUTH`/`PING` with no data commands is what
  each *new* connection sends. Current connections stay flat because each connection lives
  only milliseconds. The churn rate is new connections per second, never the
  current-connections count.
- Hit ratios are noise below about 10 lookups per second.
- One-minute datapoints are kept 15 days. For older incidents, use a 300-second period.
