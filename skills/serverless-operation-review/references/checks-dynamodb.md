# Check Catalog — Amazon DynamoDB

Covers tables, global secondary indexes, backups, capacity, and streams as they appear in a
serverless workload.

Pillar codes: **SEC** Security · **REL** Reliability · **PERF** Performance Efficiency ·
**COST** Cost Optimization · **OPS** Operational Excellence

Documented thresholds used below, from
[CloudWatch recommended alarms](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html):
`AccountProvisionedReadCapacityUtilization` and `AccountProvisionedWriteCapacityUtilization` at 80%,
`FailedToReplicateRecordCount` and `SystemErrors` tolerance-based, `ReplicationLatency` "longer than
3 minutes are generally a cause for investigation".

---

## Reliability and data durability

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-DDB-001 | REL | HIGH | `DescribeContinuousBackups` reports `PointInTimeRecoveryStatus: DISABLED` on a table holding business data | Without PITR the only recovery point is a manual or AWS Backup snapshot. Enable PITR for continuous recovery to any second in the retention window | DynamoDB point-in-time recovery |
| SLS-DDB-002 | REL | HIGH | PITR disabled **and** no AWS Backup recovery points and no manual backups | There is no recovery path at all for this table. Treat as a data-loss risk | DynamoDB backup and restore |
| SLS-DDB-003 | REL | HIGH | `DeletionProtectionEnabled: false` on a production table | A single API call or a stack replacement can delete the table and its data. Enable deletion protection | DynamoDB deletion protection |
| SLS-DDB-004 | REL | HIGH | `ReadThrottleEvents` or `WriteThrottleEvents` sustained above the workload's accepted level | Requests are being rejected. For provisioned tables raise capacity or enable autoscaling; for on-demand check for a hot partition key | CloudWatch recommended alarms — `ReadThrottleEvents` / `WriteThrottleEvents`; DynamoDB throttling troubleshooting |
| SLS-DDB-005 | REL | HIGH | GSI-dimensioned `ReadThrottleEvents`/`WriteThrottleEvents` > 0 | A throttled GSI throttles writes to the **base table** as well. Size index capacity with the table, and project only the attributes the index needs | CloudWatch recommended alarms — GSI dimension; DynamoDB GSI best practices |
| SLS-DDB-006 | REL | MEDIUM | `SystemErrors` sustained above zero | 5xx from DynamoDB. Confirm the SDK is retrying, and correlate with the Health Dashboard for a service event | CloudWatch recommended alarms — `SystemErrors` |
| SLS-DDB-007 | REL | MEDIUM | `UserErrors` sustained above zero | 4xx — the client is sending invalid requests. Check request shape and conditional-write logic in the calling function | CloudWatch recommended alarms — `UserErrors` |
| SLS-DDB-008 | REL | MEDIUM | Provisioned table with no Application Auto Scaling scalable target registered | Fixed provisioned capacity throttles under a traffic increase. Enable autoscaling, or move to on-demand | DynamoDB auto scaling |
| SLS-DDB-009 | REL | MEDIUM | Global table replica with `ReplicationLatency` above 3 minutes | Replicas are diverging. Check replica capacity and, for legacy global tables, that write capacity matches across replicas | CloudWatch recommended alarms — `ReplicationLatency`: "Replication latencies longer than 3 minutes are generally a cause for investigation" |
| SLS-DDB-010 | REL | HIGH | Kinesis data stream replication enabled with `FailedToReplicateRecordCount` > 0 | Change records are being skipped. Usually an item that expands past the Kinesis 1 MB record limit | CloudWatch recommended alarms — threshold 0 |
| SLS-DDB-011 | REL | MEDIUM | Kinesis replication `ThrottledPutRecordCount` > 0 or `AgeOfOldestUnreplicatedRecord` growing | The destination stream is under-provisioned. Add shards in proportion to the table's write throughput | CloudWatch recommended alarms |
| SLS-DDB-012 | REL | LOW | Single-Region table for a workload with a stated cross-Region resilience requirement | Global tables give multi-Region redundancy. Report the gap against the stated requirement rather than prescribing it unconditionally | DynamoDB global tables |
| SLS-DDB-013 | REL | MEDIUM | `TableStatus` is not `ACTIVE`, or a GSI `IndexStatus` is not `ACTIVE` | The table is mid-change; re-check before trusting the other findings | DynamoDB table states |

