# Proving recovery works

A DR plan that has never been tested is a guess. Propose tests in this order: the
cheapest test that gives a real number first.

## 1. Restore test (measures the restore part of RTO)

AWS Backup restore testing runs restore jobs on a schedule and records how long
each restore took. Use the result to compare the measured restore time with the
RTO.

- Create a restore testing plan: frequency, start window, and which recovery points
  to test (the latest, or a random one within a window).
- Assign the resources to test. Test critical resources more often.
- Optional validation window: keeps the restored resource for checks, then AWS
  Backup deletes it.
- For low-RPO data, test both snapshot and continuous (point-in-time) recovery
  points.

Restoring by hand (RDS point-in-time restore, DynamoDB PITR restore) also works for
a first test. Time it end to end, including the time to point the application at
the restored copy.

## 2. Failure test (shows the plan works)

AWS Fault Injection Service (FIS) has a scenario library with ready-made scenarios:

- **AZ: Power Interruption** — the symptoms of a full power loss in one AZ.
- **Cross-Region: Connectivity** — blocks network traffic between Regions.
- Partial failures, such as AZ application slowdown or cross-AZ traffic slowdown.

Rules:

- Start in non-production.
- Set stop conditions (CloudWatch alarms) before running anything.
- Write down what you expect to happen before the test, then compare.

## 3. Failover drill (measures the whole RTO)

- Run the full failover on a staging copy: promote the replica or restore, switch
  traffic, check the application. Time every step.
- Measure the data-loss bound too: note the last write before the failure and the
  last write that survived.
- Repeat on a schedule (for example every quarter). Measured RTO and planned RTO
  usually differ.

**ARC Region switch** can hold the failover as a plan made of steps (for example
scale up compute, fail over the database, shift traffic) and run it from the
Region being activated. Use it to practise the same steps you would run in an
event. It has a fixed monthly price per plan.

## 4. Keep watching

- Alarm on replication lag well before it reaches the RPO: `ReplicaLag` for RDS
  read replicas, `ReplicationLatency` for DynamoDB global tables.
- Alarm on failed backup jobs.
- AWS Resilience Hub (next generation) can hold the RPO/RTO as a resilience policy
  and assess the workload against it. Its failure mode assessment gives direction,
  not evidence: only a test is evidence.

## Sources

- AWS Backup restore testing:
  https://docs.aws.amazon.com/aws-backup/latest/devguide/restore-testing.html
- AWS FIS FAQs (scenario library):
  https://aws.amazon.com/fis/faqs/
- ARC Region switch:
  https://docs.aws.amazon.com/r53recovery/latest/dg/region-switch.html
- ARC pricing:
  https://aws.amazon.com/application-recovery-controller/pricing/
- Resilience Hub failure mode assessments:
  https://docs.aws.amazon.com/resilience-hub/latest/userguide/next-gen-how-assessments-work.html
