# Extended Support billing rules

Reference for Phase 3 and Phase 4 of the `eos-cost-analysis` skill: which resources AWS bills for Extended Support (ES), in what unit, and how many units. Rates are never stated here. They come from the AWS Pricing API at runtime, and the skill's "Validation reference rates (us-east-1)" table is the only place sample rates appear.

Sources were checked on 2026-11-04 and are linked in each section. AWS changes these schedules, so treat every list below as a dated starting point and confirm against the linked page when a resource's classification or cost depends on it.

## 1. The billed-unit model

Every ES charge follows one formula:

```
monthly_es_cost = billed_units_per_hour × es_rate_per_unit × 730
```

- `es_rate_per_unit` is `pricePerUnit.USD` from `pricing:GetProducts` (SKILL.md Step 3.2).
- The unit is the price dimension's `unit` field in the same response: `vCPU-hour`, `ACU-hour`, `Hrs` (per cluster, per node, per NIH or per instance, depending on the service), or similar. Always read it, and measure the resource in that unit. If the unit is one this file doesn't cover, report the cost as `PRICING_UNAVAILABLE` and name the unit rather than forcing it into another formula.
- `billed_units_per_hour` comes from the service rows below. Count every resource AWS bills, not only the one discovery returned first.

## 2. Service rules

