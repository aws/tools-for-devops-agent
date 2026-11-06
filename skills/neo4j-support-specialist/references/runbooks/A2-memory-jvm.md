# A2: Memory, JVM and GC

**Problem it solves:** Neo4j is killed or stops answering because heap, page cache and native memory don't fit the
container or the workload. A container memory kill leaves no log line, only `OOMKilled` and exit 137. A heap
`OutOfMemoryError` leaves the container running but unresponsive, with the error on stderr. The agent compares the
configured heap and page cache with the container limit.

**Memory model.** Neo4j memory is the sum of heap (`server.memory.heap.max_size`), page cache
(`server.memory.pagecache.size`) and native memory outside both (Lucene-backed full-text and vector indexes, Netty
buffers, thread stacks, metaspace, JIT). The container limit must cover all three. There's no fixed headroom figure:
native memory grows with full-text and vector indexes, connections and threads, and
`neo4j-admin server memory-recommendation` gives the split for a given memory size. When heap is unset, the JVM picks
a fraction of the container memory, so an unset heap is itself a finding on a dedicated Neo4j container. Initial heap
should equal max heap, so the JVM doesn't run full collections while it resizes the heap.

Where to read the settings: EKS ConfigMaps (`<release>-user-config` overrides `-default-config`); ECS
`NEO4J_server_memory_heap_max__size`, `NEO4J_server_memory_heap_initial__size`,
`NEO4J_server_memory_pagecache_size`; the debug.log startup dump (JVM memory, physical memory) if shipped. Container
limit: StatefulSet `resources.limits.memory`, ECS container `memory` or task `memory`.

## A2.1 Container memory limit reached (OOMKilled)

**Signature:** pod `lastState.terminated.reason: OOMKilled`, exit 137; on ECS the stopped task's
`containers[].reason` is `OutOfMemoryError: container killed due to memory usage` with exit 137, while the task's
`stoppedReason` only says `Essential container in task exited`. Container output has no error at all: it ends at the
startup lines. On EC2 the serial console shows kernel memory messages such as
`__vm_enough_memory: ... comm: java, bytes: <n> not enough memory for the allocation`; a kernel
`Out of memory: Killed process <pid> (java)` line may appear when the kernel kills the JVM, but isn't confirmed.
When heap + page cache fill an EC2 host without swap, the kernel may never kill anything: the host thrashes instead.
Signs: EBS `VolumeReadBytes` pinned at the volume's throughput cap with almost no writes, CPU well above its
baseline, SSM `PingStatus` `ConnectionLost`, and EC2 status checks still passing.

**Cause:** The kernel kills the JVM when total process memory exceeds the cgroup limit. Typical reasons: heap + page
cache set close to the limit with no room for native memory; heap unset and page cache set large; full-text or vector
indexes growing native memory; a sidecar sharing the task memory.

**Check:**

1. Compare heap + page cache with the container limit and state the remainder in MiB. Flag a remainder that leaves
   little room for native memory given the indexes in use, and give the operator the memory-recommendation command
   to confirm it.
2. Restart count and the times of each kill; correlate with query load or batch jobs (CloudWatch metrics, CronJobs).
3. Container Insights: EKS `pod_memory_working_set` against the limit, ECS `MemoryUtilized` against `MemoryReserved`.
4. ECS: other containers in the same task and whether the Neo4j container has its own `memory` hard limit.

**Fix (operator):** Size with `neo4j-admin server memory-recommendation --memory=<container limit> --docker` and set
heap and page cache explicitly, leaving headroom for native memory. Raise the container limit if the store needs a
larger page cache. Set initial heap equal to max heap.

## A2.2 Heap OutOfMemoryError leaves the server degraded

**Signature:** container output (stderr)
`java.lang.OutOfMemoryError thrown from the UncaughtExceptionHandler in thread ...` or
`java.lang.OutOfMemoryError: Java heap space`. The container keeps running (exit code stays 0, no restart) and stops
answering; clients time out or get `Server ... is no longer available`. Nothing in neo4j.log or debug.log.

**Cause:** The heap filled (large transactions, unbounded queries, too small a heap). Neo4j 2026.10 doesn't set
`-XX:+ExitOnOutOfMemoryError` by default, so after the error the JVM keeps running in an undefined state. The Helm
chart's TCP probes still pass, so Kubernetes doesn't restart it.

**Check:**