## Performance efficiency

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-DDB-030 | PERF | HIGH | Account-level `AccountProvisionedReadCapacityUtilization` or `AccountProvisionedWriteCapacityUtilization` ≥ 80% | The account quota is nearly consumed; once it is reached DynamoDB throttles. Request a quota increase through Service Quotas | CloudWatch recommended alarms — threshold 80%: "so that action… can be taken before it reaches full capacity to avoid throttling" |
| SLS-DDB-031 | PERF | MEDIUM | `SuccessfulRequestLatency` for a singleton operation (`GetItem`, `PutItem`) materially above single-digit milliseconds | DynamoDB provides single-digit millisecond latency on average for singleton operations; a sustained higher value warrants investigation | CloudWatch recommended alarms — `SuccessfulRequestLatency` |
| SLS-DDB-032 | PERF | MEDIUM | Consumed capacity is concentrated in a narrow key range (evidence of a hot partition) | Redesign the partition key for even distribution, or add a write-sharding suffix | DynamoDB partition key design |
| SLS-DDB-033 | PERF | LOW | Function performs `Scan` operations against a large table (evident from log patterns or the execution role granting only `dynamodb:Scan`) | Replace scans with `Query` against a key or an index | DynamoDB best practices |
| SLS-DDB-034 | PERF | LOW | Read-heavy table with no DAX and latency-sensitive access patterns | DAX gives microsecond reads for eventually-consistent access patterns | DynamoDB Accelerator |
| SLS-DDB-035 | PERF | LOW | GSI projects `ALL` attributes where the query needs only a few | Over-projection multiplies write cost and index size | DynamoDB GSI best practices |

## Security

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-DDB-050 | SEC | MEDIUM | `SSEDescription` absent or the table uses the AWS-owned key, for a workload handling regulated data | All DynamoDB tables are encrypted at rest by default with an AWS-owned key. A customer-managed KMS key adds key-policy control, rotation control, and CloudTrail visibility of key use | DynamoDB encryption at rest |
| SLS-DDB-051 | SEC | HIGH | A Lambda execution role grants `dynamodb:*` on `Resource: "*"` | Scope to the specific table and index ARNs, and to the specific actions the handler performs | Lambda best practices — most-restrictive permissions |
| SLS-DDB-052 | SEC | MEDIUM | Execution role grants `dynamodb:DeleteTable`, `dynamodb:UpdateTable`, or `dynamodb:CreateTable` to a data-plane function | Data-plane functions need only item-level actions. Remove control-plane permissions | IAM least privilege |
| SLS-DDB-053 | SEC | LOW | No resource-based policy or condition restricting access on a table shared across accounts | Use a resource-based policy with explicit principals | DynamoDB resource-based policies |
| SLS-DDB-054 | SEC | LOW | Table has no attribute-level access control where a single table serves multiple tenants | Use IAM policy conditions (`dynamodb:LeadingKeys`) for tenant isolation | DynamoDB fine-grained access control |

