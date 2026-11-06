# A1: Startup, recovery and store integrity

**Problem it solves:** Neo4j won't start, restarts in a loop, or a database stays offline. Server-level failures stop
the container (exit 1) and print the cause to container output, so they can usually be named from default
evidence. A database that fails while the server runs is different: the server still logs `Started.`, the Helm
probes still pass, and the error is only in debug.log.

## A1.1 Store lock held by another process

**Signature:** container output
`Lock file has been locked by another process: /data/databases/store_lock`, container exits 1. Older versions
show it as `FileLockException`.

**Cause:** Neo4j takes an exclusive lock on the store at startup. Another process already holds it:

- The previous pod or task hasn't finished terminating when the new one starts on the same volume (rolling
  restart, node drain, ECS deployment with `minimumHealthyPercent` that overlaps tasks).
- Two replicas mount one volume (`ReadWriteMany` PVC, shared EFS access point, ECS service with `desiredCount` > 1
  on one EFS path).
- The volume is NFS or EFS, which Neo4j doesn't support for the store because its file locking doesn't behave like
  a local filesystem.

**Check:**

1. EKS: `describe pod` and `get pod <pod> -o yaml` (table output from `use_kubectl` shows only names): is an older
   pod for the same ordinal still `Terminating`? Is the PVC `ReadWriteMany`? Does the PV's `spec.csi.driver` show
   `efs.csi.aws.com` or an NFS server?
2. ECS: `describe-services` events and deployments: overlapping tasks? Task definition `volumes` with
   `efsVolumeConfiguration`?
3. Note when the lock error first appeared relative to the last restart or deployment.

**Fix (operator):** Make sure only one Neo4j process uses a store: wait for the old pod or task to stop (ECS:
`minimumHealthyPercent` 0 and `maximumPercent` 100 for single-instance services), use one `ReadWriteOnce` EBS
volume per server, and move the store off NFS/EFS. Don't delete `store_lock` while another process may be running.

## A1.2 Database offline: transaction logs missing, recovery impossible

**Signature:** debug.log ERROR from `DbmsReconciler`: `Encountered error when attempting to reconcile database <db>
... to state 'online', database remains in state 'offline'`, with a `ManagementException: Unable to start database`
stack trace whose cause names the problem. For missing logs the cause is `Transaction logs are missing and recovery is
not possible`, which the RPM install on EC2 also logged as a line of its own. With the transaction logs removed,
container output and neo4j.log showed nothing unusual, the container or service kept running and the `system` database
was online. Only debug.log had the error. Without debug.log, the only hints are a restore Job, a volume swap or a
change to `server.directories.transaction.logs.root` just before.

**Cause:** Recovery needs the transaction logs written after the last checkpoint. They were deleted, are on a
volume that wasn't mounted, or weren't restored with the store files. Since Neo4j 5 transaction logs live in
`/data/transactions/<db>` by default, separate from `/data/databases/<db>`, so copying only the databases
directory loses them.

**Check:**

1. If debug.log is shipped, search for `remains in state`, `Unable to start database`, `Transaction logs are missing`
   (see [log-queries.md](../log-queries.md)).
2. Look for a restore, volume or configuration change in the window: Jobs in the namespace, CloudTrail
   `RegisterTaskDefinition`, `UpdateService`, `AttachVolume`.
3. Compare `server.directories.transaction.logs.root` and the volume mounts with the previous revision.

**Fix (operator):** Run `SHOW DATABASES` to confirm the state and `statusMessage`. Restore the missing transaction
logs, or restore the database from a backup. As a last resort, and only with Neo4j Support,
`db.recovery.fail_on_missing_files=false` starts the store without them, losing the transactions they held.

## A1.3 Unclean or slow shutdown

**Signature:** a clean stop logs `Neo4j Server shutdown initiated by request`, `Stopping...` and
`Stopped.`, and exits 0. A stop cut short by SIGKILL ends with `Stopping...` and no `Stopped.`, exit 137, no
`OOMKilled`. The next start runs recovery: debug.log `Recovery in 'full' mode completed. Observed transactions range
...` and `Checkpoint triggered by "Recovery completed."` (nothing in container output).

**Cause:** Shutdown flushes the page cache and writes a checkpoint, which takes longer with a large page cache and a
write-heavy workload. On an empty test database a clean stop took about 11 seconds. If shutdown runs past the stop
timeout, the orchestrator sends SIGKILL:

