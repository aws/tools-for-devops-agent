# Gateway Endpoint Coverage and Cross-Region S3

## Step 1 — Verify Gateway Endpoint existence and coverage

For each VPC, check:

```
describe-vpc-endpoints
  --filters Name=vpc-id,Values=<vpc-id> Name=vpc-endpoint-type,Values=Gateway
```

Confirm:
- Does an S3 Gateway Endpoint exist?
- Does a DynamoDB Gateway Endpoint exist?
- Which route tables are associated with each endpoint?
- Do **all active subnets** have coverage? Check subnet associations on any route table that appears to be "missing" the endpoint — an orphaned route table with no subnet associations is not a coverage gap, it's a non-issue.

## Step 2 — If S3 traffic remains despite an endpoint existing, check for cross-region

**Hard rule: Gateway Endpoints are same-region only.** They cannot intercept traffic to a different region's S3 IPs, no matter how the endpoint or route tables are configured.

1. **Check the region's prefix list** — the endpoint only intercepts destination IPs that appear in *its own region's* managed prefix list:
   ```
   get-managed-prefix-list-entries --prefix-list-id <region-s3-prefix-list-id>
   ```
2. **Resolve the destination IPs' actual region** via `ip-ranges.amazonaws.com`.
3. **If the destination IPs are NOT in the local prefix list → the traffic is cross-region S3.** The Gateway Endpoint is correctly not intercepting it — this is expected behavior, not a misconfiguration. The fix is *not* "check your endpoint config"; the fix is addressing the cross-region access pattern itself (see Step 3).

## Step 3 — Before recommending any cross-region S3 fix: the CopyObject gate

**This check is mandatory before recommending a Cross-Region Interface Endpoint.** Skip it entirely if cross-region S3 traffic is negligible (below roughly 1,000 GB) — don't surface CopyObject as a standalone finding if no cross-region-endpoint recommendation depends on it.

If cross-region S3 traffic is significant, check for CopyObject/CopyPart activity via Cost Explorer, grouped by operation:

```
aws ce get-cost-and-usage \
  --time-period Start=<30-days-ago>,End=<today> \
  --granularity MONTHLY \
  --metrics UsageQuantity \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Simple Storage Service"]}}' \
  --group-by Type=DIMENSION,Key=OPERATION
```

Look specifically for `CopyObject` and `CopyPart` in the grouped results. This is a standard, customer-callable Cost Explorer call — no special access beyond `ce:GetCostAndUsage` on the account being analyzed.

- **If CopyObject/CopyPart activity is present:** Do **not** recommend a Cross-Region Interface Endpoint with private DNS. It will break cross-region copies **VPC-wide** — private DNS applies to every subnet, public and private, with no per-subnet isolation possible. Recommend instead:
  - Cross-Region Replication (CRR) with the application reading from the local replica, or
  - Multi-Region Access Point (MRAP) with bucket replication
- **If no CopyObject/CopyPart activity is detected:** A Cross-Region Interface Endpoint can be presented as an option, but flag: "No CopyObject activity detected in the sample window — lower risk, but confirm before enabling private DNS, since the check only covers the sampled period."

### Why this matters (the mechanism)

A Cross-Region S3 Interface Endpoint uses the cross-region PrivateLink feature (not a standard same-region Interface Endpoint — standard Interface Endpoints cannot span regions). Enabling private DNS on it means *every* S3 API call from *any* subnet in the VPC resolves through the endpoint, including calls whose source bucket is in a different region than the endpoint targets. `CopyObject` and `UploadPartCopy` calls that need to reach a different region's S3 control plane will fail once intercepted by an endpoint scoped to the wrong region. There is no DNS-level split available. S3 interface endpoints do not support `CopyObject` or `UploadPartCopy` between buckets in different AWS Regions — see [Restrictions and limitations of AWS PrivateLink for Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/privatelink-interface-endpoints.html).

### Cost note

A Cross-Region Interface Endpoint costs more per GB than a same-region Interface Endpoint: PrivateLink processing *and* inter-region data transfer both apply to the same bytes. State this when comparing options, without quoting prices — the user prices it with their own rates (see `output-and-limitations.md`).

## Decision table — cross-region S3 reads

| Option | Prerequisite | CopyObject/UploadPartCopy impact | Notes |
|---|---|---|---|
| CRR (source → local) + local reads | Application points reads to the local replica | None | Best when buckets are finite and re-read frequently |
| Cross-Region Interface Endpoint | IAM permission for multi-region PrivateLink | **Blocks cross-region CopyObject VPC-wide** | No application change needed, but carries the CopyObject risk above |
| MRAP + replication | Bucket replication configured | None | Multi-region access point abstracts the region choice |
| Point application to local replica (if CRR already exists) | CRR already running | None | Simplest fix — pure application/config change, no new infrastructure |

## Related hard rules

- Gateway Endpoints don't "block" cross-region traffic — they simply don't match it, so it takes the default route (to NAT Gateway) unchanged.
- `CopyObject`'s data payload never traverses NAT Gateway — only the API control-plane call does. Don't count CopyObject volume toward NAT Gateway savings.
- CRR *inbound* traffic (`PutObjectForRepl`, `PutObjectReplTime`) is an S3-to-S3 service operation and never touches the customer's NAT Gateway.
