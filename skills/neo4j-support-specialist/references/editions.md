# Community Edition

The runbooks describe Enterprise. Read this file when the target runs Community, and state the edition in the report.

## Identifying the edition

| Platform | Evidence | Community | Enterprise |
| --- | --- | --- | --- |
| EKS (Helm) | `NEO4J_EDITION` in the `<release>-env` ConfigMap | `COMMUNITY_K8S` (the chart default) | `ENTERPRISE_K8S` |
| Any container | Image tag | `neo4j:<version>` or `neo4j:<version>-community` | `neo4j:<version>-enterprise` |
| EC2 | Package name (SSM Inventory or the operator's evidence command) | `neo4j` | `neo4j-enterprise` |
| Any | Startup output | No license block | A `LICENSE AGREEMENT REQUIRED` block and `license agreement was accepted with environment variable NEO4J_ACCEPT_LICENSE_AGREEMENT` |

An unsuffixed tag is Community, not Enterprise. Moving tags such as `neo4j:2026.10` and `neo4j:latest` can point to a
newer patch release than the one the deployment started with, so read the image digest or the startup banner
(`======== Neo4j <version> ========`) for the exact version. `neo4j --version` prints the version only.

## What Community doesn't have

| Area | On Community | Runbooks affected |
| --- | --- | --- |
| Logs | query.log and security.log stay empty. Failed logins still reach container output, neo4j.log and debug.log | A4, A6, A11: query-level and authentication detail come from client logs only |
| Clustering | No cluster. Cluster settings stop startup as unrecognized (for example `No declared setting with name: initial.dbms.default_primaries_count`); the Helm chart refuses to render with `Please use enterprise edition for clustering` | A7 doesn't apply |
| Roles and identity | No `CREATE ROLE`, `GRANT`, LDAP, SSO or OIDC; every user has full rights | A6.5 to A6.9 don't apply; the connector needs Enterprise |
| Databases | One user database. `STOP DATABASE`, `CREATE DATABASE` and home databases return `51N27 ... not supported in community edition`; `dbms.setDefaultDatabase` doesn't exist | A8.3, A10.5 |
| Backup | No `neo4j-admin database backup`, `restore` or `copy`, and no `server.backup.*` settings. `database dump` and `load` need the server stopped: a dump of a running database fails with `The database is in use` | A1.7, A3.2, A8 |
| Import | `database import full` only; no `import incremental` | A9.2 |
| Procedures and settings | No `SHOW SERVERS`, `dbms.listPools`, `dbms.cluster.*` or `dbms.setConfigValue`, so no runtime setting changes. No metrics settings | A2, A4, operator commands |
| Store format | `aligned` record format; Enterprise defaults to `block` | A1.7 |

Community deployments usually have no Neo4j Support contract. Where a runbook says to involve Neo4j Support, tell a
Community user to restore from a dump first and treat any recovery override as accepting data loss.

## Signatures that differ on Community

With default configuration on 2026.10.1:

| Fault | Community | Enterprise | Runbook |
| --- | --- | --- | --- |
| One query exhausts the heap (no transaction memory limit) | The client gets `51N59: ... internal resource exhaustion`; the server keeps answering. Nothing in container output or any log file | The JVM stops answering; `OutOfMemoryError` on stdout only | [A2.2](runbooks/A2-memory-jvm.md#a22-heap-outofmemoryerror-leaves-the-server-degraded) |
| Transaction logs missing | debug.log ERROR `Failed to start DatabaseId{...[neo4j]}` from `DatabaseLifecycles`, caused by `Error reading transaction logs, recovery not possible`. `SHOW DATABASES` shows `offline` with `An error occurred! Unable to start` | `DbmsReconciler` ERROR and `Transaction logs are missing and recovery is not possible` | [A1.2](runbooks/A1-startup-recovery.md#a12-database-offline-transaction-logs-missing-recovery-impossible) |
| Volume full | Container output and neo4j.log show nothing. debug.log ERROR `Database panic: The database has encountered a critical error`, `Could not append transaction` and `No space left on device`; clients get `2DN06: ... failed to append transaction`. `SHOW DATABASES` still shows `online`, with `statusMessage` `No space left on device` | `Panic detected` in container output; database stopping | [A3.1](runbooks/A3-disk-storage.md#a31-no-space-left-on-device) |
| `nofile` limit of 1024 | Starts normally; the debug.log startup dump shows `Max number of file descriptors: 1024` | Exit 1 with `timerfd_create() failed: Too many open files` | [A10.2](runbooks/A10-platform-config.md#a102-too-many-open-files) |

These apply to Community as written: store lock, SSL base directory, volume permissions, unrecognized setting, APOC
version mismatch, the cgroup kill (exit 137, no log line), the transaction memory limit (`51N72`, client only) and the
failed-login WARN.