- ECS `stopTimeout` defaults to 30 seconds when unset; the Fargate maximum is 120 seconds.
- Kubernetes `terminationGracePeriodSeconds`; the Neo4j Helm chart sets 3600 seconds.

**Check:**

1. Previous container: last lines, exit code, `reason`. ECS: `stopCode` and `stoppedReason` of the stopped task.
2. The stop timeout in the task definition or StatefulSet, compared with how long the last clean shutdown took: the
   time from `Stopping...` to `Stopped.` in container output. A timeout with little margin over that time is a
   finding.
3. If debug.log is shipped, look for recovery after the restart and how long checkpoints take
   (`checkpoint completed in`).

**Fix (operator):** Raise the stop timeout well above the measured shutdown time (ECS `stopTimeout` up to 120 on Fargate; a longer agent
`ECS_CONTAINER_STOP_TIMEOUT` on EC2 container instances), and keep the Helm default. Stop Neo4j with SIGTERM, not
SIGKILL. Frequent recovery on restart means shutdowns aren't completing.

## A1.4 Reading the exit code

**Symptom:** a container stopped or restarted and the cause isn't clear. Read pod `lastState.terminated.exitCode` and
`reason`, or the ECS container `exitCode`, `reason` and the task's `stoppedReason`.

**Meaning:**

| Exit | Extra field | Meaning | Go to |
| --- | --- | --- | --- |
| 0 | `Stopped.` in output | Clean stop | Look at who stopped it (deployment, scaling, node drain) |
| 1 | Cause in container output | Startup error | [A1.1](#a11-store-lock-held-by-another-process), [A6](A6-auth-tls.md) TLS, [A10](A10-platform-config.md) permissions, files, ports or settings, [A12.1](A12-versions-plugins.md) APOC |
| 137 | `OOMKilled: true` / ECS `containers[].reason` `OutOfMemoryError: container killed due to memory usage` | Memory limit | [A2.1](A2-memory-jvm.md) |
| 137 | No OOM flag, last line `Stopping...` | Killed after the stop timeout | [A1.3](#a13-unclean-or-slow-shutdown) |
| 137 | No OOM flag, no `Stopping...` | Killed externally (node failure, eviction, Spot reclaim) | Node and task events |
| 143 | None | Terminated by SIGTERM without a Neo4j shutdown; the Neo4j JVM itself exits 0 after `Stopped.`, so look at wrapper scripts or a custom entrypoint | Entrypoint and stop signal |

**Check:** Read the exit code together with the last lines of the previous container output and the events at
`finishedAt`.

## A1.5 JMX "Port already in use" from neo4j-admin

**Signature:** on the operator's terminal, `java.rmi.server.ExportException: Port already in use: <port>` when
running `neo4j-admin` or a second JVM on the host.

**Cause:** JMX remote options such as `-Dcom.sun.management.jmxremote.port=3637` in `server.jvm.additional` apply to
every JVM that reads neo4j.conf, including `neo4j-admin`. The second JVM can't bind the port the server already
holds.

**Check:** Look for `com.sun.management.jmxremote` in `server.jvm.additional`.

**Fix (operator):** Run `neo4j-admin` with `JAVA_OPTS` that don't include the JMX flags, or move the flags out of
neo4j.conf into the server's start environment only. Prefer the Prometheus or CSV metrics endpoints to remote JMX.

## A1.6 Suspected store corruption

**Symptom:** panics, `Inconsistent` or `ConsistencyCheck` errors, or record-read exceptions in container output or
debug.log; a database that goes offline right after such errors. The agent can't run a consistency check; it can only
point at the errors that suggest one.

**Cause:** Corruption is rare. Most "corruption" reports turn out to be a full disk ([A3.1](A3-disk-storage.md)),
missing transaction logs ([A1.2](#a12-database-offline-transaction-logs-missing-recovery-impossible)) or a store
copied while running.

**Fix (operator):** Check the database offline: stop it (`STOP DATABASE <db>`), or take a backup and check that, with
`neo4j-admin database check <db>` (`--report-path` for the report). Send the report to Neo4j Support.

## A1.7 Consistency check id-file warnings

**Signature:** in a consistency-check report,
`The referenced record is not in use but the id is not up for reuse in the id file`.

**Cause:** A free record isn't marked free in its id file, so the space isn't reused. It wastes space; it isn't data
loss, which is why it's a warning. Applies to record-format stores (`system`); 2026.x user databases use the block
format by default.

**Fix (operator):** Rebuild the id files by copying the database (`neo4j-admin database copy`) during a maintenance
window, or ignore the warning if the wasted space is small.