1. Search container output for `OutOfMemoryError` (see [log-queries.md](../log-queries.md)).
2. Is `-XX:+ExitOnOutOfMemoryError` (or `-XX:+CrashOnOutOfMemoryError`) in `server.jvm.additional`?
3. If query.log is shipped, find the queries running at that time with high allocated bytes ([A4](A4-query-transactions.md)).
4. Is `dbms.memory.transaction.total.max` or `db.memory.transaction.max` set so that one transaction can't take the
   heap?

**Fix (operator):** Restart the server now. Add `-XX:+ExitOnOutOfMemoryError` to `server.jvm.additional` so the
orchestrator restarts a broken JVM, and optionally `-XX:+HeapDumpOnOutOfMemoryError` with a dump path on a volume
with space. Then fix the cause: limit transaction memory, batch large writes, size the heap.

## A2.3 Memory sizing doesn't match the workload

**Symptom:** no dedicated message. Neo4j 2026.x doesn't refuse a heap or page cache larger than the container or host:
the container is OOM-killed (A2.1), or on EC2 the service exits 1 with `Neo4j web server failed to start`. Don't
expect an `Invalid memory configuration - exceeds physical memory` message. Otherwise the symptoms of A2.1, A2.2 or
A3.5 (page faults).

**Cause:** Heap, page cache and OS reserve weren't derived from the store size and the workload. A page cache much
smaller than the store means page faults and disk reads; a heap too small for the query mix means GC pressure and
OOM.

**Check:** Settings vs limit; volume size and, if shipped, store and index sizes in the debug.log startup dump; page
faults per query in query.log ([A3.5](A3-disk-storage.md)).

**Fix (operator):** `neo4j-admin server memory-recommendation --memory=<limit> --docker` as a starting point. Page
cache close to store size plus expected growth when it fits; heap sized for concurrent query memory. See
[operator-queries.md](../operator-queries.md).

## A2.4 Memory used outside the page cache

**Symptom:** container memory well above heap + page cache, ending in A2.1, on deployments with full-text or vector
indexes. Index types and sizes are only in the debug.log startup dump; otherwise ask the operator for `SHOW INDEXES`.

**Cause:** Lucene-backed indexes (full-text, vector) keep data in memory-mapped files and native memory, not in the page
cache. Memory sized as heap + page cache doesn't account for them.

**Check:** Working set minus (heap + page cache); index types in the startup dump or from the operator.

**Fix (operator):** Leave native headroom proportional to Lucene index size, or raise the container limit. Run
`SHOW INDEXES YIELD name, type, state, populationPercent` to list index types.

## A2.5 Native thread exhaustion

**Signature:** container output `java.lang.OutOfMemoryError: unable to create native thread: possibly out of memory or
process/resource limits reached`. Not confirmed on 2026.x; match on `unable to create native thread`.

**Cause:** Each Bolt connection being served uses a worker thread, up to `server.bolt.thread_pool_max_size`
(default 400), on top of internal threads. A process or PID limit below that, or a connection storm, stops thread
creation.

**Check:** `ulimits` in the task definition; `server.bolt.thread_pool_max_size`; connection storms in client logs or
NLB `ActiveFlowCount`/`NewFlowCount` metrics; thread starvation errors ([A5.12](A5-connectivity-drivers.md)).

**Fix (operator):** Raise the process limit, cap client connection pools, and keep `thread_pool_max_size` within it.

## A2.6 Long GC pauses

**Signature:** debug.log WARN `Detected VM stop-the-world pause: {pauseTime=<ms>, gcTime=<ms>, gcCount=<n>}` from the
VM pause monitor. Whether it also reaches container output isn't confirmed. GC logging
(`server.logs.gc.enabled`) is off by default. Without debug.log, only the effects show: CPU throttling, leader
changes, client timeouts, member restarts.

**Cause:** Heap under pressure (large transactions, too small a heap, heap set larger than needed with long full
collections), or CPU throttling stretching collections. Pauses longer than the Raft leader failure detection window
(`dbms.cluster.raft.leader_failure_detection_window`, default 20s to 23s) cause leader re-elections.

**Check:**

1. If debug.log is shipped: count and maximum `pauseTime` per member ([log-queries.md](../log-queries.md)). On a
   cluster, compare the longest pauses with the configured leader failure detection window; on a standalone server,
   with the client and transaction timeouts.
2. CPU limits and throttling (Container Insights), heap size, and whether pauses line up with batch jobs.

**Fix (operator):** Reduce heap pressure (batch writes, transaction memory limits), size the heap from the
recommendation, give the container enough CPU for GC threads. Enable GC logging temporarily for Neo4j Support
(`server.logs.gc.enabled=true`).
