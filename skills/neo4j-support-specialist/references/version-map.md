# Version map

Older configurations, documentation and questions often use Neo4j 3.x, 4.x or 5.x names. Translate them before
quoting a setting, command or procedure to the operator. 2026.x names were checked against Neo4j 2026.10.1 (`SHOW SETTINGS`, `SHOW PROCEDURES`,
`neo4j-admin --help`).

## Settings

| Older name | 2026.x |
| --- | --- |
| `dbms.memory.heap.max_size`, `dbms.memory.heap.initial_size` | `server.memory.heap.max_size`, `server.memory.heap.initial_size` |
| `dbms.memory.pagecache.size` | `server.memory.pagecache.size` |
| `dbms.jvm.additional` | `server.jvm.additional` |
| `dbms.tx_state.memory_allocation`, `dbms.tx_state.max_off_heap_memory` | Removed; transaction state is on heap |
| `dbms.memory.transaction.global_max_size` | `dbms.memory.transaction.total.max` (default 70% of max heap) |
| `dbms.memory.transaction.max_size` | `db.memory.transaction.max` |
| `dbms.memory.transaction.database_max_size` | `db.memory.transaction.total.max` |
| `dbms.connector.bolt.listen_address`, `.advertised_address` | `server.bolt.listen_address`, `server.bolt.advertised_address` |
| `dbms.connector.bolt.tls_level` | `server.bolt.tls_level` |
| `dbms.connector.bolt.thread_pool_max_size` | `server.bolt.thread_pool_max_size` |
| `dbms.connector.bolt.connection_keep_alive*` | `server.bolt.connection_keep_alive*` |
| `dbms.connector.http.*`, `dbms.connector.https.*` | `server.http.*`, `server.https.*` |
| `dbms.default_listen_address`, `dbms.default_advertised_address` | `server.default_listen_address`, `server.default_advertised_address` |
| `causal_clustering.initial_discovery_members`, `dbms.cluster.discovery.endpoints` | `dbms.cluster.endpoints` (members' `server.cluster.advertised_address`, port 6000) |
| `causal_clustering.discovery_type`, `dbms.cluster.discovery.type` | `dbms.cluster.discovery.resolver_type` |
| `causal_clustering.discovery_listen_address` (port 5000) | Removed; discovery uses `server.cluster.listen_address` (port 6000) |
| `causal_clustering.transaction_listen_address` | `server.cluster.listen_address` |
| `causal_clustering.raft_listen_address` | `server.cluster.raft.listen_address` |
| `causal_clustering.minimum_core_cluster_size_at_formation` | `dbms.cluster.minimum_initial_system_primaries_count`, `initial.dbms.default_primaries_count` |
| `causal_clustering.cluster_binding_timeout` | `dbms.cluster.raft.binding_timeout` (default 1d) |
| `causal_clustering.load_balancing.*`, `causal_clustering.server_groups` | `dbms.routing.load_balancing.*`, `initial.server.tags` |
| `dbms.mode=CORE` / `READ_REPLICA` | Servers host databases as primaries or secondaries (`initial.server.mode_constraint`, `ALTER DATABASE ... SET TOPOLOGY`) |
| `dbms.backup.enabled`, `dbms.backup.listen_address` | `server.backup.enabled`, `server.backup.listen_address` (default `127.0.0.1:6362`) |
| `dbms.directories.*` | `server.directories.*` (transaction logs: `server.directories.transaction.logs.root`) |
| `dbms.logs.query.*` | `db.logs.query.*` (`enabled` is `OFF`, `INFO` or `VERBOSE`; default `VERBOSE`) |
| `dbms.logs.debug.level` | Log4j configuration in `server-logs.xml` |
| `dbms.logs.gc.enabled` | `server.logs.gc.enabled` |
| `dbms.security.procedures.whitelist` | `dbms.security.procedures.allowlist` |
| `dbms.config.strict_validation` | `server.config.strict_validation.enabled` (default `true`) |
| `dbms.default_database` | `initial.dbms.default_database` (first start only), then `dbms.setDefaultDatabase` |
| `dbms.transaction.timeout` | `db.transaction.timeout` |
| `dbms.checkpoint.*` | `db.checkpoint.*` |
| `dbms.tx_log.rotation.retention_policy` | `db.tx_log.rotation.retention_policy` (default `2 days 2G`) |
| `cypher.lenient_create_relationship` | `dbms.cypher.lenient_create_relationship` |
| `dbms.record_format` (`standard`, `high_limit`) | `db.format` (`block` default on Enterprise, `aligned` on Community; `standard` and `high_limit` deprecated) |
| `metrics.*` | `server.metrics.*` |

## Commands

| Older command | 2026.x |
| --- | --- |
| `neo4j-admin check-consistency` | `neo4j-admin database check` |
| `neo4j-admin backup` | `neo4j-admin database backup` |
| `neo4j-admin restore` | `neo4j-admin database restore` |
| `neo4j-admin dump`, `neo4j-admin load` | `neo4j-admin database dump`, `neo4j-admin database load` |
| `neo4j-admin import`, `neo4j-import` | `neo4j-admin database import full` (and `incremental`) |
| `neo4j-admin copy`, `store-utils` | `neo4j-admin database copy` |
| `neo4j-admin store-info` | `neo4j-admin database info` |
| `neo4j-admin memrec` | `neo4j-admin server memory-recommendation` |
| `neo4j-admin unbind` | `neo4j-admin server unbind` |
| `neo4j-admin set-initial-password` | `neo4j-admin dbms set-initial-password` |
| `neo4j-admin push-to-cloud` | `neo4j-admin database upload` (Aura only) |
| 4.x → 5.x configuration migration | `neo4j-admin server migrate-configuration` |
| Store upgrade on start (`dbms.allow_upgrade`) | `neo4j-admin database migrate` |

## Procedures

| Older procedure | 2026.x |
| --- | --- |
| `CALL db.indexes()`, `CALL db.constraints()` | `SHOW INDEXES`, `SHOW CONSTRAINTS` |
| `CALL dbms.listQueries()`, `CALL dbms.listTransactions()` | `SHOW TRANSACTIONS` |
| `CALL dbms.killQuery()`, `CALL dbms.killTransaction()` | `TERMINATE TRANSACTION '<id>'` |
| `CALL dbms.cluster.overview()`, `CALL dbms.cluster.role()` | `SHOW SERVERS`, `SHOW DATABASES` (`role` column) |
| `CALL dbms.listConfig()` | `SHOW SETTINGS` (`dbms.listConfig` still exists) |
| `CALL dbms.procedures()`, `CALL dbms.functions()` | `SHOW PROCEDURES`, `SHOW FUNCTIONS` |
| `CALL dbms.security.listUsers()`, `listRoles()` | `SHOW USERS`, `SHOW ROLES` |
| Pattern expressions in `size((n)-->())` | `COUNT { (n)-->() }` |

## Terms

| Older term | 2026.x |
| --- | --- |
| Causal Cluster, core member | Cluster, primary |
| Read replica, follower | Secondary (follower is still the Raft role of a primary that isn't leader) |
| Leader | Writer for a database (`writer` column of `SHOW DATABASES`) |
| Neo4j 5 version numbers (5.26) | Calendar versions (2025.x, 2026.x); 5.26 is the last 5.x LTS |
