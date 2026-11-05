# ElastiCache for Valkey: OpenTelemetry metrics through PromQL

Node-based ElastiCache for Valkey replication groups emit OpenTelemetry metrics to
CloudWatch, queryable with PromQL. Vended metrics are emitted automatically every
60 seconds at no additional cost; queries through the CloudWatch API are charged by
samples scanned, so keep them filtered and aggregated. Compared with classic metrics,
they add aggregation by shard or AZ in one query, calls and latency per individual
command (classic metrics only have command families), and error replies by type
(classic `ErrorCount` has no type).

Not emitted for serverless caches, Redis OSS, Memcached or replication groups on
Outposts.

## Workflow

1. Confirm the group is emitting, in one call:
   ```
   list_prometheus_metadata(
       aws_account_id="<account>", aws_region="<region>",
       kind="label_values", label_name="@resource.aws.elasticache.replication_group.id",
       match=['{"valkey.memory.used"}'], start="<window start>", end="<window end>",
   )
   ```
   If the ID is absent, use [classic-metrics.md](classic-metrics.md). Do not enumerate metric names; they
   are listed below.
2. Run the **triage batch** in parallel as range queries over the incident window,
   `step` 60s, then over a baseline window of the same length before the onset.
3. Follow up only in the areas the triage batch flags (see Interpretation).

## Query rules

- **Counters are cumulative**, not histograms (for example `valkey.commands.processed`,
  `valkey.command.calls`, `valkey.command.duration`, `valkey.errors`,
  `valkey.keys.evicted`, `process.cpu.time`). Wrap them in `rate(...[5m])`; use a range
  of at least `[5m]` for 60-second metrics. Never use `histogram_avg`/`histogram_sum` on
  `valkey.*` metrics. Only `system.network.io.rate` and `system.network.packet.rate` are
  histograms; read them with `histogram_quantile(0.99, ...)`.
- Gauges and up-down counters (`valkey.memory.used`, `valkey.memory.max`,
  `valkey.clients.connected`, `valkey.clients.max`, `valkey.replication.link_healthy`)
  are queried directly, without `rate`. Do not `sum` gauges across nodes; use `max` or
  `avg`.
- **Quote every dotted name**, inside braces and inside `by(...)`/`without(...)`/`on(...)`:
  `sum by ("valkey.command") (rate({"valkey.command.calls", ...}[5m]))`. Unquoted
  `by (valkey.command)` fails with HTTP 400.
- **Always filter** on `"@resource.aws.elasticache.replication_group.id"="<id>"` and
  **always aggregate**. Raw per-command series are huge, and a response is capped at
  500 series.
- **Ratios between two metrics:** PromQL pairs series only when their labels are
  identical, and returns no result otherwise. Aggregate both sides by node and match on
  node:
  `max by (N) ({"A", RG}) / on (N) max by (N) ({"B", RG})`.
- **`valkey.role` (`primary`|`replica`) is a datapoint label.** A node whose role changed
  appears as two series. Aggregate it away (`max without ("valkey.role")`) unless you
  need it. A role change during the window is itself a failover signal.
- Guard divisions with `> 0` so idle commands don't produce NaN series.
- `valkey.command.duration` is in seconds. Multiply by `1e6` for microseconds.
- **Detailed-only metrics** (e.g. `valkey.memory.used.overhead`, `valkey.eventloop.*`,
  `valkey.command.failed_calls`) are empty unless detailed monitoring is configured.
  Empty means *not configured*, not a wrong name. Do not retry; note it as a gap.

## Triage batch

`RG` = `"@resource.aws.elasticache.replication_group.id"="<id>"`,
`SHARD` = `"@resource.aws.elasticache.shard.id"`,
`NODE` = `"@resource.aws.elasticache.node.id"`.

T1, load per shard:
```
sum by (SHARD) (rate({"valkey.commands.processed", RG}[5m]))
```
T2, memory % of maxmemory per node:
```
100 * max by (NODE) ({"valkey.memory.used", RG}) / on (NODE) max by (NODE) ({"valkey.memory.max", RG})
```
T3, engine main-thread CPU % per node:
```
100 * sum by (NODE, "valkey.role") (rate({"process.cpu.time", "thread.type"="main", RG}[5m]))
```
T4, error replies by type:
```
sum by ("valkey.error.type") (rate({"valkey.errors", RG}[5m]))
```
T5, average latency per data command, in µs:
```
1e6 * sum by ("valkey.command") (rate({"valkey.command.duration", RG, CMDS}[5m]))
    / (sum by ("valkey.command") (rate({"valkey.command.calls", RG, CMDS}[5m])) > 0)
```
T6, calls/s per data command:
```
topk(10, sum by ("valkey.command") (rate({"valkey.command.calls", RG, CMDS}[5m])))
```
T7, evictions, expirations, new and rejected connections per node:
```
sum by (NODE) (rate({"valkey.keys.evicted", RG}[5m]))
sum by (NODE) (rate({"valkey.keys.expired", RG}[5m]))
sum by (NODE) (rate({"valkey.connections.received", RG}[5m]))
sum by (NODE) (rate({"valkey.connections.rejected", RG}[5m]))
```
`CMDS` excludes ElastiCache's own monitoring and client housekeeping:
```
"valkey.command"!~"INFO|PING|AUTH|HELLO|SELECT|CLIENT .*|CLUSTER .*|CONFIG .*|ACL .*|COMMAND.*"
```
Without it, `INFO`, which ElastiCache runs to monitor the node, can top the latency
ranking.

