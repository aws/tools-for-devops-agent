# Filling a scoping sheet

Load this at Step 7 when the user gives you a scoping, criticality or
application sheet (a file, a table or just its column headers), or asks for one.
Teams use such a sheet to register applications in AWS Resilience Hub and to
agree recovery objectives with the business. The sheet usually comes back with
the RTO, RPO and recovery approach columns empty, because the Ops team cannot
answer for the business. Your job is to send it back filled with what the
account shows, so the business only has to confirm or correct it.

## The rule that does not change

Never write a value as the business's target. Fill recovery cells with **what
the current setup delivers today**, read from the configuration, and label every
one of them `today, to confirm`. A number you cannot trace to a read-only call
or to the reference values below stays empty or says `to measure`. Columns that
only the business can answer stay empty.

## Columns

Use the user's own headers, in their order, word for word. Map each header by
meaning:

| A header that asks for | Fill it with | Source |
|---|---|---|
| Application name or code | The workload name you assessed | Step 0: stack, application or tag value |
| Names or tags seen | Stack names and tag values you read | Step 0 |
| Accounts, with resource counts | Each account you read, with its number of resources | Step 0 |
| Number of resources | The component count from Step 0 | Step 0 |
| Availability class (24/7, business hours) | The value of the tag that holds it, if the user names the tag or it is obvious; otherwise empty. Never infer it from scaling settings or names | Tags |
| Criticality proposed by AWS | Your tier from Step 2, in the sheet's own scale (for example High, Medium, Low), marked as proposed, with its reason in the line under the sheet | Step 2 |
| RTO or RPO for a scenario | What the setup delivers today for that scenario (table below), labelled `today, to confirm` | Steps 5 and 6 |
| Recovery approach | The approach in place today, in the sheet's labels (see "Approach labels") | Steps 4 and 5 |
| Restore time from backup | `to measure: restore test` unless a measured result exists | Step 6 |
| Container or Kubernetes namespace | What you read; `not applicable` if the workload does not use it | Compute layer |
| Criticality retained, owner, parent application, target availability, comments, or anything the business decides | Empty | The business |
| A header you cannot interpret | Empty, never a guess or a proxy value; list it under "Columns I could not fill" | — |

A sheet often asks for RTO and RPO for one scenario only, for example the loss
of one Availability Zone. Fill those columns for that scenario. Put what you
found for the other scenarios in scope (Region, bad data) in the line under the
sheet, not in the sheet's cells.

## What "today" means per configuration

Use the reference values in the table at the end. Write ranges as the source
gives them, with the configuration that produces them.

**One Availability Zone fails:**

| What you verified | RTO today | RPO today |
|---|---|---|
| RDS DB instance with Multi-AZ | automatic failover, typically 60 to 120 s | near zero (synchronous standby) |
| Aurora cluster with a replica in another AZ | automatic failover, typically under 120 s, often under 60 s | zero: the cluster volume keeps a copy in each AZ |
| Aurora cluster with one instance | Aurora creates a new primary instance, slower than a failover: `to measure` | zero: the cluster volume keeps a copy in each AZ, whatever the number of instances |
| RDS DB instance without Multi-AZ | no automatic recovery in another AZ: restore from a backup or a point in time, `to measure` | the gap between now and `LatestRestorableTime` (read it with `rds:DescribeDBInstances`) |
| DynamoDB table, S3 bucket in a multi-AZ storage class, EFS Regional file system | no recovery needed for the data: the service stores it across AZs | zero for the data |
| EFS Regional file system with mount targets in one AZ only | the data is safe, but clients cannot mount it from another AZ until a mount target exists there: `to measure` | zero for the data |
| EFS One Zone file system (`AvailabilityZoneName` is set), S3 One Zone-IA objects, an EBS volume, a single-node cache | the data can be lost or unavailable with the AZ: restore from a backup, `to measure` | the time since the last backup or copy that exists now |
| Lambda function attached to subnets in one AZ only | no recovery until it is attached to another AZ's subnets: `to measure` | not applicable (stateless) |
| Auto Scaling group, ECS service or EKS nodes in two or more AZs | capacity replaced automatically; time depends on start-up, `to measure` | not applicable (stateless) |
| One instance, or one task, in one AZ | no automatic recovery in another AZ: `to measure` | not applicable (stateless), or as for its data store |

The workload's RTO for the scenario is that of its slowest layer, and its RPO
that of its weakest source-of-truth data store. Say which layer sets each value.
A store not yet confirmed as rebuildable is named in the cell, not used as the
RPO. An EFS file system is One Zone only when `AvailabilityZoneName` is set; one
mount target does not make it One Zone.

**A whole Region fails, or bad data:** the RPO today is the age of the newest
copy outside the Region, or of the newest restorable point, that exists now.
Without copies outside the Region, write `no copy outside the Region`. The RTO
today is `to measure` until a drill or restore test has run.

## Approach labels

Many sheets use five labels: backup and restore, pilot light, warm standby, hot
standby, active-active. Hot standby is an active/passive multi-site setup: a full
copy in another Region that takes no traffic until failover (a fully scaled warm
standby). Map what exists today to the sheet's labels. If nothing exists outside
the Region, the approach today is `backup and restore` only if backups or copies
can be restored there; otherwise write `none outside the Region`.

## Output

After section 6 of the report, add this block:

````markdown
## Scoping sheet

Values marked "today, to confirm" describe the current setup. They are not
targets: the business confirms or corrects them.

```csv
<the user's headers, comma-separated>
<one row for the workload; quote any cell that contains a comma>
```

**Columns I could not fill:** <headers, and why>
**For the business to confirm:** <the target questions from Step 3, one line each>
````

Write the sheet as CSV rows in a code block, never as a column-and-value table: the team pastes it into their file. Write every empty cell as `""`, and put each value only in the column whose header asks for it. Before you send, count the fields: the data row must have exactly as many as the header row, because one extra comma shifts every value after it into the wrong column. One workload per answer means one row. If the user asks for several
applications, fill the row for the one you assessed and list the others as
candidates to assess next.

## Reference values (checked 4 Nov 2026)

| Item | Value | Source |
|---|---|---|
| RDS Multi-AZ DB instance failover | typically 60 to 120 seconds | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.Failover.html |
| Aurora failover with a replica | typically under 120 seconds, often under 60 seconds | https://repost.aws/knowledge-center/aurora-mysql-downtime-factors |
| Aurora with no replica | creates a new primary instance, so downtime is longer | https://aws.amazon.com/blogs/database/failover-with-amazon-aurora-postgresql/ |
| Aurora data | the cluster volume spans several AZs: an AZ failure loses no data, with a brief interruption | https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.AuroraHighAvailability.html |
| RDS point-in-time restore | transaction logs uploaded every 5 minutes; the latest point is `LatestRestorableTime` | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIT.html |
| DynamoDB | data replicated across three AZs in the Region | https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/disaster-recovery-resiliency.html |
| S3 | storage classes other than One Zone store data in at least three AZs; One Zone-IA uses one AZ | https://aws.amazon.com/s3/storage-classes/ |
| EFS | Regional file systems span several AZs; One Zone file systems use one AZ | https://docs.aws.amazon.com/efs/latest/ug/features.html |
| Approach labels | four strategies; multi-site covers active/active and hot standby active/passive | https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html |

Values change: re-check a value against its source before you rely on it for a
decision.
