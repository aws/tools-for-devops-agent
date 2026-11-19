# Mitigations the agent can apply after approval

Read this file in Step 7, only when the operator asks you to apply a fix. Each row is a
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

## Table

| Confirmed cause | Operation and parameters | Pre-check (read-only) | Verify | Rollback |
|---|---|---|---|---|
| `OOM` writes under `noeviction` (or `volatile-*` with no keys that have a TTL) on a **pure cache** | `ModifyCacheParameterGroup`: `maxmemory-policy` = `allkeys-lru`. The change takes effect immediately, without a reboot | Memory at ~100% of maxmemory; `OOM` error replies > 0; evictions = 0; `CurrVolatileItems` = 0 for `volatile-*`; the operator confirms the data can be evicted (a cache, not a primary store) | `OOM` errors fall to 0 and evictions rise above 0 on the affected primaries; memory stays at the limit, as expected under LRU | `ModifyCacheParameterGroup`: `maxmemory-policy` back to the recorded value |
| `OOM` from a list, set or stream that is never trimmed | **Operator-only:** trim or expire the collection (`LTRIM`, `EXPIRE`) and fix the writer. Changing the policy would only evict other data while the collection keeps growing | | | |
| Idle connections near `maxclients` from a leak | `ModifyCacheParameterGroup`: `timeout` = a number of seconds (20 or more) longer than the longest idle period the application needs. The change takes effect immediately | `timeout` is 0 (never disconnect idle clients); connected clients near the limit; the operator gives the application's longest legitimate idle period | Connected clients fall; rejected connections stop | `timeout` back to the recorded value |
| Uniform memory pressure or engine saturation on **every** shard (no skew), cluster mode enabled | `ModifyReplicationGroupShardConfiguration`: `NodeGroupCount` = current + 1, `ApplyImmediately` = true. Online resharding moves slots while the cluster serves traffic; its duration depends on data size and load | All primaries carry similar load; no hot shard; no expensive command; CPU below 80% on multicore nodes or below 50% on single-core nodes (AWS guidance for resharding) | Per-shard memory or engine CPU falls as slots move; the group returns to `available` | `ModifyReplicationGroupShardConfiguration` with a lower `NodeGroupCount` and `NodeGroupsToRemove` or `NodeGroupsToRetain`, once the retained shards have free memory of at least 1.5 times the memory used on the shards to remove |
| Replica reads saturated on a read-heavy workload | `IncreaseReplicaCount`: + 1 per shard, `ApplyImmediately` = true | Replica engine CPU high, primary normal; clients read from replicas (reader endpoint, or `READONLY` in cluster mode); a shard has fewer than 5 replicas | Replica engine CPU falls once the new replica is in sync and receiving reads | `DecreaseReplicaCount` |
| Hot key or hash tag on one shard | **Operator-only:** spread the keys or cache client-side. Scaling does not spread one hot key | | | |
| Client timeout too tight | **Operator-only:** raise the client timeout. Nothing on the cache changes | | | |
