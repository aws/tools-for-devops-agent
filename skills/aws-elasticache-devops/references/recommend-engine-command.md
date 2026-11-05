# Engine-side follow-ups (operator-run)

The agent cannot connect to the cache. When metrics have narrowed the cause, but only
engine data can name the key, slot or client, recommend these commands for the operator
to run. Each entry says what result confirms the hypothesis. Use the most specific
command the deployment supports. Node-based ElastiCache blocks `CONFIG` and `DEBUG`.

## Recommend a command in this form

- **Command:** the exact command line.
- **Where:** the node endpoint and its role (primary or replica), and why that node.
- **Cost on the node:** what the command does to the engine, and why it is safe there.
- **What confirms the cause:** the result that confirms or rules out the hypothesis.
- **Next step:** what the operator does with the result.

## Never recommend these

| Command | Why |
|---|---|
| `MONITOR` on a primary | A single `MONITOR` client can reduce throughput by more than 50% |
| `KEYS <pattern>` | O(N) over the keyspace; the Valkey documentation says to use it in production only with extreme care. Use `SCAN` |
| `FLUSHALL`, `FLUSHDB` | They delete data |
| `DEBUG`, `CONFIG` | Restricted on ElastiCache; use the parameter group |
| `HGETALL`, `SMEMBERS`, `LRANGE 0 -1` on a key you suspect is big | Each returns the whole value in one call, in O(N); use `HMGET`, bounded ranges or `SSCAN` |
| `DEL` on a big key | It frees the memory on the main thread; use `UNLINK` |
| One `LTRIM`, `ZREMRANGEBYRANK` or `XTRIM` that removes millions of elements | The cost grows with the number of elements removed; trim in steps |
| `MEMORY USAGE <key> SAMPLES 0` | It samples every nested value; keep the default sample count |

Deleting or trimming data is the data owner's decision: recommend it only with the
condition that the data can be lost, and say what is lost.

## Hot key (one shard hot)

1. **Valkey 8.0+ with cluster mode enabled:** on the hot shard's primary,
   `valkey-cli -h <node> -p 6379 --tls CLUSTER SLOT-STATS ORDERBY KEY-COUNT LIMIT 10`.
   `CPU-USEC`, `NETWORK-BYTES-IN` and `NETWORK-BYTES-OUT` can also be used for
   `ORDERBY`, but the engine reports them only when `cluster-slot-stats-enabled` is on;
   if they return 0, rely on `KEY-COUNT`. One slot far above the rest points to a hot
   slot. Then run `CLUSTER GETKEYSINSLOT <slot> 100` to list candidate keys.
2. **LFU eviction policy only** (`allkeys-lfu`/`volatile-lfu`): `OBJECT FREQ <key>` per
   candidate, or `valkey-cli --hotkeys`. Both need an LFU policy; under other policies
   `OBJECT FREQ` returns an error.
3. **Otherwise:** have the application log command and key pairs for a short period.
4. **Never** run `MONITOR` on a primary. The Valkey documentation shows a single
   `MONITOR` client reducing throughput by more than 50%.

Remediation, in order of preference: client-side caching with a short TTL, splitting
the key (`hot:1..N`), reads from replicas, then decomposing the value.

## Big or growing key (one shard's memory grows while its key count stays flat)

Use this first whenever memory grows faster than the key count, whatever the engine
version. It looks at individual keys, so it finds one growing list even when every key
shares one slot.

1. **Where to run it.** The samplers are client-side `SCAN` loops that also read each
   key's type and size from the node they connect to, so they add load on that node.
   - **A replica of the affected shard**, when the shard has one. `valkey-cli` sends
     `READONLY` itself in cluster mode.
   - **The primary, only when the shard has no replica**, off-peak and throttled with
     `-i 0.1`. In the samplers, `-i` pauses for that many seconds after every 100 `SCAN`
     calls.