| Service | In scope (dated list, confirm on the source) | Billing unit | `billed_units_per_hour` | Source |
|---|---|---|---|---|
| EKS | Kubernetes versions past end of standard support | cluster-hour | 1 per cluster | [EKS versions](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) |
| RDS for MySQL / PostgreSQL | Major versions on the Extended Support versions page | vCPU-hour | vCPUs of the instance class × billed instances (section 3) | [RDS ES versions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/extended-support-versions.html), [RDS for MySQL pricing](https://aws.amazon.com/rds/mysql/pricing/) |
| Aurora (provisioned) | Aurora MySQL and Aurora PostgreSQL major versions past end of standard support | vCPU-hour | vCPUs of each member instance's class, each instance once (section 3) | [Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/) |
| Aurora Serverless v2 | Same versions as Aurora provisioned | ACU-hour | ACUs consumed (section 5) | [Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/) |
| ElastiCache | Redis OSS v4, v5 and v6 only. Valkey and Memcached have no Extended Support | node-hour | nodes running the in-scope version | [ElastiCache ES versions](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/extended-support-versions.html) |
| OpenSearch Service | Elasticsearch and OpenSearch versions past end of standard support | NIH, or instance-hour during an extension period (section 4) | Section 4 | [OpenSearch pricing](https://aws.amazon.com/opensearch-service/pricing/), [Calculating ES charges](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html) |
| Lambda | Deprecated runtimes | none | No ES charge; report as a security risk | [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) |

Engines and versions not on a service's source page are out of scope: list them in the discovery summary with the reason and do not price them. That covers RDS for MariaDB, Oracle and SQL Server, and ElastiCache Valkey and Memcached. ElastiCache has no Extended Support usagetype for serverless caches (every ES usagetype is per node), so a serverless cache on an in-scope version is reported as `PRICING_UNAVAILABLE`, never priced as nodes.

## 3. RDS and Aurora: counting billed instances

AWS charges ES on every instance running the affected major version: "you will be charged for all instances in a Multi-AZ deployment", and "you will be charged for any Amazon RDS Read Replicas" on a version past end of standard support ([RDS for MySQL pricing FAQ](https://aws.amazon.com/rds/mysql/pricing/)). Count instances from `rds:DescribeDBInstances`, where each listed instance is one row:

| Deployment shape | How it appears in `DescribeDBInstances` | Billed instances |
|---|---|---|
| Single-AZ DB instance | One instance, `MultiAZ: false`, no `DBClusterIdentifier` | 1 |
| Multi-AZ DB instance (one standby) | One instance, `MultiAZ: true`, no `DBClusterIdentifier`. The standby is not listed | 2: the listed instance plus its hidden standby |
| Multi-AZ DB cluster (writer + two readable standbys) | Three instances, each with the same `DBClusterIdentifier` | 3: each listed instance once |
| Read replica | Its own instance, with `ReadReplicaSourceDBInstanceIdentifier` set | 1 per replica on the affected version (2 if the replica is itself Multi-AZ) |
| Aurora cluster member (writer or reader) | Its own instance with `DBClusterIdentifier` | 1 per member, never multiplied |
| Aurora Serverless v2 member | Instance class `db.serverless` | Priced in ACU-hours (section 5), not vCPUs |

Rules that follow:
- Add a hidden standby only for an instance with `MultiAZ: true` and no `DBClusterIdentifier`. Instances in a cluster (Aurora or a Multi-AZ DB cluster) already list their standbys and readers, so never add or double for them, whatever the cluster's own `MultiAZ` flag says.
- Price each instance at its own class's vCPU count. Members of one cluster can have different classes.
- Classify a cluster member by the cluster's `EngineVersion` (instance-level versions can lag); classify a standalone instance or read replica by its own `EngineVersion`.

## 4. OpenSearch Service: charge mode and normalization factors

**Charge mode depends on the version and date** ([OpenSearch pricing](https://aws.amazon.com/opensearch-service/pricing/)):

| Mode | Versions (as published on 2026-11-04) | ES charge |
|---|---|---|
| Extension period: equal to instance cost | Elasticsearch 1.5, 2.3, 5.1–5.5, 6.0–6.7, 7.1–7.8; OpenSearch 1.0–1.2 and 2.3–2.9, from November 7, 2026 through November 7, 2027 | The instance's own on-demand hourly price, per instance-hour, in addition to the normal instance charge. Storage is unaffected |
| Standard per-NIH rate | Elasticsearch 5.6 (until November 7, 2028); Elasticsearch 6.8, 7.9 and 7.10, OpenSearch 1.3, 2.11–2.17 and 2.19 once they reach end of standard support (November 7, 2027) | `OpenSearchExtendedSupport` rate per Normalized Instance Hour (NIH) |

AWS describes the extension-period rule generally as "for versions where the originally published extended support date has passed, and there has been an additional extension to the end of support date, extended support fee will be equal to your instance cost". Use the mode the source page assigns to the version on the date you are pricing; if the page has changed, follow the page.

- **Instance-cost mode:** `billed_units_per_hour` = instance count per node group, and the rate is that instance type's on-demand price: `{PREFIX}-ESInstance:{type without .search}` in `AmazonES`, with no prefix in us-east-1 (for example `ESInstance:m7g.medium`, `EU-ESInstance:m7g.medium`).
- **NIH mode:** `billed_units_per_hour` = Σ over node groups of `instance_count × normalization factor`, using the table below.

**Normalization factors**, from the OpenSearch Service developer guide ([Calculating extended support charges](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html)). The Price List cannot supply these: it has a single `OpenSearchExtendedSupport` row priced per NIH, and no instance row carries a size factor.

| Size | Factor | Size | Factor |
|---|---|---|---|
| nano | 0.25 | 8xlarge | 64 |
| micro | 0.5 | 9xlarge | 72 |
| small | 1 | 10xlarge | 80 |
| medium | 2 | 12xlarge | 96 |
| large | 4 | 16xlarge | 128 |
| xlarge | 8 | 18xlarge | 144 |
| 2xlarge | 16 | 24xlarge | 192 |
| 4xlarge | 32 | 32xlarge | 256 |

The size is the part of the instance type before `.search`: `r6g.large.search` → `large` → 4. The pricing page's own example uses this scale: an `m7g.medium.search` instance for 24 hours is billed the per-NIH rate × 24 instance hours × 2, the "normalization factor for medium". A size not in the table is reported as `PRICING_UNAVAILABLE`, never extrapolated.

Count every node group of a domain from `DescribeDomain` → `ClusterConfig`: data nodes (`InstanceType` × `InstanceCount`), dedicated master nodes (`DedicatedMasterType` × `DedicatedMasterCount`, when `DedicatedMasterEnabled`) and UltraWarm nodes (`WarmType` × `WarmCount`, when `WarmEnabled`).

## 5. Aurora Serverless v2: ACU-hours

AWS prices serverless ES "per Aurora Capacity Unit (ACU) per hour consumed by your database" ([Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/)).

- **Rate:** an `ASv2` usagetype in `AmazonRDS`, unit `ACU-hour`. Both forms exist: `{PREFIX}-ExtendedSupport:Yr1-Yr2:ASv2:{EngineVersion}` (for example `ExtendedSupport:Yr1-Yr2:ASv2:AuroraMySQL3` in us-east-1, `USW2-ExtendedSupport:Yr1-Yr2:ASv2:AuroraPostgreSQL13`) and, for some engine versions, `{PREFIX}-ASv2-ExtendedSupport:Yr1-Yr2:{EngineVersion}`. Find the one that exists with `pricing:GetAttributeValues` (usagetypes containing `ASv2` and the engine version).
- **Usage:** average `ServerlessDatabaseCapacity` (namespace `AWS/RDS`, dimension `DBInstanceIdentifier`) over the last 14 days, in ACUs. `billed_units_per_hour` = that average.
- **No metric:** when the metric can't be read (no permission, no datapoints, instance newer than the window), report the cost as `USAGE_DEPENDENT` with the per-ACU-hour rate and the instance's configured `MinCapacity`–`MaxCapacity` range from `DescribeDBClusters` → `ServerlessV2ScalingConfiguration`. Don't assume an average.

## 6. Values when a fact can't be established

When an input can't be confirmed, every field that depends on it carries the same value, and the resource is listed but kept out of the dollar totals.

| Value | When | Fields set | In totals? |
|---|---|---|---|
| `UNVERIFIED` | No end-of-standard-support date confirmed from AWS documentation for the exact engine and version | `eos_date`, `eos_status`, `urgency`, `current_monthly_es_cost`. `projected_monthly_es_cost` shows the cost the resource would carry if it is in ES, labelled "if in Extended Support" | No. Counted and listed separately |
| `PRICING_UNAVAILABLE` | Status known, but no Pricing API product after the `GetAttributeValues` retry, or an unknown unit or normalization size | `current_monthly_es_cost`, `projected_monthly_es_cost`, `annual_es_cost` | No. Counted and listed separately |
| `USAGE_DEPENDENT` | Usage-priced resource with no usage data (section 5) | `current_monthly_es_cost`, `projected_monthly_es_cost`, `annual_es_cost`, with the rate and capacity range in the note | No. Counted and listed separately |
| `N/A` | The field doesn't apply (for example `es_year` before a resource enters ES) | The field concerned | n/a |