## Interpretation

**Shard skew (T1-T3):** one shard clearly above the others in TPS, memory % or
main-thread CPU (quote each shard's value) is **key-distribution skew** (hot key, shared
hash tag, or one growing key), not "a busy node". Follow up with T6 filtered to that shard's primary (`NODE="<node>"`) to
name the hot commands, and memory growth on the shard:
`deriv({"valkey.memory.used", RG, SHARD="<shard>"}[30m])` (bytes per second).

**Latency (T5):**
- One data command far slower than the rest (`KEYS`, `HGETALL`, `SMEMBERS`, `LRANGE`,
  `SORT` at hundreds of µs or more): expensive command or big key.
- All commands flat versus baseline while CPU or TPS rose: throughput and queueing, not
  slow commands. Say so with the per-command values.
- Main-thread CPU (T3) is a percentage of one vCPU. At or above the AWS-recommended 90%
  threshold, the engine is saturated regardless of vCPU count. T3 excludes I/O threads.
- `valkey.throttling.active == 1`: traffic management is active because more commands
  arrive than the engine can process; sustained, the node is underscaled.

**Errors (T4):** map `valkey.error.type` with [error-strings.md](error-strings.md). `OOM` → memory;
`READONLY` → failover or writes to a replica; `MOVED` high or rising → client not
cluster-aware or resharding.

**Memory:**
- Projection: `100 * predict_linear({"valkey.memory.used", RG}[1h], 3600) / on (NODE) group_left max by (NODE) ({"valkey.memory.max", RG})`.
  Above 100 means the node reaches maxmemory within an hour.
- Evictions (T7) under an eviction policy, or `OOM` errors under `noeviction`: the
  dataset no longer fits. Evictions with expirations flat rule out TTL expiry.
- `valkey.memory.allocator_frag_ratio` above 1.0 is allocator fragmentation; the higher
  the value, the worse. It is the fragmentation that the `activedefrag` parameter can
  address. Prefer it over `valkey.memory.fragmentation_ratio`, which includes OS-level
  overhead.
- Evictions while memory % looks below 100: compare `valkey.memory.used` minus
  `valkey.memory.not_counted_for_evict` with `valkey.memory.max`.
- Swap: `deriv({"system.paging.usage", "system.paging.state"="used", RG}[30m])` above 0,
  or a rising `rate({"process.paging.faults", RG}[5m])`.

**Connections:** `valkey.clients.connected / valkey.clients.max` (match on node) near
100%, or rejected connections above 0: the limit was hit. The `maxclients` limit also
counts replica and cluster bus connections. A high rate of
`valkey.connections.received` with a flat connected count: connection churn.

**Cache effectiveness:**
`100 * sum(rate({"valkey.keyspace.hits", RG}[5m])) / (sum(rate({"valkey.keyspace.hits", RG}[5m])) + sum(rate({"valkey.keyspace.misses", RG}[5m])))`.
Quote the lookup rate with it; a ratio over very few lookups is not meaningful.

**Network:** `sum by (NODE, "network.allowance_exceeded.reason") (rate({"system.network.allowance_exceeded", RG}[5m]))`
above 0 means packets were queued or dropped (`bandwidth_in`, `bandwidth_out`, `pps`,
`conntrack`). For bursts, compare `histogram_quantile(0.99, {"system.network.io.rate", RG})`
with `{"system.network.bandwidth.limit", RG}` per node.

**Replication and failover:** `{"valkey.replication.link_healthy", "valkey.role"="replica", RG} == 0`
means a replica's link is down. `valkey.persistence.rdb.save_in_progress == 1` during a
lag spike points to a snapshot. A change in `valkey.replication.is_primary` is a failover.

## Investigation priority

Start with the area that matches the reported symptom (connections, errors, memory,
latency). Then:

1. One shard or the whole group (T1-T3).
2. Slow command or throughput (T5, T6).
3. Errors by type (T4).
4. Memory: pressure, trend, evictions vs expirations, fragmentation.
5. Connections, network allowance, replication.
