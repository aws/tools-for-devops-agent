# A8: Backup and restore

**Problem it solves:** Backups fail, run out of memory or are exposed. Backups that run as a Kubernetes Job or ECS
task leave their output and stop reason where the agent can read them; `neo4j-admin` writes to its own console, not
the server's debug.log.

**Where backups run.** EKS: the `neo4j-admin` Helm chart creates a CronJob (values `backup.heapSize`,
`backup.pageCache`, `backup.cloudProvider`, `backup.bucketName`, `resources`); look at its Jobs and pod logs. ECS: a
scheduled task (EventBridge Scheduler or rule) running `neo4j-admin database backup`; its log group and stopped-task
reason. AWS Backup jobs for EBS snapshots are separate and visible through `backup list-backup-jobs`; a snapshot of a
running store is crash-consistent, not a Neo4j backup.

## A8.1 Backup job runs out of memory

**Signature:** backup Job pod `OOMKilled` with exit 137, or the ECS scheduled task stopped with
`OutOfMemoryError: container killed due to memory usage`; slow backups with heavy GC.

**Cause:** `neo4j-admin database backup` starts its own JVM. Without explicit sizing it takes a JVM default heap and a
page cache derived from the configuration it reads, which can be sized for the server rather than the backup container.

**Check:** Job/task memory limit vs `HEAP_SIZE` (or the chart's `backup.heapSize`) and `--pagecache`
(`backup.pageCache`).

**Fix (operator):** Set both explicitly so heap + page cache fit the backup container with headroom, for example
`HEAP_SIZE=2g neo4j-admin database backup --pagecache=2g ...`.

## A8.2 Backup fails on SSL policy base directory

**Signature:** backup output
`Base directory '...' for SSL policy with name '...' does not exist.` The 3.x variant named the `default` policy,
which no longer exists.

**Cause:** `neo4j-admin` reads neo4j.conf in the backup container; an enabled SSL policy (for example `backup` or
`cluster`) points at a directory that isn't mounted there.

**Fix (operator):** Mount the same certificates in the backup container, or give the backup its own configuration via
`--additional-config` with only the policies it needs.

## A8.3 Restore in containers

**Symptom:** a restore is needed and Neo4j is the container's main process.

**Fix (operator):** `neo4j-admin database restore` needs the target database stopped, not necessarily the server:
`STOP DATABASE <db>`, restore with `--overwrite-destination=true`, then `START DATABASE <db>` (or `CREATE DATABASE` for
a new name). When the whole server must be down, use the Helm chart's `neo4j.offlineMaintenanceModeEnabled: true`
(the pod runs without the Neo4j process) or, on ECS, scale the service to 0 and run a one-off task with the same volume
and a `neo4j-admin` command override. A database can also be seeded from a backup in S3 with
`CREATE DATABASE <db> OPTIONS {seedURI: 's3://...'}`.

## A8.4 Backup port exposed

**Symptom:** port 6362 reachable from outside the backup network.

**Cause:** The backup protocol doesn't authenticate users; anyone who reaches the port can copy the database. Neo4j
2026.10 listens on `127.0.0.1:6362` by default, but the Helm chart sets `server.backup.listen_address: 0.0.0.0:6362`
when backups are enabled on Enterprise, so exposure depends on Services and network rules.

**Check:** Services or NLB listeners with port 6362; security group rules allowing 6362 from broad CIDRs; the listen
address.

**Fix (operator):** Allow 6362 only from backup hosts (security groups, NetworkPolicy), don't publish it on a load
balancer, and require mutual TLS with `dbms.ssl.policy.backup.enabled=true` and `client_auth=REQUIRE`.
