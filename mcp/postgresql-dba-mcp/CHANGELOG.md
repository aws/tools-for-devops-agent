# Changelog

All notable changes to the PostgreSQL DBA MCP server are documented here.

## [Unreleased]

### Added

- Read-only diagnostics for Amazon RDS for PostgreSQL and Aurora PostgreSQL through 10 MCP tools and 55 predefined SQL queries.
- Complete 26-section health reports and control-plane major-version readiness evidence returned as on-screen Markdown tool results.
- Explicit instance, database, and endpoint allowlists; a single configured Secrets Manager credential; TLS verification; and verified read-only PostgreSQL transactions.
- Aurora topology, RDS configuration, CloudWatch metric, parameter-group, log-metadata, and upgrade-readiness evidence.
- A default-disabled, conservatively validated plan-only `EXPLAIN` surface for separately reviewed deployments.

### Security

- Reports are delivered on screen only. The server does not create report artifacts, write to Amazon S3, or mint presigned URLs.
- Health diagnostics execute only the fixed query catalog. The default deployment keeps the free-form `EXPLAIN` surface disabled.
- The Lambda Function URL uses AWS IAM authentication and the deployment uses least-privilege AWS API and database access.
- Every database connection restricts `search_path` to `pg_catalog, pg_temp` inside the read-only transaction, and `pg_stat_statements` views are schema-qualified from `pg_extension`. This prevents another database user from substituting operators, functions, or relations used by the predefined queries. Table-size queries 5.1 and 5.2 now use `relid`, which also handles mixed-case and quoted table names.

## [0.1.0] - 2026-08-17

### Added

- Initial PostgreSQL DBA MCP implementation with Streamable HTTP transport, AWS IAM authentication, AWS SAM deployment, and predefined diagnostic queries.
