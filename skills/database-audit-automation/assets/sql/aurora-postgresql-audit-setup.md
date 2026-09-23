# Aurora PostgreSQL Audit Setup (pgAudit)

Run these on your Aurora PostgreSQL cluster to enable auditing. This file is reference SQL/CLI — you run it in your environment; the DevOps Agent does not execute it.

```sql
-- Aurora PostgreSQL Audit Configuration
-- Run these commands on your Aurora PostgreSQL cluster

-- 1. Install pgAudit extension
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- 2. Configure audit logging (run as superuser or rds_superuser)
-- Set in parameter group or session level.
-- For parameter group (recommended):
-- aws rds modify-db-cluster-parameter-group \
--     --db-cluster-parameter-group-name your-parameter-group \
--     --parameters "ParameterName=shared_preload_libraries,ParameterValue=pgaudit,ApplyMethod=pending-reboot" \
--     --parameters "ParameterName=pgaudit.log,ParameterValue='all',ApplyMethod=immediate" \
--     --parameters "ParameterName=pgaudit.log_catalog,ParameterValue=on,ApplyMethod=immediate" \
--     --parameters "ParameterName=pgaudit.log_parameter,ParameterValue=on,ApplyMethod=immediate" \
--     --parameters "ParameterName=pgaudit.log_relation,ParameterValue=on,ApplyMethod=immediate" \
--     --parameters "ParameterName=pgaudit.log_statement_once,ParameterValue=off,ApplyMethod=immediate" \
--     --region us-east-1

-- For session level (temporary):
ALTER SYSTEM SET pgaudit.log = 'all';
ALTER SYSTEM SET pgaudit.log_catalog = on;
ALTER SYSTEM SET pgaudit.log_parameter = on;
ALTER SYSTEM SET pgaudit.log_relation = on;
SELECT pg_reload_conf();

-- 3. Configure audit for specific roles (DBA users)
CREATE ROLE audit_monitor;
GRANT audit_monitor TO your_dba_user1;
GRANT audit_monitor TO your_dba_user2;
ALTER ROLE audit_monitor SET pgaudit.log = 'all';
ALTER ROLE audit_monitor SET pgaudit.log_level = 'notice';

-- 4. Verify pgAudit is working
SHOW shared_preload_libraries;
SHOW pgaudit.log;
SELECT * FROM pg_stat_activity WHERE usename IN ('your_dba_user1', 'your_dba_user2');

-- 5. Enable CloudWatch Logs export
-- aws rds modify-db-cluster \
--     --db-cluster-identifier your-aurora-cluster \
--     --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["postgresql"]}' \
--     --region us-east-1

-- 6. Configure log retention
-- aws logs put-retention-policy \
--     --log-group-name /aws/rds/cluster/your-aurora-cluster/postgresql \
--     --retention-in-days 90 \
--     --region us-east-1

-- 7. Monitor audit logs
SELECT
    usename,
    application_name,
    client_addr,
    backend_start,
    state,
    query
FROM pg_stat_activity
WHERE usename IN ('your_dba_user1', 'your_dba_user2')
ORDER BY backend_start DESC;

-- 8. Create view for audit summary
CREATE OR REPLACE VIEW audit_summary AS
SELECT
    date_trunc('hour', backend_start) as hour,
    usename,
    COUNT(*) as connection_count,
    COUNT(DISTINCT client_addr) as unique_ips
FROM pg_stat_activity
WHERE usename IN ('your_dba_user1', 'your_dba_user2')
GROUP BY 1, 2
ORDER BY 1 DESC;
```
