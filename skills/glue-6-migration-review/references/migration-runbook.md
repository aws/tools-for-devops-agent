# Glue 6.0 Migration Runbook

A repeatable, per-job procedure for moving an AWS Glue for Apache Spark job from a
pre-6.0 version to Glue 6.0. All steps are recommendations for the operator — this
skill does not mutate jobs or start runs. Ground the runtime jumps in
`references/version-feature-matrix.md` and the cost figures in
`references/cost-model.md`. Authoritative reference:
[Migrating AWS Glue for Spark jobs to AWS Glue version 6.0](https://docs.aws.amazon.com/glue/latest/dg/migrating-version-60.html).

## Order jobs by risk/effort

Migrate lowest-gap jobs first to build confidence:

1. Glue 5.0 jobs (smallest Spark/Python jump)
2. Glue 4.0 jobs
3. Glue 3.0 jobs
4. Glue 2.0 / 1.0 / 0.9 jobs (largest Spark 2→4 and Python jumps; expect real
   code changes)

Prefer starting with non-production, low-criticality, tag-identified jobs.

## Per-job migration steps

### 1. Assess the runtime jump
- Look up the job's current Glue version in the feature matrix and note the
  Spark, Scala, and Python deltas to 6.0 (Spark 4.1.1 / Scala 2.13 / Python 3.13).
- The wider the gap, the more Spark API and Python-3 changes to review.

### 2. Review code for breaking changes
- **Spark 4.x** removes and changes APIs relative to Spark 2.x/3.x — review
  DataFrame/SQL usage, deprecated RDD patterns, datetime/parsing behavior, and
  changed default configs.
- **Python 3.13** — validate third-party library compatibility, remove Python 2
  idioms (for 0.9/1.0), and re-pin dependencies. Glue 6.0 supports
  customer-managed Python virtual environments.
- **Scala 2.13** — recompile Scala jobs; check for 2.12→2.13 collection/API
  changes.
- **Connectors/formats** — Glue 6.0 brings Apache Iceberg v3 (with VARIANT).
  Re-validate table format versions and any bundled connector versions the job
  relies on.
- Consider **AI-powered Spark Upgrades** in AWS Glue to automate much of the code
  and configuration modernization, then review its diff before adopting.

### 3. Update job configuration (operator applies)
- Set `GlueVersion` to `6.0`.
- Re-evaluate `WorkerType` / `NumberOfWorkers`; the newer runtime may let you
  reduce workers. Confirm auto-scaling (`--enable-auto-scaling`) settings.
- Review `DefaultArguments`, `--additional-python-modules`, connections, and any
  version-specific flags.

### 4. Validate before cutover
- Clone the job to a **non-production copy** (or a separate test job) set to Glue
  6.0 — do not upgrade the production job in place first.
- Run against representative data. Compare:
  - **Output correctness** (row counts, schema, checksums vs the current version).
  - **Run metrics** — `ExecutionTime`, DPU-hours, and cost against the Step 2
    baseline for the same input, to confirm the expected savings materialize.
- Iterate on config/code until output matches and metrics are acceptable.

### 5. Cut over and keep a rollback
- Once validated, update the production job to Glue 6.0.
- **Retain the prior job definition/version** (export the current definition
  before changing it) so the operator can revert quickly if a regression appears
  post-cutover.
- Monitor the first several production runs for errors and cost/latency drift.

## Job-type notes
- **`gluestreaming`** — after upgrading, evaluate Glue 6.0's real-time streaming
  mode where lower latency matters; validate checkpointing behavior across the
  Spark version change.
- **`pythonshell` / `glueray`** — not on the Spark track; migrate on their own
  runtime cadence and call this out separately in the report rather than bundling
  with Spark ETL jobs.

## Definition of done (per job)
- Job runs on Glue 6.0 with correct output validated against the prior version.
- Observed DPU-hours/cost are at or below the Step 2 estimate.
- Prior definition retained for rollback; first production runs monitored clean.
