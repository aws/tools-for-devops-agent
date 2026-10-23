# Flow Log Location

Use this when the user asks about a NAT Gateway but hasn't supplied flow log data. Find out whether flow logs exist for the NAT Gateway, where they are delivered, and how to read them, before running any query.

## Step 1 — Get the NAT Gateway's network interface, subnet, and VPC

```
aws ec2 describe-nat-gateways --region <region> --nat-gateway-ids <nat-gw-id>
```

Record `natGatewayAddresses[].networkInterfaceId` (the NAT Gateway ENI), `subnetId`, and `vpcId`. Every flow-log query in this skill must be filtered to that ENI.

Regional NAT Gateways (`availabilityMode` = `regional`) are not tied to a single subnet. Their flow-log records identify the gateway by `resource-id` and the zone by `az-id` rather than by one network interface. If the gateway is regional, say so, and confirm the field names in the user's log format before filtering.

## Step 2 — Find flow logs that capture the NAT Gateway ENI

Flow logs can be created on a network interface, a subnet, or a VPC. A subnet-level or VPC-level flow log also captures the NAT Gateway ENI, and VPC-level flow logs delivered to a central S3 bucket are a common setup. Check all three levels:

```
aws ec2 describe-flow-logs --region <region> --filter Name=resource-id,Values=<nat-eni-id>
aws ec2 describe-flow-logs --region <region> --filter Name=resource-id,Values=<subnet-id>
aws ec2 describe-flow-logs --region <region> --filter Name=resource-id,Values=<vpc-id>
```

For each flow log found, record:

| Field | Why it matters |
|---|---|
| `logDestinationType` | `cloud-watch-logs`, `s3`, or `kinesis-data-firehose` — decides how to read the data (Step 3) |
| `logGroupName` / `logDestination` | Where the records are |
| `logFormat` | Which fields exist (Step 4) |
| `trafficType` | `ALL` is needed; `ACCEPT`-only is fine for volume; `REJECT`-only is not usable for this analysis |
| `flowLogStatus`, `deliverLogsStatus` | An inactive or failing flow log may have gaps |
| `creationTime` | How far back the data can go (feeds the analysis-window check) |

If more than one flow log covers the ENI, prefer the most specific level (ENI, then subnet, then VPC) and say which one you used.

## Step 3 — Read the records by destination type

### CloudWatch Logs

Use CloudWatch Logs Insights against the log group. For the default flow-log format, Logs Insights discovers the fields automatically (`interfaceId`, `srcAddr`, `dstAddr`, `bytes`, and others). A per-destination volume query looks like:

```
filter interfaceId = "<nat-eni-id>"
| stats sum(bytes) as totalBytes by dstAddr
| sort totalBytes desc
| limit 1000
```

Notes:
- For a **custom** log format, fields are not auto-discovered. Use `parse @message` with the field order from `logFormat`, then the same `filter` and `stats`.
- Run the query over the analysis window chosen in Step 2 of the main procedure, not a default short window.
- Check whether the query hit its result limit. If it did, say the destination list is truncated, and report the totals by category rather than claiming the list is complete.

### Amazon S3

The default DevOps Agent role can't read S3 objects or run Athena queries. Both are opt-in permissions the customer must add to the agent role (`s3:GetObject` and `s3:ListBucket` on the flow-log bucket, `kms:Decrypt` if the bucket is encrypted with a customer managed key, or `athena:StartQueryExecution` with a workgroup that uses managed query results). Handle S3 in this order:

1. **An existing Athena table over the flow-log bucket.** If the customer already has one and the agent can query it, run the per-destination volume query there, filtered to the NAT Gateway ENI and the analysis window:
   ```
   SELECT dstaddr, SUM(bytes) AS total_bytes
   FROM <flow_log_table>
   WHERE interface_id = '<nat-eni-id>' AND <partition or time filter for the window>
   GROUP BY dstaddr
   ORDER BY total_bytes DESC
   LIMIT 1000
   ```
   Column names depend on how the table was defined. Read the table schema first. Don't create tables or other catalog objects.
2. **No table, or no permission.** Don't try to read the raw objects one by one. A week of flow logs for a busy NAT Gateway is thousands of compressed objects. Tell the user where the flow logs are (bucket and prefix), and give two options:
   - add the opt-in permissions above and point the skill at an Athena table; or
   - provide a per-destination summary (total bytes per destination IP for the NAT Gateway ENI over the window) from their own query.
3. Until data arrives, answer from the configuration checks that don't need flow logs (Gateway Endpoints, Interface Endpoints, peering and route tables) and say the traffic breakdown is pending.

### Kinesis Data Firehose

The records are delivered to wherever the Firehose stream sends them (often S3 or a third-party tool). The agent can't read the stream itself. Tell the user where the stream delivers, and ask for a per-destination summary.

## Step 4 — Check the log format has what the analysis needs

Required: `interface-id`, `dstaddr`, `bytes`. Useful: `srcaddr`, `start`/`end` (time window), `pkt-srcaddr`/`pkt-dstaddr` (original addresses), `flow-direction`, `traffic-path`.

If `dstaddr` or `bytes` is missing, the traffic breakdown can't be computed from these logs. Say so, and recommend a flow log with the needed fields.

The `pkt-src-aws-service` and `pkt-dst-aws-service` fields may be present. Don't attribute traffic from them (Hard Rule 13).

## Step 5 — No flow logs exist

If no flow log covers the NAT Gateway ENI at any level:

- Say so plainly, and give the enable command as a **recommendation** (this skill never creates resources):
  ```
  aws ec2 create-flow-logs --resource-type NetworkInterface --resource-ids <nat-eni-id> \
    --traffic-type ALL --log-destination-type cloud-watch-logs \
    --log-group-name <log-group> --deliver-logs-permission-arn <role-arn>
  ```
  Tell the user to wait at least 7 days before analysis.
- In the meantime, report only what doesn't need flow logs: the NAT Gateway's CloudWatch byte metrics (when traffic flows and how much), and the configuration checks (Gateway Endpoints, Interface Endpoints, peering, route tables). Don't categorize destinations without flow-log data.

## Output for this step

State in the findings where the data came from — the log group, the S3 location with the Athena table, or a user-supplied file — the flow-log level (ENI, subnet, or VPC), and that every query was filtered to the NAT Gateway ENI.
