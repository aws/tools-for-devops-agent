# A7: Clustering

**Problem it solves:** The cluster won't form, members fall behind, or routing ignores zones. A member that can't form
a cluster never logs `Started.` and fails its startup probe, which the agent sees. Raft and replication detail is only
in debug.log.

**What to read.** Cluster settings: `dbms.cluster.discovery.resolver_type` (`LIST`, `DNS`, `SRV`, `K8S`),
`dbms.cluster.endpoints` (for `LIST`, host:port of each member's `server.cluster.advertised_address`, port 6000),
`dbms.cluster.minimum_initial_system_primaries_count` (default 3), `initial.dbms.default_primaries_count`,
`initial.dbms.default_secondaries_count`, `dbms.cluster.raft.binding_timeout` (default 1d). On Helm each member is a
separate release sharing one `neo4j.name`; the `-default-config` ConfigMap sets `resolver_type: K8S`,
`dbms.kubernetes.label_selector` (`app=<name>,helm.neo4j.com/service=internals,...`) and advertised addresses from the
`-internals` Services, and discovery calls the Kubernetes API with the pod's service account. Ports between members:
6000 (cluster and discovery), 7000 (Raft), 7688 (server-side routing).

## A7.1 Secondary or primary lagging behind

**Symptom:** stale reads from some members; replication messages and catch-up in debug.log; operator output with a
non-zero `replicationLag`.

**Cause:** Sustained write load the member can't apply in time (CPU throttled, slower volume, smaller page cache, long
GC pauses), or network problems between members.

**Check:** Compare members' CPU throttling, EBS metrics ([A3.5](A3-disk-storage.md)) and GC pauses
([A2.6](A2-memory-jvm.md)); instance or node types differ between members?

**Fix (operator):** `SHOW DATABASES YIELD name, address, role, currentStatus, lastCommittedTxn, replicationLag` and
`CALL dbms.cluster.statusCheck(['<db>'])` to measure; give lagging members the same resources as the writer; batch
heavy writes.

## A7.2 Cluster formation timeout

**Signature:** container output never reaches `Started.` after the startup lines, and the container keeps
running. Bolt isn't listening, so the startup probe keeps failing. debug.log holds the discovery entries (category
`ListResolver` for `LIST`). The Helm startup probe allows 1000 × 5 s (about 83 minutes) before Kubernetes restarts
the pod, so a stuck member stays not-Ready for a long time.

**Cause:**

- Fewer members running than `dbms.cluster.minimum_initial_system_primaries_count` (Helm `minimumClusterSize`) on first
  start, for example one release not installed or pods pending.
- Endpoints that don't resolve or point at the wrong port: `dbms.cluster.endpoints` typos, DNS names not created yet.
- Helm: releases with different `neo4j.name`, missing `-internals` Services, or a service account without permission to
  list Services for `K8S` discovery.
- Ports 6000 or 7000 blocked between members (security groups, NACLs, NetworkPolicies).

**Check:**

1. Container output of every member: whether any reached `Started.`; debug.log discovery entries if shipped.
2. Pods pending or missing; number of members vs the minimum count.
3. `neo4j.name` label and the `-internals` Services across releases; `dbms.cluster.endpoints` for `LIST`.
4. Security groups for 6000 and 7000 between member nodes or tasks.

**Fix (operator):** Start all initial members together, align `neo4j.name` and minimum counts, fix endpoints or DNS,
and open the cluster ports. `CALL dbms.cluster.checkConnectivity()` from a started member checks the ports to the
others. Raising the binding timeout only helps when members are slow to arrive, not when they can't connect.

## A7.3 Raft handler not installed warnings

**Signature:** debug.log WARN `Unable to process message ... because handler for Raft ID ... is not installed`
(text unchanged on 2026.10).

**Cause:** A member receives Raft messages for a database that is offline or not started on it. Transient during
database start, stop or reallocation; persistent warnings mean the database isn't running on that member.

**Fix (operator):** If persistent, check the database on that member with `SHOW DATABASES` and start or reallocate it.

## A7.4 Raft E_COUNT_EXCEEDED warnings

**Signature:** debug.log `Raft in-queue dropping messages after: E_COUNT_EXCEEDED`, followed by
`Raft in-queue not dropping messages anymore. Dropped <n> messages.`

**Cause:** A follower's incoming Raft queue filled (`db.cluster.raft.in_queue.max_bytes`, default 2 GiB on 2026.10)
because it applies entries more slowly than the leader sends them. Short bursts during heavy writes recover on their own;
frequent ones point at an under-resourced member.

**Fix (operator):** Same as [A7.1](#a71-secondary-or-primary-lagging-behind): find what slows the follower.

## A7.5 Routing in multi-zone or multi-region deployments

**Symptom:** clients in one zone or region use distant members; cross-zone data transfer costs.

**Cause:** Without server tags and a routing policy, the routing table treats all members as equal.

**Fix (operator):** Tag servers (`initial.server.tags`, or `ALTER SERVER '<id>' SET OPTIONS {tags: [...]}`), define
policies with `dbms.routing.load_balancing.config.server_policies.<name>`, and have clients pass the policy in the
routing context (`neo4j://host?policy=<name>`).
