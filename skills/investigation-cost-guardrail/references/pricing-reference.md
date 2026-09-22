# AWS Pricing Reference

This file contains all AWS-specific Pricing API call patterns. Read this file the first time any operation is classified PAID by Layer 2, before estimating cost.

> **Critical:** `usagetype` and `operation` are **different** Pricing API filter fields. Always use the field and value specified in the Layer 2 table — do NOT derive the filter value from the AWS API operation name. Every rate must come from an exact Pricing API lookup with the correct filter field/value and the correct region scoping. If any of these cannot be resolved exactly, **HALT** — do NOT improvise a rate.

---

## Two different regions — do not conflate

1. **Pricing API endpoint region** — always `us-east-1`.
2. **Workload region** — the region of the resource being priced. For `operation`-based lookups this is passed as a `regionCode` filter. For `usagetype`-based lookups this drives the prefix (`USW2-`, `EU-`, etc.).

> The workload region is a function of the **resource being priced only** — never the agent's runtime region, and never a hardcoded default. If the workload region is unknown, resolve it from the resource ARN before pricing. **Do NOT default to us-east-1** as the workload region.

---

## Region Scoping by Filter Type

| Filter type | How to scope to workload region |
|---|---|
| `operation` | Add `{"Type":"TERM_MATCH","Field":"regionCode","Value":"<workload-region>"}` as a second filter. Returns exactly 1 product. Omitting it returns all regions (paginated, nondeterministic). |
| `usagetype` | Prepend the workload-region prefix to the value (e.g. `USW2-DataScannedInTB`). See Region Prefix Mapping table below. |

---

## Standard Patterns

### operation-based lookup 

```bash
aws pricing get-products \
  --service-code <ServiceCode> \
  --filters '[{"Type":"TERM_MATCH","Field":"operation","Value":"<OperationValue>"},
              {"Type":"TERM_MATCH","Field":"regionCode","Value":"<workload-region>"}]' \
  --region us-east-1
```

### usagetype-based lookup

```bash
aws pricing get-products \
  --service-code <ServiceCode> \
  --filters '[{"Type":"TERM_MATCH","Field":"usagetype","Value":"<WORKLOAD-PREFIX>-<UsagetypeValue>"}]' \
  --region us-east-1
```

### Empty result = lookup failure = HALT

If the Pricing API returns zero products, **do not proceed**. This is a lookup failure, not a zero-cost result.

```text
if len(products) == 0:
    🚫 HALT — Pricing lookup returned no results
    Do NOT proceed with the paid operation.
    Do NOT improvise a rate from memory, training data, or any other source.
```

> Every operation that returns empty HALTs. There are no exceptions.

> ⚠️ **X-Ray eu-west-3 catalog gap:** `XRay-Traces-Scanned` and `XRay-Traces-Retrieved` do not exist in the AWS Pricing catalog for eu-west-3. This is expected — HALT-on-empty applies, report the gap to the user.

---

## Amazon S3 — usagetype with region prefix

```bash
aws pricing get-products \
  --service-code AmazonS3 \
  --filters '[{"Type":"TERM_MATCH","Field":"usagetype","Value":"<WORKLOAD-PREFIX>-Requests-<TIER>"}]' \
  --region us-east-1
```

**us-east-1 uses a bare value (no prefix):** `Requests-Tier2`. All other regions carry the prefix: `USW2-Requests-Tier2`. If the lookup returns 0 products, HALT.

#### S3 Tier Mapping

| Tier | Operations |
|---|---|
| `Tier1` | PUT, COPY, POST, LIST |
| `Tier2` | GET, SELECT, HEAD |

#### S3 Select (`SelectObjectContent`) — three meters

The request tier prices the **call**, not the bytes. Select needs all three lookups below; `usagetype` is the only viable filter, as these carry an empty `operation` field.

