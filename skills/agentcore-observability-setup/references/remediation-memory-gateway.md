# Remediation — Memory & Gateway Resources

Memory and Gateway resources do **not** get log destinations configured automatically. Logs and
traces must be wired explicitly. Default vended log group:
`/aws/vendedlogs/bedrock-agentcore/{memory|gateway}/APPLICATION_LOGS/{resource-id}`.

All steps are applied by the customer; the skill only generates them.

---

## Console

**Log delivery (Memory or Gateway):**
1. Open the resource in the AgentCore console (Memory or Gateway page).
2. Select the resource → **Log delivery** pane → **Add**.
3. Choose destination: CloudWatch Logs group, Amazon S3 bucket, or Amazon Data Firehose.
4. **Log type:** `APPLICATION_LOGS`.
5. For S3/Firehose, enter a delivery destination ARN. For CloudWatch Logs, the destination log group
   is prepopulated (override if desired).
6. **Add**.

**Tracing (Memory or Gateway):**
1. Open the resource → **Tracing** pane → **Edit**.
2. Toggle **Enable** → **Save**.

---

## SDK (boto3)

Wires both a logs delivery (→ CloudWatch Logs) and a traces delivery (→ X-Ray) for a Memory or
Gateway resource.

```python
import boto3

def enable_observability_for_resource(resource_arn, resource_id, account_id, region="us-east-1"):
    logs_client = boto3.client("logs", region_name=region)

    # 0. Log group for vended log delivery
    log_group_name = f"/aws/vendedlogs/bedrock-agentcore/{resource_id}"
    logs_client.create_log_group(logGroupName=log_group_name)
    log_group_arn = f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"

    # 1. Delivery source for logs
    logs_source = logs_client.put_delivery_source(
        name=f"{resource_id}-logs-source",
        logType="APPLICATION_LOGS",
        resourceArn=resource_arn,
    )

    # 2. Delivery source for traces
    traces_source = logs_client.put_delivery_source(
        name=f"{resource_id}-traces-source",
        logType="TRACES",
        resourceArn=resource_arn,
    )

    # 3. Delivery destinations
    logs_dest = logs_client.put_delivery_destination(
        name=f"{resource_id}-logs-destination",
        deliveryDestinationType="CWL",
        deliveryDestinationConfiguration={"destinationResourceArn": log_group_arn},
    )
    traces_dest = logs_client.put_delivery_destination(
        name=f"{resource_id}-traces-destination",
        deliveryDestinationType="XRAY",
    )

    # 4. Connect sources to destinations
    logs_client.create_delivery(
        deliverySourceName=logs_source["deliverySource"]["name"],
        deliveryDestinationArn=logs_dest["deliveryDestination"]["arn"],
    )
    logs_client.create_delivery(
        deliverySourceName=traces_source["deliverySource"]["name"],
        deliveryDestinationArn=traces_dest["deliveryDestination"]["arn"],
    )
```

---

## Verification after applying

- `logs:DescribeDeliverySources` → an `APPLICATION_LOGS` source bound to the resource ARN.
- `logs:DescribeDeliveries` → an active logs delivery and a `TRACES`→XRAY delivery.
- `logs:FilterLogEvents` on the vended log group → recent events after exercising the resource.

See the provided log-data references for the fields emitted per resource type
(`observability-memory-metrics`, `observability-gateway-metrics` in the AgentCore docs).
