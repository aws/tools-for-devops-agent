# RDS / Aurora Cost Optimization Reference

## Instance Generation Comparison

Do **not** rely on a hardcoded list of instance generations or savings percentages —
supported classes, newer Graviton generations, and price deltas change over time and
vary by engine and Region. Look up current values from the authoritative sources:

- **DB instance classes (types, sizes, Graviton generations):** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.html
- **Supported DB engines per instance class:** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.DBInstanceClass.Support.html
- **Aurora supported DB instance classes:** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.DBInstanceClass.html
- **Instance types overview:** https://aws.amazon.com/rds/instance-types/
- **Current pricing (for actual savings between generations):** https://aws.amazon.com/rds/pricing/ and the [AWS Pricing Calculator](https://calculator.aws/)

**Determine what is orderable for a given engine/version/Region (live, not hardcoded):**
```
aws rds describe-orderable-db-instance-options \
  --engine <engine> --engine-version <version> --region <region> \
  --query 'OrderableDBInstanceOptions[].{InstanceClass:DBInstanceClass,StorageType:StorageType}'
```

Guidance (engine/Region-independent): prefer the latest-generation and Graviton
(`*g`) classes where supported for the engine and Region, and compute the actual
On-Demand price delta from the pricing page/Calculator rather than assuming a fixed
percentage. Flag previous-generation classes as right-sizing/modernization candidates.

## Storage Type Comparison

Do **not** rely on hardcoded IOPS/throughput/cost figures — baseline and maximum
storage performance, striping thresholds, and prices differ by engine and Region and
change over time. Look up current values from the authoritative sources:

- **Amazon RDS DB instance storage (gp2, gp3, io1, io2; baselines, max IOPS/throughput, striping thresholds per engine):** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html
- **Storage overview (What is Amazon RDS):** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html
- **Aurora storage & I/O (Standard vs I/O-Optimized, how storage is billed):** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.StorageReliability.html
- **Storage pricing:** https://aws.amazon.com/rds/pricing/ and https://aws.amazon.com/rds/aurora/pricing/

Guidance (values from the docs above, not hardcoded here): gp2 is legacy — evaluate
migrating to gp3 (decouples IOPS/throughput from capacity, generally more
cost-effective); use io1/io2 for sustained high-IOPS, latency-sensitive workloads; for
Aurora, choose between Standard and I/O-Optimized using the decision matrix below with
current pricing.

## Aurora I/O-Optimized Decision Matrix

Compute the comparison from **actual** measured I/O and current pricing (do not assume
rates): Aurora storage configurations & billing — https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.StorageReliability.html · Aurora pricing — https://aws.amazon.com/rds/aurora/pricing/

| Condition | Recommendation |
|-----------|---------------|
| I/O cost > 25% of total Aurora spend | Switch to I/O-Optimized |
| I/O cost < 25% of total Aurora spend | Stay on Standard |
| Already on I/O-Optimized, equivalent standard I/O cost < 25% | Switch back to Standard |
| Low IOPS workload (< 1000 avg) | Standard is more cost-effective |

## Commitment-Based Savings: Reserved DB Instances & Savings Plans

Do **not** hardcode terms, payment options, coverage, or savings percentages — these
change and differ by service/engine/Region. Recommend commitments only after
operational optimizations (right-sizing, storage/I/O), and verify the current details
from the authoritative sources before quoting any number:

**Reserved DB Instances (RDS):**
- Reserved DB instances for Amazon RDS (terms, payment options, size-flexibility): https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithReservedDBInstances.html
- Purchasing reserved DB instances: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithReservedDBInstances.WorkingWith.html
- RDS pricing (reserved): https://aws.amazon.com/rds/pricing/
- Inspect available offerings / existing reservations (live):
  ```
  aws rds describe-reserved-db-instances-offerings --region <region>
  aws rds describe-reserved-db-instances --region <region>
  ```

**Savings Plans (including Database Savings Plans):**
- Savings Plans types — Compute vs Database vs EC2 Instance vs SageMaker (term options, coverage, and current savings %): https://docs.aws.amazon.com/savingsplans/latest/userguide/plan-types.html
- Savings Plans vs Reserved Instances comparison: https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-ris.html
- Savings Plans FAQ: https://aws.amazon.com/savingsplans/faqs/
- Savings Plans pricing/recommendations (via Cost Explorer): https://docs.aws.amazon.com/savingsplans/latest/userguide/sp-recommendations.html

**When recommending for RDS/Aurora:** confirm from the "Savings Plans types" page above
which **Database Savings Plans** term(s), payment option(s), covered services, and
savings percentage currently apply — do NOT assume a fixed term, payment option, or
flat percentage, and look up the actual savings for the specific instance type/Region.
Keep the distinction from **Compute Savings Plans** (which cover EC2/Fargate/Lambda, not
databases) clear.

## Idle Database Detection Criteria

A database is considered potentially idle when ALL of the following are true over 7 days:
- `DatabaseConnections` maximum < 5
- `CPUUtilization` average < 5%
- `ReadIOPS + WriteIOPS` average < 10

**Note:** Stopped RDS instances still incur storage charges and are automatically restarted after 7 days.

## Right-Sizing Indicators

| Signal | Current State | Recommendation |
|--------|--------------|----------------|
| CPU avg < 20% for 14 days | Oversized | Downsize by one class |
| CPU avg < 10% for 14 days | Significantly oversized | Downsize by two classes |
| FreeableMemory > 80% of class memory | Memory oversized | Consider smaller class |
| Serverless v2 avg ACU < min+1 | Floor too high | Reduce MinCapacity |
| Serverless v2 sustained at max | Ceiling hit | Raise MaxCapacity or switch to provisioned |

## Cost Allocation Tags (Recommended)

| Tag Key | Purpose | Priority |
|---------|---------|----------|
| Environment | Cost attribution by env (prod/dev/test) | HIGH |
| Owner | Team or individual accountability | MEDIUM |
| CostCenter | Finance allocation | MEDIUM |
| Project | Project-level tracking | LOW |
| Application | Application attribution | LOW |

## Backup Cost Optimization

| Strategy | Savings Potential |
|----------|-------------------|
| Reduce retention to minimum needed | Variable (storage savings) |
| Delete unneeded manual snapshots | Direct storage savings |
| Use Aurora Backtrack instead of PITR for short recovery (MySQL) | Reduced snapshot costs |
| Cross-region backup only for DR-required databases | Reduce transfer costs |
