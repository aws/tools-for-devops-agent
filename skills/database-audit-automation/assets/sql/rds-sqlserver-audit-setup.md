# RDS SQL Server Audit Setup (Native Audit)

Run these on your RDS SQL Server instance to enable auditing. This file is reference SQL/CLI — you run it in your environment; the DevOps Agent does not execute it.

```sql
-- RDS SQL Server Audit Configuration
-- Run these commands on your RDS SQL Server instances

-- 1. Enable SQL Server Audit
USE master;
GO
-- Create server audit (RDS will automatically send to CloudWatch)
EXEC msdb.dbo.rds_fn_task_create_audit
    @audit_name = 'RDSAudit',
    @audit_log_destination = 'CLOUDWATCH';
GO

-- 2. Create Server Audit Specification for login monitoring
CREATE SERVER AUDIT SPECIFICATION LoginAuditSpec
FOR SERVER AUDIT RDSAudit
    ADD (FAILED_LOGIN_GROUP),
    ADD (SUCCESSFUL_LOGIN_GROUP),
    ADD (LOGOUT_GROUP)
WITH (STATE = ON);
GO

-- 3. Create Database Audit Specification for privileged access
USE [YourDatabaseName];  -- Replace with your database name
GO
CREATE DATABASE AUDIT SPECIFICATION PrivilegedAccessAudit
FOR SERVER AUDIT RDSAudit
    ADD (SELECT, INSERT, UPDATE, DELETE ON DATABASE::YourDatabaseName BY dbo),
    ADD (EXECUTE ON DATABASE::YourDatabaseName BY dbo),
    ADD (SCHEMA_OBJECT_CHANGE_GROUP),
    ADD (DATABASE_PERMISSION_CHANGE_GROUP),
    ADD (DATABASE_ROLE_MEMBER_CHANGE_GROUP)
WITH (STATE = ON);
GO

-- 4. Verify audit is enabled
SELECT
    name,
    type_desc,
    on_failure_desc,
    is_state_enabled
FROM sys.server_audits;
GO

-- 5. Configure CloudWatch Logs export in RDS Console or CLI:
-- aws rds modify-db-instance \
--     --db-instance-identifier your-rds-instance \
--     --cloudwatch-logs-export-configuration '{"LogTypesToEnable":["error","agent"]}' \
--     --region us-east-1

-- Note: For RDS SQL Server, audit logs are sent to CloudWatch automatically
-- when using rds_fn_task_create_audit with CLOUDWATCH destination.
```
