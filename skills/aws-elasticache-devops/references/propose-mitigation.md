# Mitigations the agent can apply after approval

Read this file in Step 6, only when the operator asks you to apply a fix. Each row is a
single ElastiCache API operation for a confirmed cause. Everything outside this table is
an operator-run action: data commands (`LTRIM`, `DEL`, `EXPIRE`), client changes,
application code, and deletions.

Applying a change needs AWS DevOps Agent directed actions: agent actions enabled on the
Agent Space, an actions role registered on the AWS account, and the operator's approval
of each action in chat. Without them, give the operator the manual steps.

## Rules

- Confirm the cause first. A mitigation for the wrong cause is worse than none.
- Change a **custom** parameter group only. Default parameter groups (`default.*`)
  cannot be modified: say so, and recommend that the operator creates a custom group
  and attaches it to the cluster.
- A parameter group can be shared by several clusters, and a change applies to all of
  them. Before changing it, list the clusters that use it
  (`describe_cache_clusters`, field `CacheParameterGroup.CacheParameterGroupName`) and
  name them in the proposal.
- Record the current value from `describe_cache_parameters` before the change; it is
  the rollback value.
- **The agent never removes capacity.** Scale-in, removing a shard, removing a replica
  and removing any node are operator-run, and so is every rollback that removes
  capacity. Give the operator the rollback command as a manual step.

## Table

| Confirmed cause | Operation and parameters | Pre-check (read-only) | Verify | Rollback |
|---|---|---|---|---|
| `OOM` writes under `noeviction` (or `volatile-*` with no keys that have a TTL) on a **pure cache** | `ModifyCacheParameterGroup`: `maxmemory-policy` = `allkeys-lru`. The change takes effect immediately, without a reboot | Memory at ~100% of maxmemory; `OOM` error replies > 0; evictions = 0; `CurrVolatileItems` = 0 for `volatile-*`; the operator confirms the data can be evicted (a cache, not a primary store) | `OOM` errors fall to 0 and evictions rise above 0 on the affected primaries; memory stays at the limit, as expected under LRU | `ModifyCacheParameterGroup`: `maxmemory-policy` back to the recorded value |
| Idle connections near `maxclients` from a leak | `ModifyCacheParameterGroup`: `timeout` = a number of seconds (20 or more) longer than the longest idle period the application needs. The change takes effect immediately | `timeout` is 0 (never disconnect idle clients); connected clients near the limit. The operator confirms that no normal client is legitimately idle for longer than the new value: a connection idle for longer is closed and the client must reconnect, which includes pooled connections that sit idle between bursts. The Valkey documentation says the timeout does not apply to Pub/Sub clients, and its source skips replica links and clients blocked in a blocking command such as `BLPOP` ([client handling](https://valkey.io/topics/clients/), [timeout.c](https://github.com/valkey-io/valkey/blob/8.1.0/src/timeout.c#L56-L62)); say so, and ask whether any other client stays idle for long | Connected clients fall; rejected connections stop | `timeout` back to the recorded value |
| **Node-based, uniform memory pressure:** memory near maxmemory on every primary, and the key count grows along with memory (no single large or growing key). Cluster mode enabled | `ModifyReplicationGroupShardConfiguration`: `NodeGroupCount` = current + 1, `ApplyImmediately` = true. Online resharding moves slots while the cluster serves traffic; its duration depends on data size and load | Quote each primary's memory %: all similar, no hot shard. `CurrItems` rising with memory on every primary. The operator confirms no single collection is growing without limit (see recommend-engine-command.md). Engine main-thread CPU below 80% on multicore nodes, or below 50% on single-core nodes (AWS guidance for resharding); above that, stop: the case is operator-only (next row) | Per-shard memory falls as slots move; the group returns to `available` | **Operator-run, not by the agent:** `ModifyReplicationGroupShardConfiguration` with a lower `NodeGroupCount` and `NodeGroupsToRemove` or `NodeGroupsToRetain`, once the retained shards have free memory of at least 1.5 times the memory used on the shards to remove |
| **Node-based, engine saturation on every shard** (main-thread CPU at or above 90%) | **Operator-only for now:** resharding and changing the node type both add load while they run, so it is not established which capacity change is safe at this CPU. Report the evidence and the options, and let the operator choose | | | |
| **Node-based, replica reads saturated** on a read-heavy workload | `IncreaseReplicaCount`: + 1 per shard, `ApplyImmediately` = true | Replica engine CPU high, primary normal; clients read from replicas (reader endpoint, or `READONLY` in cluster mode); a shard has fewer than 5 replicas. Replicas serve reads only, so if the load is writes, stop | Replica engine CPU falls once the new replica is in sync and receiving reads | **Operator-run, not by the agent:** `DecreaseReplicaCount` |
| **Serverless, throttled at the ECPU maximum** | `ModifyServerlessCache`: `CacheUsageLimits.ECPUPerSecond.Maximum` = a higher value, stated in the proposal for the operator to approve | `describe_serverless_caches` shows the current maximum (record it as the rollback value). `ThrottledCmds` > 0 while `ElastiCacheProcessingUnits` sits at that maximum. If processing units stay below the maximum, the throttling comes from a fast ramp or from one slot at its own limit (30,000 ECPU/s, or 90,000 with read from replica): stop. The operator confirms the load is not concentrated on one key or slot | `ThrottledCmds` falls to 0; `ElastiCacheProcessingUnits` rises above the old maximum | **Operator-run, not by the agent:** `ModifyServerlessCache` with the recorded maximum (lowering a limit removes capacity) |
| **Serverless, `OOM` at the data storage maximum** | `ModifyServerlessCache`: `CacheUsageLimits.DataStorage.Maximum` = a higher value, with `Unit` = `GB`, stated in the proposal | `describe_serverless_caches` shows the current maximum (record it). `BytesUsedForCache` is at that maximum. If it is below the maximum, the limit hit is the per-slot one (32 GiB) and the cause is concentration in one slot: stop. The operator confirms the growth is many keys, not one collection that is never trimmed | `BytesUsedForCache` rises above the old maximum. Serverless has no error-count metric, so the operator confirms that the application's write errors stop | **Operator-run, not by the agent:** `ModifyServerlessCache` with the recorded maximum (lowering a limit removes capacity) |
| `OOM` from a list, set or stream that is never trimmed | **Operator-only:** trim or expire the collection (`LTRIM`, `EXPIRE`) and fix the writer. Changing the policy or adding capacity would only delay the `OOM` while the collection keeps growing | | | |
| Hot key or hash tag on one shard | **Operator-only:** spread the keys or cache client-side. Capacity does not spread one hot key | | | |
| Client timeout too tight | **Operator-only:** raise the client timeout. Nothing on the cache changes | | | |

## When capacity does not help

Do not propose a capacity change for these causes, even when the symptoms look like
pressure on the cache.

| Cause | Why capacity does not help | Do instead |
|---|---|---|
| Hot key or hot slot | A key lives in one slot, and one primary serves that slot. More shards or a larger node do not split it, and moving slots adds load while it runs | Client-side caching with a short TTL, or splitting the key |
| One collection that is never trimmed or expired | It keeps growing, so more memory only postpones the `OOM` | Trim or expire it, and fix the code that writes it |
| Client timeout too tight, or any other client-side cause | The cluster is healthy: engine CPU, memory and connections have headroom | Raise the client timeout from the client's measured round trip; fix the client |
