# A3: Disk and storage

**Problem it solves:** A volume fills up, the store doesn't shrink after deletes, or storage is too slow. A full
volume panics the database with the error in container output. Store and index sizes are only in the debug.log
startup dump; without it the agent has the volume size and EBS metrics.

**Finding the volume.** EKS: PVC → PV → `spec.csi.volumeHandle` (`vol-...`) with driver `ebs.csi.aws.com`, and the
StorageClass `parameters` (`type`, `iops`, `throughput`) and `allowVolumeExpansion`. ECS: task `attachments` for an
ECS-managed EBS volume, or the task definition `volumes` (EFS, bind mount). EC2: the instance's block device mappings.
Then `ec2 describe-volumes` for type, size, provisioned IOPS and throughput.

## A3.1 No space left on device

**Signature:** container output `Panic detected [Reason: Kernel database panicked ...]`, and clients get `50N00 ...
Failed to apply transaction` followed by `2DN05: invalid transaction termination - failed to apply transaction`. The
database stops with `System is out of disk space for store file` (visible to the operator in `SHOW DATABASES`
`statusMessage`). The container keeps running and the TCP probe still passes while only a user database is stopped.
When the system database then fails a checkpoint on the same volume, debug.log logs `Terminating neo4j process due to
panic. [reason: The system database panicked ...]` and the server shuts down, which can happen many minutes after the
user database stopped. debug.log adds `No space left on device`. Volume fill is known only if a filesystem metric is
already collected (CloudWatch agent `disk_used_percent`); don't estimate it.

On Community container output and neo4j.log stay silent. The signals are debug.log ERROR `Database panic: The
database has encountered a critical error`, `Could not append transaction` and `No space left on device`, and the
client error `2DN06: ... failed to append transaction`. The database still shows `online`, with `statusMessage`
`No space left on device`.

**Cause:** The data or transaction-log volume filled. Usual drivers: transaction log retention
(`db.tx_log.rotation.retention_policy`, default `2 days 2G`) larger than expected under heavy writes; store growth
with no capacity planning; backups or dumps written to the data volume; index growth ([A3.3](#a33-index-files-grow-after-purges)).
Neo4j panics the database instead of writing a partial transaction, to protect the store.

**Check:**

1. Container output for `Panic detected`, `out of disk space`, `No space left on device` and `Terminating neo4j
   process`; when each started.
2. Volume size and type; any filesystem metric; recent `ModifyVolume` in CloudTrail.
3. `db.tx_log.rotation.retention_policy` and `server.directories.*` in the configuration: are transaction logs on
   the same volume as the store?
4. Backup Jobs or tasks writing to the same volume.

**Fix (operator):** Grow the volume (EBS `ModifyVolume`; on EKS a PVC size increase when the StorageClass allows
expansion), or free space that isn't Neo4j's. Don't delete files under `/data/transactions` or
`/data/databases` by hand. Then `START DATABASE <db>` (or restart the server) and confirm with `SHOW DATABASES`.
Lower the transaction log retention if it was oversized, and alert on volume fill.

## A3.2 Store doesn't shrink after deletes

**Symptom:** volume use stays flat or keeps growing after large deletes. Store file sizes are in the debug.log startup
dump; compare them across restarts. Otherwise only the volume size is known.

**Cause:** Deleted records are marked free and reused by later writes; the files aren't truncated. Space comes back
only by copying the database.

**Check:** Store sizes in successive startup dumps; delete jobs in the window.

**Fix (operator):** If the space is needed, copy the database offline: `neo4j-admin database copy <source> <target>`,
then create the target as the new database and drop the old one. Estimate the gain first by comparing current node,
relationship and property counts with the store file sizes, or by running the copy to a scratch location. `database copy`
is Enterprise only; on Community the freed space is only reused by later writes.

## A3.3 Index files grow after purges

**Symptom:** the schema/index directory grows while the data size stays constant, in workloads that delete and
re-insert. One purge and re-insert can make it about four times larger before it levels off. Directory sizes are in
the debug.log startup dump; compare them across restarts.

**Cause:** Index structures keep freed pages for reuse instead of shrinking; churn grows them until they reach a
steady state.

**Fix (operator):** Usually none: growth levels off. To reclaim space, drop and recreate the index or copy the
database ([A3.2](#a32-store-doesnt-shrink-after-deletes)).

## A3.4 Index size for capacity planning

**Symptom:** a capacity question, or a volume filling with index data. Per-database store and index sizes are in the
debug.log startup dump.

**Fix (operator):** Map index directories under `/data/databases/<db>/schema/index/` to index names with
`SHOW INDEXES YIELD id, name, type, labelsOrTypes, properties`, then measure each directory's size.

## A3.5 Slow storage

**Symptom:** high page faults per query in query.log (`<n> page faults`), long checkpoints in debug.log
(`checkpoint completed in`), latency without CPU saturation.

**Cause:** IOPS or throughput at the volume's provisioned limit (gp3 baseline unless raised), burst credits exhausted
(gp2 `BurstBalance`), instance-level EBS bandwidth limits (`EBSIOBalance%`, `EBSByteBalance%` on instance types that
burst EBS), or a page cache too small for the working set, which turns reads into disk I/O.

**Check:**

1. `ec2 describe-volumes`: type, `Iops`, `Throughput`.
2. `AWS/EBS` metrics for the volume over the window: `VolumeReadOps` + `VolumeWriteOps` per second and
   `VolumeReadBytes` + `VolumeWriteBytes` per second against the provisioned values; `VolumeQueueLength`;
   `BurstBalance` for gp2. List the volume's metrics first and use any additional latency or limit-exceeded metrics
   that are present.
3. Node or instance type EBS bandwidth and its balance metrics.
4. Page cache size against store size ([A2.3](A2-memory-jvm.md)).

**Fix (operator):** Raise gp3 IOPS/throughput or move to io2; pick an instance type with enough EBS bandwidth; grow
the page cache so the working set stays in memory. Benchmark the volume with `fio` from a separate pod or host, not
inside the running Neo4j container.
