# ElastiCache engine error replies

The customer may quote the error, or it shows in `valkey.errors` by `valkey.error.type`
(node-based Valkey; the type is the first word of the reply). Classic `ErrorCount`
gives the total of failed commands without the type. Confirm the cause with the listed
evidence before reporting it.

| Error prefix | Meaning | Confirm with | Fix (operator-run) |
|---|---|---|---|
| `OOM` | Write rejected: memory at maxmemory and nothing evictable (`noeviction`, or `volatile-*` with no keys that have a TTL; on serverless, the data storage maximum or a slot's 32 GiB limit) | Memory ~100%, evictions 0, `maxmemory-policy`, `CurrVolatileItems` | Add capacity, add TTLs and use a `volatile-*` policy, or `allkeys-lru` only if the data can be lost (not for login sessions or other state that exists only in the cache); trim a growing collection |
| `MOVED` / `ASK` | Cluster redirect to the node that owns the slot | Rate: a client may send a request to any node and be redirected ([cluster specification](https://valkey.io/topics/cluster-spec/)), so some redirects are normal; high or rising means the client is not cluster-aware, has a stale slot map, or resharding is running (event) | Use a cluster-aware client against the configuration endpoint |
| `CROSSSLOT` | Multi-key command whose keys hash to different slots | Error rate with `ClusterEnabled = true` | Hash tags `{...}` for keys used together, or split the command |
| `READONLY` | Write sent to a replica in **cluster mode disabled** | Failover event and role flip at the onset, or a client configured with a replica or reader endpoint | Write through the primary endpoint, not a node endpoint; reconnect on `READONLY` |
| `CLUSTERDOWN` | Slots not served | Failover or node replacement event, shard without a primary | Wait for failover; check `AutomaticFailover` and replicas per shard |
| `LOADING` | Node loading its dataset after a restart or full sync | Reboot, replacement or failover event | Retry with backoff |
| `BUSY` | Lua script running longer than `lua-time-limit` | Script latency (`EvalBasedCmdsLatency`), slow log `EVAL*`/`FCALL` | Shorten the script |
| `NOAUTH` / `WRONGPASS` | Authentication missing or wrong | `AuthenticationFailures`, `valkey.acl.denied` reason `auth` | Fix credentials. IAM tokens are valid for 15 minutes, and IAM-authenticated connections are disconnected after 12 hours unless re-authenticated |
| `NOPERM` | Authenticated user lacks permission | `CommandAuthorizationFailures` / `KeyAuthorizationFailures` / `ChannelAuthorizationFailures`, `valkey.acl.denied` reason `cmd`/`key`/`channel` | Fix the user's access string |
| `WRONGTYPE` | Command run against a key of another type | Error rate only | Application bug |
| `ERR max number of clients reached` | `maxclients` hit | Connected clients near the limit, `RejectedConnections` > 0 | Pool connections, close idle ones, add nodes |

In cluster mode, a replica redirects commands for its slots to the primary with `MOVED`,
so writes sent to a replica return `MOVED`, not `READONLY`. A cluster mode enabled cache
has a single configuration endpoint, and by connecting to it a client discovers the
primary and read endpoints of every shard
([endpoints](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Endpoints.html)), so a
cluster-aware client connects to each node endpoint after discovery. That is normal, not a
misconfiguration.