2. **The samplers:**
   - `valkey-cli -h <node> -p 6379 --tls --memkeys -i 0.1`: the keys that use the most
     memory, by type. It calls `MEMORY USAGE` for each key it samples.
   - `valkey-cli -h <node> -p 6379 --tls --bigkeys -i 0.1`: the keys with the most
     elements, by type.

   A sampler sees only the node it connects to: run it on each node whose shard is in
   question. One key far above the rest (for example a list with millions of elements)
   confirms a big or growing key. Run the command again a few minutes later: a key whose
   size keeps rising is a collection that is never trimmed or expired.
3. `MEMORY USAGE <key>` on a candidate gives its exact bytes.
4. For streams, `XINFO GROUPS <key>`: a pending count that keeps growing means consumers
   are not acknowledging entries.

On serverless, `MEMORY` commands are blocked, so `--memkeys` and `MEMORY USAGE` cannot
work. `--bigkeys` does not use them, but this has not been tested on serverless: rely on
CloudWatch metrics and application-side instrumentation.

Remediation. Deleting or trimming removes data, so recommend it only with the data
owner's confirmation that the data can be lost, and say what is lost.

- **Remove a key with `UNLINK`, not `DEL`.** `DEL` frees the memory of a big key on the
  main thread. `UNLINK` removes the key from the keyspace at once and reclaims the memory
  in a different thread ([UNLINK](https://valkey.io/commands/unlink/),
  [DEL](https://valkey.io/commands/del/)).
- **Trim in steps.** The cost of `LTRIM` grows with the number of elements it removes
  ([LTRIM](https://valkey.io/commands/ltrim/)). Remove a collection in several smaller
  `LTRIM`, `ZREMRANGEBYRANK` or `XTRIM` calls instead of one call that removes millions
  of elements, and watch main-thread CPU between steps.
- Set a TTL (`EXPIRE`) or a maximum length on the collection, and fix the code that
  writes it.
- Split the value, replace `HGETALL`/`LRANGE 0 -1`/`SMEMBERS` with `HMGET`/bounded
  ranges/`SSCAN`, compress, or move large objects to S3.

## Many keys concentrated on one shard (memory and key count both high)

- Valkey 8.0+ cluster mode: `CLUSTER SLOT-STATS ORDERBY KEY-COUNT LIMIT 20` on that
  shard's primary. `SLOTSRANGE` and `ORDERBY` cannot be combined, and the only
  `ORDERBY` statistics are `KEY-COUNT`, `CPU-USEC`, `NETWORK-BYTES-IN` and
  `NETWORK-BYTES-OUT`; there is no memory statistic. One slot with far more keys than
  the rest means hash-tag concentration: keys sharing a `{tag}` all land in one slot.
  Then `CLUSTER GETKEYSINSLOT <slot> 100` lists the keys.
- Older engines: `--memkeys` on the shard's replica, then `CLUSTER KEYSLOT <key>` on the
  largest keys.

Remediation: redesign the hash tag (for example `{tenant}:{0-15}`), move an oversized
tenant to its own cache, or reshard online. Scaling up only postpones the problem.

## Slow commands: naming the key and the client

Delivered slow logs (CloudWatch Logs or Firehose) **replace the key and arguments** with
`... (N more arguments)`. They show the command name, `Duration (us)`, `ClientAddress`
and `ClientName`. To see the keys:

- `SLOWLOG GET 128` on the node (node-based only).
- `COMMANDLOG GET 128 slow` (Valkey 8.1+, node-based only). `large-request` and
  `large-reply` instead of `slow` list commands with large requests or replies.
- Match `ClientAddress` against `CLIENT LIST` to find the application instance. If the
  connection is gone, use VPC Flow Logs for that source IP.

## Blocked on serverless

ElastiCache Serverless blocks, among others, `KEYS`, `OBJECT`, `MEMORY`, `LATENCY`,
`SLOWLOG`, `COMMANDLOG`, `MONITOR`, `CLIENT LIST` and `CLIENT KILL`, and has no log
delivery. On serverless, rely on CloudWatch metrics and application-side
instrumentation.