| Component | usagetype | Unit | Formula |
|---|---|---|---|
| Bytes scanned | `<WORKLOAD-PREFIX>-Select-Scanned-Bytes` | GB | `scan_gb × rate` |
| Bytes returned | `<WORKLOAD-PREFIX>-Select-Returned-Bytes` | GB | `returned_gb × rate` |
| Request | `<WORKLOAD-PREFIX>-Requests-Tier2` | Requests | `requests × rate` |

`total = scanned + returned + request`. Bare values in us-east-1, prefixed elsewhere. If any lookup returns 0 products, HALT.

#### Region Prefix Mapping (usagetype-based services: S3, Athena, DynamoDB, PromQL)

| Region | Prefix |
|---|---|
| us-east-1 | *(S3/DynamoDB/PromQL: omit — bare value; Athena: USE1-)* |
| us-east-2 | USE2 |
| us-west-1 | USW1 |
| us-west-2 | USW2 |
| eu-west-1 | EU |
| eu-west-2 | EUW2 |
| eu-west-3 | EUW3 |
| eu-central-1 | EUC1 |
| eu-central-2 | EUC2 |
| eu-north-1 | EUN1 |
| eu-south-1 | EUS1 |
| eu-south-2 | EUS2 |
| ap-southeast-1 | APS1 |
| ap-southeast-2 | APS2 |
| ap-southeast-3 | APS4 |
| ap-southeast-4 | APS6 |
| ap-southeast-5 | APS7 |
| ap-southeast-6 | APS8 |
| ap-southeast-7 | APS9 |
| ap-northeast-1 | APN1 |
| ap-northeast-2 | APN2 |
| ap-northeast-3 | APN3 |
| ap-south-1 | APS3 |
| ap-south-2 | APS5 |
| ap-east-1 | APE1 |
| ap-east-2 | APE2 |
| sa-east-1 | SAE1 |
| ca-central-1 | CAN1 |
| ca-west-1 | CAN2 |
| me-south-1 | MES1 |
| me-central-1 | MEC1 |
| mx-central-1 | MXC1 |
| af-south-1 | AFS1 |
| il-central-1 | ILC1 |

---

## Cross-Region Data Transfer Rate

For any paid operation where the source (workload) region differs from the destination (agent space) region, fetch the live transfer rate. Supplying **both** `fromRegionCode` and `toRegionCode` (plus `transferType` and `toLocationType`) narrows the result to a single deterministic product; a `fromRegionCode`-only filter returns many products and must not be used.

```bash
aws pricing get-products \
  --service-code AWSDataTransfer \
  --filters '[{"Type":"TERM_MATCH","Field":"transferType","Value":"InterRegion Outbound"},
              {"Type":"TERM_MATCH","Field":"fromRegionCode","Value":"<source-region>"},
              {"Type":"TERM_MATCH","Field":"toRegionCode","Value":"<destination-region>"},
              {"Type":"TERM_MATCH","Field":"toLocationType","Value":"AWS Region"}]' \
  --region us-east-1
```

- `<source-region>`: region where data originates (the workload region) — resolve from the resource ARN; do NOT default it
- `<destination-region>`: the agent space region — resolve it explicitly; do NOT hardcode us-east-1
- Select the price dimension with `beginRange: "0"` if multiple are returned
- Cache as `transfer_rate_cache[source_region → destination_region]` — one lookup per route per investigation
- **If the filtered query returns 0 results: 🚫 HALT.** Do NOT improvise a rate. Re-check the region codes and filters, or report the gap.

> Inter-region transfer rates vary widely by geography (roughly $0.01–$0.15/GB depending on source region) — always look up the specific route; never assume a flat rate.

---

## Reference Links

[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/) · [X-Ray](https://aws.amazon.com/xray/pricing/) · [Athena](https://aws.amazon.com/athena/pricing/) · [DynamoDB](https://aws.amazon.com/dynamodb/pricing/on-demand/) · [S3](https://aws.amazon.com/s3/pricing/) · [Lambda](https://aws.amazon.com/lambda/pricing/) · [Data Transfer](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer)
