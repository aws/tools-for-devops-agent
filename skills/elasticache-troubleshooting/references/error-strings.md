# ElastiCache engine error replies

The customer may quote the error, or it shows in `valkey.errors` by `valkey.error.type`
(node-based Valkey). Confirm the cause with the listed evidence before reporting it.

| Error prefix | Meaning | Confirm with | Fix (operator-run) |
|---|---|---|---|
| `OOM` | Write rejected: memory at maxmemory under `noeviction` | Memory ~100%, evictions 0, `maxmemory-policy` | Set an eviction policy (`allkeys-lru` for pure caches), add TTLs, scale up or add shards |
| `MOVED` / `ASK` | Cluster redirect | Rate: low and steady is normal; high or rising means the client is not cluster-aware, has a stale slot map, or resharding is running (event) | Use a cluster-aware client against the configuration endpoint |
| `CROSSSLOT` | Multi-key command whose keys hash to different slots | Error rate with `ClusterEnabled = true` | Hash tags `{...}` for keys used together, or split the command |
| `READONLY` | Write sent to a replica in **cluster mode disabled** (or after a client sent `READONLY`) | Failover event and role flip at the onset, or client configured with a replica/reader endpoint | Write through the primary endpoint, not a node endpoint; keep DNS TTL short; reconnect on `READONLY` |
| `CLUSTERDOWN` | Slots not served | Failover or node replacement event, shard without a primary | Wait for failover; check `AutomaticFailover` and replicas per shard |
| `LOADING` | Node loading its dataset after restart or full sync | Reboot, replacement or failover event | Retry with backoff |
| `BUSY` | Long-running Lua script or function | Script latency (`EvalBasedCmdsLatency`), slow log `EVAL*`/`FCALL` | Shorten the script |
| `NOAUTH` / `WRONGPASS` | Authentication missing or wrong | `AuthenticationFailures`, `valkey.acl.denied` reason `auth` | Fix credentials; IAM tokens expire after 15 minutes and connections after 12 hours |
| `NOPERM` | Authenticated user lacks permission | `CommandAuthorizationFailures` / `KeyAuthorizationFailures`, `valkey.acl.denied` reason `cmd`/`key` | Fix the user's access string |
| `WRONGTYPE` | Command run against a key of another type | Error rate only | Application bug |
| `ERR max number of clients reached` | `maxclients` hit | Connected clients near the limit, rejected connections > 0 | Pool connections, close idle ones, add nodes |
