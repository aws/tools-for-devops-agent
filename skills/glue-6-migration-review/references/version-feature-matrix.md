# AWS Glue Version → Runtime Feature Matrix

Use this matrix to determine the runtime jump involved in moving a job from its
current AWS Glue version to **Glue 6.0**, and to flag versions that are
deprecated or near end of support. Confirm the live values against the
[AWS Glue versions release notes](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)
and the [version support policy](https://docs.aws.amazon.com/glue/latest/dg/glue-version-support-policy.html)
before finalizing a report — Glue version support windows change over time.

> The AWS Glue version pins the Apache Spark, Scala, and Python runtime for a
> Spark job. Migrating to 6.0 therefore means jumping all of these at once, which
> is where most breaking changes come from.

## Spark job runtime by Glue version

| Glue Version | Apache Spark | Python (Spark) | Scala | Migration status | Notes |
|---|---|---|---|---|---|
| 0.9 | Spark 2.2.x | Python 2 | 2.11 | Legacy — migrate urgently | No auto-scaling; DPU-based only |
| 1.0 | Spark 2.4.x | Python 2 / 3.6 | 2.11 | Legacy — migrate urgently | DPU-based; oldest common in the field |
| 2.0 | Spark 2.4.x | Python 3.7 | 2.11 | Legacy — migrate | Reduced startup billing introduced |
| 3.0 | Spark 3.1.x | Python 3.7 | 2.12 | Migrate | Worker types (G.1X/G.2X), auto-scaling GA |
| 4.0 | Spark 3.3.x | Python 3.10 | 2.12 | Migrate | Cloud-native adaptivity, more connectors |
| 5.0 | Spark 3.5.x | Python 3.11 | 2.12 | Migrate to 6.0 | Most recent pre-6.0 line |
| **6.0** | **Spark 4.1.1** | **Python 3.13** | **Scala 2.13** | **Target** | Iceberg v3 (VARIANT), Spark Declarative Pipelines, real-time streaming mode, Arrow-native Python UDFs, customer-managed Python virtual environments, ~30% lower price |

> **Treat as a migration candidate** any Spark (`glueetl` / `gluestreaming`) job
> whose `GlueVersion` is earlier than `6.0`. The larger the version gap, the
> larger the Spark/Python jump and the more code review the migration needs.

## Runtime jump summary (to Glue 6.0)

| From | Spark jump | Python jump | Scala jump | Relative migration effort |
|---|---|---|---|---|
| 5.0 | 3.5 → 4.1.1 | 3.11 → 3.13 | 2.12 → 2.13 | Lowest — smallest gap |
| 4.0 | 3.3 → 4.1.1 | 3.10 → 3.13 | 2.12 → 2.13 | Moderate |
| 3.0 | 3.1 → 4.1.1 | 3.7 → 3.13 | 2.12 → 2.13 | Moderate–high (larger Python jump) |
| 2.0 | 2.4 → 4.1.1 | 3.7 → 3.13 | 2.11 → 2.13 | High — major Spark 2→4 rewrite risk |
| 1.0 / 0.9 | 2.2/2.4 → 4.1.1 | Py2/3.6 → 3.13 | 2.11 → 2.13 | Highest — expect significant code changes |

## Job types and their upgrade path

| `Command.Name` | Job type | 6.0 upgrade path |
|---|---|---|
| `glueetl` | Spark batch ETL | In scope — change `GlueVersion` to 6.0, review Spark 4 / Python 3.13 breaking changes |
| `gluestreaming` | Spark streaming | In scope — as above; evaluate the new real-time streaming mode |
| `pythonshell` | Python shell | Different track — Python-shell versions are decoupled from Spark; note separately, do not lump with Spark jobs |
| `glueray` | Ray | Different track — Ray runtime is versioned separately; note separately |

Report Python-shell and Ray jobs in a separate line item so the Spark-to-6.0
inventory and cost estimates stay accurate.
