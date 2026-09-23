# Athena Setup (Optional — Query Archived Audit Logs)

Run these in the Athena Query Editor after deploying the log-archival stack. Replace `<account-id>` with your AWS account ID. This file is reference SQL — you run it in your environment; the DevOps Agent does not execute it.

```sql
-- Athena Setup for Database Audit AI Solution

-- Step 1: Create Database
CREATE DATABASE IF NOT EXISTS rds_logs;

-- Step 2: Create External Table with Partition Projection
-- Replace <account-id> with your actual AWS account ID
CREATE EXTERNAL TABLE IF NOT EXISTS rds_logs.postgresql_logs (
  `timestamp`  string,
  `message`    string,
  `logStream`  string,
  `logGroup`   string
)
PARTITIONED BY (year string, month string, day string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES ('ignore.malformed.json' = 'true')
STORED AS TEXTFILE
LOCATION 's3://db-audit-ai-log-archive-<account-id>/rds-logs/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.year.type'='integer',
  'projection.year.range'='2024,2030',
  'projection.month.type'='integer',
  'projection.month.range'='1,12',
  'projection.month.digits'='2',
  'projection.day.type'='integer',
  'projection.day.range'='1,31',
  'projection.day.digits'='2',
  'storage.location.template'='s3://db-audit-ai-log-archive-<account-id>/rds-logs/year=${year}/month=${month}/day=${day}/'
);

-- Step 3: Verify Data (run after ~10 minutes of setup)
-- SELECT * FROM rds_logs.postgresql_logs LIMIT 10;
```
