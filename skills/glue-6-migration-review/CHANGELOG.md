# Changelog

All notable changes to the `glue-6-migration-review` skill are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-06

### Added
- Initial release.
- Read-only assessment that inventories AWS Glue for Apache Spark jobs running on
  a version earlier than Glue 6.0 and guides the migration to 6.0.
- **Step 1 — Legacy job inventory table**: discovery via `ListJobs` /
  `BatchGetJobs` / `GetTags`, filtered to pre-6.0 Spark jobs, with version,
  worker configuration, auto-scaling, execution class, last run, and owner tag.
- **Step 2 — Per-job cost summary**: DPU-hour computation from `GetJobRuns` and
  CloudWatch history, with an estimated current cost and projected Glue 6.0 cost
  and savings based on the published ~30% price reduction
  (`references/cost-model.md`).
- **Step 3 — Migration guide**: per-job procedure covering the Spark/Scala/Python
  runtime jump, breaking changes, configuration updates, a validation plan, and
  rollback, ordered by migration risk/effort (`references/migration-runbook.md`).
- Glue version → runtime feature matrix mapping each Glue version to its Spark,
  Scala, and Python runtime and migration status
  (`references/version-feature-matrix.md`).
- Report artifact named `glue-6-migration-<scope>-<YYYY-MM-DD>.md`.
