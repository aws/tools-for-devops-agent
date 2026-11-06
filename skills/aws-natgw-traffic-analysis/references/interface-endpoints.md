# Interface Endpoint Coverage (non-S3/DynamoDB AWS service traffic)

Gateway Endpoints exist only for S3 and DynamoDB. Every other AWS API that private-subnet workloads call — container registries, credential and key services, logging and monitoring, Systems Manager, queues — crosses the NAT Gateway unless an **Interface Endpoint** (AWS PrivateLink) carries it. This is the most common NAT cost driver for EKS and ECS workloads in private subnets.

## Step A — Find out which AWS APIs are actually crossing NAT

The flow log destination IP alone cannot answer this. `ip-ranges.amazonaws.com` only has service codes for a few services (S3, DynamoDB, EC2, CloudFront, Route 53, and a handful of others); most AWS API endpoints fall under the generic `AMAZON` code. Do not name a specific API service from an IP lookup.

Use CloudTrail instead. API calls made from a private subnet through a NAT Gateway carry the NAT Gateway's public IP in the event's `sourceIPAddress` field, and `eventSource` names the service.

1. Get the NAT Gateway's public IP(s):
   ```
   aws ec2 describe-nat-gateways --nat-gateway-ids <nat-id> \
     --query 'NatGateways[].NatGatewayAddresses[].PublicIp'
   ```
2. Group CloudTrail events from that IP by service. `cloudtrail lookup-events` **cannot** filter on source IP (its lookup attributes are EventId, EventName, ReadOnly, Username, ResourceType, ResourceName, EventSource, and AccessKeyId), so use CloudTrail Lake or Athena over the trail's S3 logs:
   ```sql
   SELECT eventsource, count(*) AS calls
   FROM <cloudtrail_table>
   WHERE sourceipaddress = '<nat-public-ip>'
     AND eventtime > '<window-start>'
   GROUP BY eventsource
   ORDER BY calls DESC
   ```
3. **Limitation — state it in the output:** call counts are not bytes. CloudTrail records management events by default; high-volume data-plane calls appear only if data events are logged for that service. A service with few calls may still move many GB, and a service with many calls may move few. Use the result to decide *which* services to check for endpoint coverage, not to size the savings.

## Step B — Check Interface Endpoint coverage for those services

```
aws ec2 describe-vpc-endpoints \
  --filters Name=vpc-id,Values=<vpc-id> Name=vpc-endpoint-type,Values=Interface \
  --query 'VpcEndpoints[].{Service:ServiceName,PrivateDns:PrivateDnsEnabled,Subnets:SubnetIds,State:State}'
```

For each service from Step A, confirm all of the following. An endpoint that fails any of them can exist and still leave the traffic on NAT (Hard Rule 11):

- **The endpoint exists** for that service (`com.amazonaws.<region>.<service>`) in the VPC the traffic comes from.
- **Private DNS is enabled** (`PrivateDnsEnabled: true`). Without it, SDKs and CLIs keep resolving the public service hostname and route through NAT, unless the application was configured with the endpoint-specific URL.
- **The VPC has both DNS attributes on.** Private DNS for Interface Endpoints requires `enableDnsSupport` **and** `enableDnsHostnames`:
  ```
  aws ec2 describe-vpc-attribute --vpc-id <vpc-id> --attribute enableDnsSupport
  aws ec2 describe-vpc-attribute --vpc-id <vpc-id> --attribute enableDnsHostnames
  ```
- **The endpoint has a subnet in every AZ the workloads run in.** Check `SubnetIds` against the subnets of the workloads generating the traffic.
- **The state is `available`.**

If the VPC uses custom DNS servers instead of the Amazon-provided resolver, private DNS for the endpoint will not take effect unless those servers forward the service's domain to the Amazon-provided resolver. Note this as a possible cause rather than asserting it.

## Container image pulls (EKS/ECS) — a specific pattern

Pulling a private image from Amazon ECR uses three paths, and all three must be covered to keep pulls off NAT:

- `com.amazonaws.<region>.ecr.api` — ECR API calls.
- `com.amazonaws.<region>.ecr.dkr` — Docker registry calls (push/pull). Private DNS must be enabled on this endpoint.
- **The S3 Gateway Endpoint** — ECR stores image layers in S3, so the layer bytes (usually the bulk of the volume) go to S3, not to ECR. An ECR Interface Endpoint alone leaves layer downloads on NAT.

Also flag: the first pull through an ECR pull-through cache rule needs internet egress (NAT) even when ECR Interface Endpoints exist. That traffic is expected and is not an endpoint misconfiguration.

## Step C — Present the tradeoff, not a blanket recommendation

Interface Endpoints are not free. They bill for each hour the endpoint is provisioned **in each Availability Zone**, plus a per-GB processing charge. That fixed hourly cost per AZ means an endpoint only reduces cost when the traffic it would carry is large enough to outweigh it.

- Do not present a dollar figure. Tell the user which inputs decide the answer — GB/month for that service from the NAT traffic, number of AZs the endpoint needs, and their current NAT Gateway and PrivateLink rates — and that they should price both options with their own rates.
- If Step A shows only low call counts for a service, say that the data does not establish that an endpoint would pay off.
- Interface Endpoints also have non-cost benefits (traffic stays on the AWS network, endpoint policies). Mention these only as context, not as the reason to recommend one in a cost investigation.

## Read-only commands summary

```
aws ec2 describe-nat-gateways --nat-gateway-ids <nat-id>
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<vpc-id> Name=vpc-endpoint-type,Values=Interface
aws ec2 describe-vpc-attribute --vpc-id <vpc-id> --attribute enableDnsSupport
aws ec2 describe-vpc-attribute --vpc-id <vpc-id> --attribute enableDnsHostnames
aws ec2 describe-subnets --filters Name=vpc-id,Values=<vpc-id>
```
