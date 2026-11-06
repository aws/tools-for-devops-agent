# Engine-side follow-ups (operator-run)

The agent cannot connect to the cache. When metrics have narrowed the cause, but only
engine data can name the key, slot or client, recommend these commands for the operator
to run. Each entry says what result confirms the hypothesis. Use the most specific
command the deployment supports.

## Hot key (one shard hot)

1. **Valkey 8.0+ with cluster mode enabled:**
   `valkey-cli -h <node> -p 6379 --tls CLUSTER SLOT-STATS ORDERBY CPU-USEC LIMIT 10`.
   It is subsecond and safe in production. One slot far above the rest confirms a hot
   slot. Then run `CLUSTER GETKEYSINSLOT <slot> 200` to list the candidate keys. If the
   top 10 slots are within 2x of each other, there is no single hot slot: suspect
   command cost instead.
2. **LFU eviction policy only** (`allkeys-lfu`/`volatile-lfu`): `OBJECT FREQ <key>` per
   candidate, or `valkey-cli --hotkeys`. A counter of 9 or more means a hot key. Under
   LRU policies both are meaningless.
3. **Otherwise:** have the application log command and key pairs for 5-10 minutes.
4. **Never** run `MONITOR` on a primary. It can cut throughput by more than 50%.

Remediation, in order of preference: client-side caching with a short TTL, splitting
the key (`hot:1..N`), reads from replicas, then decomposing the value.

## Big key (memory grows faster than key count, one node's NetworkBytesOut spikes)

- `valkey-cli -h <replica> -p 6379 --tls --bigkeys`: a client-side SCAN sampler that
  takes about 1-3 minutes per million keys. Run it on a **replica**, or off-peak on
  serverless (it consumes ECPUs).
- Node-based only: `MEMORY USAGE <key>` gives exact bytes. `DEBUG OBJECT` is blocked
  on ElastiCache.
- Size thresholds for "big": strings ≥ 100 KB, hashes, sets or sorted sets ≥ 1,000
  members, lists ≥ 10,000 items, streams ≥ 100,000 entries.
- For streams, `XINFO GROUPS <key>`: an old first entry plus a growing pending list
  means consumers are stuck.

Remediation: decompose the value, replace `HGETALL`/`LRANGE 0 -1`/`SMEMBERS` with
`HMGET`/bounded ranges/`SSCAN`, compress, or move blobs to S3. **Cluster mode:** slots
holding an item larger than 256 MB cannot be migrated, so decompose it before any
resharding or scale-out.

## One shard's memory high (spread > 15 points between primaries)

- Valkey 8.0+ cluster mode: `CLUSTER SLOT-STATS ORDERBY MEMORY-BYTES DESC LIMIT 20`, then
  `CLUSTER COUNTKEYSINSLOT <slot>`. A few keys holding a lot of memory means big keys.
  Many keys holding a lot of memory means hash-tag concentration: keys sharing a
  `{tag}` all land in one slot.
- Older engines: `--bigkeys` on the hot shard's replica, then `CLUSTER KEYSLOT <key>`.

Remediation: redesign the hash tag (for example `{tenant}:{0-15}`), move an oversized
tenant to its own cache, or reshard online. Scaling up only masks the problem.

## Slow commands: naming the key and the client

Delivered slow logs (CloudWatch Logs or Firehose) **redact keys and values**. They show
the command name, `Duration (us)`, `ClientAddress` and `ClientName`. To see the keys:

- `SLOWLOG GET 128` on the node (node-based only).
- `COMMANDLOG GET 128` (Valkey 8.1+): separates slow commands, large requests and
  large replies.
- Match `ClientAddress` against `CLIENT LIST` to find the application instance. If the
  connection is gone, use VPC Flow Logs for that source IP.

## Blocked on serverless

`OBJECT`, `MEMORY`, `LATENCY`, `SLOWLOG`, `COMMANDLOG`, `CONFIG`, `MONITOR`, `--hotkeys`
and `--memkeys` are blocked. `--bigkeys` works. On serverless, rely on CloudWatch
metrics and application-side instrumentation.
