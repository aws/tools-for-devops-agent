# Diagnosis table: symptom → cause → evidence → lookalike

Read this file in Step 3 of every investigation.

## Anchor on the reported symptom and onset

Start with the row for the symptom the operator reported, even if another anomaly looks
bigger. A change that *ended* before the onset (traffic stopping, a load going away) does
not cause symptoms that start after it. Traffic that stops on every node with no errors
and no events means the clients stopped, not that the cache failed. If the window just
before the onset contains a different anomaly, say so, report it separately, and choose
an earlier steady-state window as the baseline.

The cause is confirmed only when its evidence is present **and** the lookalike's evidence
is absent.

## Table

| Symptom | Cause | Discriminating evidence | Lookalike to rule out |
|---|---|---|---|
| Writes fail, `OOM` errors | Memory full and nothing evictable: `noeviction`, or a `volatile-*` policy with no keys that have a TTL | Memory at ~100% of maxmemory, **evictions = 0** (quote it), `OOM` error replies, the policy value, and `CurrVolatileItems` (keys with a TTL) | Eviction policy working (evictions > 0, no `OOM`). Fix: if `CurrVolatileItems` is 0, `volatile-lru` frees nothing, so recommend `allkeys-lru` for a pure cache, deleting keys, or more capacity |
| Keys disappear, hit rate drops | Evictions: working set larger than memory | Evictions > 0 and rising while memory sits at max; expirations flat | TTL expiry (expirations up, evictions 0); cold cache after a failover or node replacement (event, item count drop) |
| Latency up, every shard | Engine saturation | Main-thread CPU ≥ 90% (`EngineCPUUtilization`), throughput up, **per-command latency flat** vs baseline | Expensive commands (next row); network allowance exceeded; swap |
| Latency spikes, periodic | Expensive O(N) commands (`KEYS`, `HGETALL`/`SMEMBERS`/`LRANGE` on big keys, `SORT`, scripts) | One command's average latency far above the others; matching slow log entries at the spike times | Saturation (all commands slow together) |
| Latency or CPU on **one shard** | Key-distribution skew: hot key, shared hash tag, or one growing key | One node ≥ 1.5x the median in throughput or engine CPU; the command family that dominates on it names the data type. To name the key, recommend `CLUSTER SLOT-STATS ORDERBY CPU-USEC LIMIT 10` then `CLUSTER GETKEYSINSLOT` (Valkey 8+, cluster mode); `--hotkeys`/`OBJECT FREQ` only under an LFU policy; never `MONITOR` on a primary | Undersized node type: all nodes within ~15 points of each other. Fix skew with client-side caching or by splitting the key; scaling up or adding shards does not fix one hot key |
| One shard's memory high or climbing | Hash-tag concentration, a big key, or an unbounded collection (a list, set or stream that is never trimmed or expired) in one slot | Memory spread > 15 points between primaries. Linear growth on one shard (OTel `deriv`/`predict_linear` on `valkey.memory.used`) means an unbounded collection; project when it reaches maxmemory | Uniform memory pressure (all primaries within ~10 points) |
| Memory grows faster than key count | Big keys | Bytes per item (`BytesUsedForCache` / `CurrItems`) rising; `NetworkBytesOut` spikes on one node with engine CPU; slow log shows `HGETALL`/`LRANGE`/`SMEMBERS` | Many small keys: bytes per item flat |
| Command timeouts, cluster looks healthy | Client command or socket timeout too tight for the full round trip | Engine CPU low, connections steady, no errors, server latency (`SuccessfulReadRequestLatency`/`SuccessfulWriteRequestLatency` p99 and maximum) normal. These metrics are server-side only: the client also pays the network round trip, TLS and its own processing, often several hundred µs and more across AZs. A timeout of a few milliseconds or less can fail normal requests even when server latency is in µs. Compare the client's timeout with its observed round trip (client p99 and maximum); if either is unknown, report it as the key missing fact and ask for it. Note the client and node AZs from the deployment details | Connection churn (new connections high); engine saturation (CPU high); network allowance exceeded. Fix: raise the timeout to a safe multiple of the client's observed maximum round trip. Do not recommend a bigger node |
| Timeouts in bursts that get worse | Retries without backoff amplifying a brief stall | Short bursts where command rate and new connections jump many times above the steady level right after a small latency or CPU blip, then repeat; the user-facing request rate did not change | Steady connection churn (no bursts); a real traffic increase (application requests rose too). Fix: exponential backoff with jitter, a retry cap, a circuit breaker |
| Latency up, engine CPU low | Network limit on the node, or requests queuing in a too-small client pool | Network allowance exceeded > 0 (`NetworkBandwidthIn/OutAllowanceExceeded`, `NetworkPacketsPerSecondAllowanceExceeded`, `NetworkConntrackAllowanceExceeded`; OTel `system.network.allowance_exceeded` by reason), or p99 network rate near `system.network.bandwidth.limit`. If network is clean too, the queue is in the client | Engine saturation (CPU high); expensive commands. Fix for network: larger or network-optimized node type, spread traffic across shards, smaller payloads |
| Current connections climb steadily | Connection leak or unbounded client pool | `CurrConnections` (OTel `valkey.clients.connected`) rising for hours without a matching rise in commands; later `maxclients` and rejected connections | Real traffic growth (commands grow in proportion). Fix: bound the pool, close connections, set the `timeout` parameter for idle clients |
| Connection errors or timeouts | `maxclients` reached | Connected clients near the limit (65,000 on most node types), rejected connections > 0 | Connection churn |
| Connection timeouts, CPU up | Connection churn: no pooling, a new TLS connection per request | New connections per second very high (`NewConnections`; OTel `rate(valkey.connections.received)`) while current connections stay flat; handshake commands (`HELLO`, `CLIENT SETINFO`, `AUTH`, `PING`) at a high rate with no data commands; no rejections | `maxclients` (rejections > 0); security group change (CloudTrail, connections drop to 0) |
| Stale reads from replicas | Replication lag | `ReplicationLag` (seconds) up on replicas. Cause: a snapshot (`SaveInProgress`, snapshot event), a write burst on the primary, or a broken link (`MasterLinkHealthStatus`/`link_healthy` = 0, full resync) | Application reading through a cache layer with its own TTL |
| Brief outage, then errors | Failover or maintenance | Failover/replacement event at the onset; node role flip (`IsMaster` / `is_primary`). If errors persist **after** failover completes, the client is the cause: cached DNS, a pinned node endpoint, or a cluster client without topology refresh | Network or client-side failure (no event, no role change) |
| Authentication errors, often at regular intervals | IAM auth token expired, or ElastiCache closing IAM-authenticated connections after 12 hours | `IamAuthenticationExpirations` > 0, `AuthenticationFailures` rising (OTel `valkey.acl.denied` with reason `auth`); failures repeat about every 12 hours of connection age, or appear when a client reuses a token older than 15 minutes to reconnect | Wrong password or user (failures constant from the start, no expirations); missing `elasticache:Connect` permission. Fix: generate a fresh token for every new connection and reconnect before 12 hours |
| Clients cannot connect after a change, no engine errors | In-transit encryption mismatch between client and cache | `TransitEncryptionEnabled`/`TransitEncryptionMode` on the cache versus the client's TLS setting; a CloudTrail `ModifyReplicationGroup` that set `TransitEncryptionMode` to `required` at the onset; connections from that client drop to 0 while the cache is healthy | Security group change (CloudTrail on the group); failover (event). Fix: enable TLS in the client, or move through `preferred` before `required` |
| Serverless commands throttled | ECPU usage limit reached | `ThrottledCmds` > 0 while `ElastiCacheProcessingUnits` sits at `CacheUsageLimits.ECPUPerSecond.Maximum` | Client timeouts without throttling |
| A specific engine error reply | Read [error-strings.md](error-strings.md) | | |

## Stop conditions

- Engine CPU below 60% and stable connections: the cause is not capacity or
  connections. Look at commands and the slow log.
- Evictions 0 and memory below 70%: eviction is not the cause.
