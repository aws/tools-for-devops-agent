# Parameter Lists

## Step 2b parameters to extract

- **PostgreSQL:** `rds.force_ssl`, `ssl_min_protocol_version`, `password_encryption`, `log_connections`, `log_disconnections`, `log_checkpoints`, `log_statement`, `log_min_duration_statement`, `log_autovacuum_min_duration`, `shared_preload_libraries` (pg_stat_statements/pgaudit/auto_explain), the `autovacuum*` family, `max_connections`, memory/planner params (`shared_buffers`, `work_mem`, `effective_cache_size`).
- **MySQL/MariaDB:** `require_secure_transport`, `slow_query_log`, `long_query_time`, `general_log`, `log_output`, `innodb_print_all_deadlocks`, `innodb_buffer_pool_size`, `max_connections`, `innodb_flush_log_at_trx_commit`, audit plugin params.

## Step 5b logging parameters

**PostgreSQL** — from the **parameter group** (Step 2b): `log_connections`, `log_disconnections`, `log_checkpoints`, `log_statement`, `log_min_duration_statement`, `log_temp_files`, `log_autovacuum_min_duration`; `shared_preload_libraries` (verify `pg_stat_statements`, `auto_explain`).
**MySQL** — from the **parameter group**: `general_log`, `slow_query_log`, `log_output`, `long_query_time`, audit plugin status.