## Cost optimization

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-DDB-070 | COST | MEDIUM | `BillingModeSummary` is `PROVISIONED` and consumed capacity is far below provisioned over the window | Either enable autoscaling with a realistic target utilisation, or switch to `PAY_PER_REQUEST` | DynamoDB capacity modes |
| SLS-DDB-071 | COST | MEDIUM | `BillingModeSummary` is `PAY_PER_REQUEST` with steady, predictable, high-volume traffic | Provisioned capacity with autoscaling is usually cheaper for predictable load | DynamoDB capacity modes |
| SLS-DDB-072 | COST | MEDIUM | Table has no TTL (`DescribeTimeToLive` reports `DISABLED`) and stores time-bounded data (events, sessions, audit records) | TTL deletes expired items with no write-capacity cost | DynamoDB Time to Live |
| SLS-DDB-073 | COST | LOW | `TableClassSummary` is `STANDARD` on a table dominated by storage cost rather than throughput | Standard-Infrequent Access lowers storage cost at a higher request cost | DynamoDB table classes |
| SLS-DDB-074 | COST | LOW | Streams enabled (`StreamSpecification.StreamEnabled: true`) with no consumer — no event source mapping and no Kinesis replication references the stream | Disable the unused stream | DynamoDB Streams |
| SLS-DDB-075 | COST | LOW | Unused GSIs — no query pattern in the workload targets them | Each GSI carries its own write cost on every base-table write. Remove unused indexes | DynamoDB GSI best practices |
| SLS-DDB-076 | COST | LOW | Zero consumed capacity over the window on a table that still holds provisioned capacity | Decommission or move to on-demand | DynamoDB capacity modes |

## Operational excellence

| ID | Pillar | Severity | Detection | Remediation | Source |
|---|---|---|---|---|---|
| SLS-DDB-090 | OPS | MEDIUM | No alarm on `ReadThrottleEvents` or `WriteThrottleEvents` | See `cloudwatch-alarm-reference.md` | Lens — Metrics and alerts |
| SLS-DDB-091 | OPS | MEDIUM | No alarm on `SystemErrors` | as above | Lens — Metrics and alerts |
| SLS-DDB-092 | OPS | MEDIUM | No alarm on `UserErrors` | as above | Lens — Metrics and alerts |
| SLS-DDB-093 | OPS | MEDIUM | No alarm on `ThrottledRequests` | as above | Lens — Metrics and alerts |
| SLS-DDB-094 | OPS | LOW | Contributor Insights disabled on a table with suspected key skew | Contributor Insights identifies the most-accessed keys, which is the fastest way to confirm a hot partition | DynamoDB Contributor Insights |
| SLS-DDB-095 | OPS | LOW | Missing operational tags — `Environment`, `Owner`, `Runbook`, `OnCall` | Tag for ownership routing and cost allocation | Well-Architected OPS |
| SLS-DDB-096 | OPS | LOW | Global table replicas have mismatched capacity settings (legacy 2017.11.29 version) | AWS specifically calls out verifying that write capacity units are identical across replica tables for the legacy global tables version | CloudWatch recommended alarms — `ReplicationLatency` guidance |

---

## Remediation snippets

### Enable PITR and deletion protection

```bash
aws dynamodb update-continuous-backups \
  --table-name orders \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

aws dynamodb update-table \
  --table-name orders \
  --deletion-protection-enabled
```

SAM/CloudFormation:

```yaml
Resources:
  OrdersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: orders
      BillingMode: PAY_PER_REQUEST
      DeletionProtectionEnabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !Ref TableKey
      TimeToLiveSpecification:
        AttributeName: expiresAt
        Enabled: true
```

### Enable TTL

```bash
aws dynamodb update-time-to-live \
  --table-name sessions \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt"
```

### Add autoscaling to a provisioned table

```bash
aws application-autoscaling register-scalable-target \
  --service-namespace dynamodb \
  --resource-id "table/orders" \
  --scalable-dimension "dynamodb:table:WriteCapacityUnits" \
  --min-capacity 5 --max-capacity 500

aws application-autoscaling put-scaling-policy \
  --service-namespace dynamodb \
  --resource-id "table/orders" \
  --scalable-dimension "dynamodb:table:WriteCapacityUnits" \
  --policy-name orders-write-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {"PredefinedMetricType": "DynamoDBWriteCapacityUtilization"}
  }'
```

### Check the account capacity quota before recommending an increase

```bash
aws service-quotas list-service-quotas \
  --service-code dynamodb \
  --query "Quotas[?contains(QuotaName,'capacity')].[QuotaName,Value,Adjustable]" \
  --output table
```
