# A10: Platform and configuration

**Problem it solves:** Container or host settings stop Neo4j from starting. Volume permissions, file-descriptor limits
and unknown settings each exit with code 1 and print the cause to container output, so these are the most reliable
diagnoses the agent makes.

## A10.1 Permission denied on data or log directories

**Signature:** container output `Folder /data is not accessible for user: 7474 or group 7474`, exit 1. Other mounted
folders (`/logs`, `/import`) are expected to fail the same way with their own path. `Permission denied` exceptions
after running `neo4j-admin` as root are the bare-metal variant.

**Cause:** The image runs Neo4j as uid/gid 7474. The mounted volume is owned by another user and isn't writable: an
EBS volume formatted by another workload, an EFS access point with another POSIX user, a pod `securityContext` that
overrides the chart's `runAsUser`/`fsGroup` 7474, or files created by a root `neo4j-admin` run.

**Check:** Pod `securityContext` (`runAsUser`, `runAsGroup`, `fsGroup`, `fsGroupChangePolicy`) against the chart
defaults; ECS container `user`; EFS access point `PosixUser` and root directory ownership.

**Fix (operator):** Restore uid/gid 7474 (`fsGroup: 7474` on Kubernetes; EFS access point with uid/gid 7474), or chown
the data on the volume to 7474:7474. Run `neo4j-admin` as the neo4j user.

## A10.2 Too many open files

**Signature:** container output `timerfd_create() failed: Too many open files` from a server component, exit 1 at a
limit of 1024. At runtime: `Too many open files` from Lucene or the store. The effective limit is also in the
debug.log startup dump.

**Cause:** The file-descriptor limit is below what Neo4j needs for store files, index files and connections.

**Check:** ECS `ulimits` (`nofile` soft and hard); on EKS the limit comes from the container runtime on the node. The
Neo4j Operations Manual recommends at least 40,000, and its systemd example uses 60,000.

**Fix (operator):** Raise `nofile` to 40,000 or more (ECS `ulimits`, node runtime configuration, `LimitNOFILE` in the
systemd unit on EC2).

## A10.3 Binding privileged ports

**Signature:** startup failure binding a port below 1024 (`BindException`, `Permission denied`). Docker lets non-root
processes bind low ports, so a port that works on Docker can fail on Kubernetes.

**Cause:** Neo4j runs as uid 7474, and binding ports below 1024 needs `CAP_NET_BIND_SERVICE` or a lowered
`net.ipv4.ip_unprivileged_port_start`.

**Fix (operator):** Keep Neo4j on its default ports and map 80/443/7687 on the Service or load balancer instead, or set
the `net.ipv4.ip_unprivileged_port_start` sysctl in the pod `securityContext`.

## A10.4 Unrecognized setting stops startup

**Signature:** container output `Unrecognized setting. No declared setting with name: <setting>. Cleanup the config or disable 'server.config.strict_validation.enabled' to continue.`,
exit 1.

**Platform difference:** the Docker image (ECS) and the RPM (EC2) leave
`server.config.strict_validation.enabled` at its default, true, so the unknown setting exits 1. The Neo4j Helm chart
sets it to `"false"` in its default `config` values (rendered into `<release>-user-config`), so on EKS the same
setting only logs `WARN  Unrecognized setting. No declared setting with name: <setting>.` and Neo4j starts. On EKS,
treat the WARN as a configuration finding, not as a crash cause.

**Cause:** `server.config.strict_validation.enabled` defaults to true, so any setting Neo4j doesn't know stops startup.
Common sources: settings of a plugin whose jar was removed (Bloom, GDS, APOC Extended), a misspelled name, a setting
removed in this version (translate with [version-map.md](../version-map.md)), or a stray Docker environment variable
starting with `NEO4J_`. Older versions only logged a WARN.

**Check:** The named setting: is its plugin in `NEO4J_PLUGINS` or `/var/lib/neo4j/plugins`? Is it in version-map.md
as renamed or removed? Which ConfigMap or environment variable sets it, and when did it change (CloudTrail for task
definitions; Helm history isn't readable)?

**Fix (operator):** Remove or rename the setting, or install the plugin it belongs to. Validate before restarting with
`neo4j-admin server validate-config`.

## A10.5 Default database

**Symptom:** a request to change which database clients get when they don't name one.

**Fix (operator):** `initial.dbms.default_database` applies only when the DBMS is first created. Afterwards run
`CALL dbms.setDefaultDatabase('<db>')` against the `system` database. Per-user home databases
(`ALTER USER ... SET HOME DATABASE`) take precedence.
