# Pricing Data Acquisition: AWS Price List

How the skill obtains authoritative, current rates without per-request
charges. The skill reads the Price List Query API through the AWS CLI
(SKILL.md Step 1). This file explains the Query API output, the Bulk API
files an operator can fetch without credentials when the `pricing:` actions
are not granted, the offer codes, and the validation rules the agent applies
to either source, so results can be verified and failures diagnosed. No
script ships with the skill; every step below is a CLI call or a plain HTTPS
download.

## Contents

1. Rate sources
2. Bulk API endpoint structure (operator path)
3. Offer codes for Media Services
4. Price file structure (JSON and CSV)
5. Validation rules the agent applies
6. Known pitfalls
7. Alternatives and when to mention them

## 1. Rate sources

Three candidate sources for rates. The skill uses the Query API; the Bulk
API is the credential-free fallback an operator can fetch by hand:

| Source | IAM needed | Cost | Fit |
|---|---|---|---|
| Price List Query API (`aws pricing ...`) | `pricing:DescribeServices`, `pricing:GetProducts`; endpoints in us-east-1 / eu-central-1 / ap-southeast-1 / ap-south-1 | Free | YES: SKILL.md Step 1, granted for this skill in the shared IAM template |
| Price List Bulk API (HTTPS files) | None | Free | Operator fallback when the `pricing:` actions are not granted; the operator downloads the region-scoped file and pastes back what the review needs |
| Cost Explorer (`ce:GetCostAndUsage`) | `ce:*`, often payer-account scoped | $0.01 per paginated request; cannot be un-enabled once enabled | NEVER by default; customer-driven only |

The bulk files are plain HTTPS GETs against
`pricing.us-east-1.amazonaws.com` and require no credentials at all.

## 2. Bulk API endpoint structure (operator path)

```
Offer index (all services):
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json

Region index for one service:
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<offerCode>/current/region_index.json

Region-scoped price file (preferred):
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<offerCode>/current/<regionCode>/index.json
  ...or index.csv

Full-service price file (avoid; can be very large):
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<offerCode>/current/index.json
```

All `currentVersionUrl` values inside index files are relative to
`https://pricing.us-east-1.amazonaws.com`. The `current` alias always
points at the latest published version; each file carries its own
`publicationDate` and version. Publication cadence is roughly monthly,
plus ad hoc updates.

Always prefer the region-scoped file. It contains every SKU available in
that region, including the related global SKUs, and is dramatically
smaller than the full-service file. Either the JSON or the CSV form works;
CSV is easier to skim by hand.

## 3. Offer codes for Media Services

The offer code is the URL path segment AND the `servicecode` attribute on
each SKU. The prefix is NOT uniform across Media Services:

| Service | Offer code | Verification status |
|---|---|---|
| MediaLive | `AWSElementalMediaLive` | Consistent with CUR service code |
| MediaPackage | `AWSElementalMediaPackage` | Consistent with CUR service code |
| MediaTailor | `AWSElementalMediaTailor` | Consistent with CUR service code |
| CloudFront | `AmazonCloudFront` | Consistent with CUR service code |
| MediaConnect | `AWSMediaConnect` (expected) | UNVERIFIED against a live index fetch as of 2026-07. Corroborated by the boto3 pricing ServiceCode, SDK naming, and CUR references, but the "Elemental" prefix is dropped and this has not been confirmed by reading the live offer index |

Because of the MediaConnect uncertainty, and because AWS may add or rename
offers, never assume a single code. Confirm it in the live catalog first
(`aws pricing describe-services`, or the Bulk API offer index), try the
candidates above, and fall back to a case-insensitive substring match on all
service codes (for example, any code containing `mediaconnect`). If no
candidate resolves, report the service as a pricing DATA GAP.

MediaConnect Router SKUs live inside the MediaConnect offer file; there is
no separate Router offer code. Router products are distinguished by
product family and usage type attributes.

CloudFront is a global service: its region index may not contain the
pipeline's region code. Fall back to the global/full current file for
CloudFront (large), or use the Query API with `Field=location,Value=Global`.

## 4. Price file structure

### JSON form

```
{
  "formatVersion": "v1.0",
  "publicationDate": "<ISO8601>",
  "version": "<yyyymmddhhmmss>",
  "products": {
    "<SKU>": {
      "sku": "<SKU>",
      "productFamily": "<family>",
      "attributes": { "servicecode": "...", "location": "US East (N. Virginia)", "usagetype": "...", "operation": "...", ...service-specific keys }
    }
  },
  "terms": {
    "OnDemand": {
      "<SKU>": {
        "<SKU>.<offerTermCode>": {
          "priceDimensions": {
            "<rateCode>": {
              "description": "...",
              "beginRange": "0", "endRange": "Inf",
              "unit": "Hrs" | "GB" | ...,
              "pricePerUnit": { "USD": "0.1600000000" }
            }
          },
          "termAttributes": {}
        }
      }
    },
    "Reserved": {
      ... same shape; termAttributes carries LeaseContractLength,
      PurchaseOption, OfferingClass
    }
  }
}
```

### CSV form

Five metadata lines precede the header row:

```
"FormatVersion","v1.0"
"Disclaimer","..."
"Publication Date","<ISO8601>"
"Version","<version>"
"OfferCode","<offerCode>"
"SKU","OfferTermCode","RateCode","TermType","PriceDescription",
"EffectiveDate","StartingRange","EndingRange","Unit","PricePerUnit",
"Currency","RelatedTo","LeaseContractLength","PurchaseOption",
"OfferingClass","Product Family","serviceCode","Location", ...
```

One row per rate. Service-specific attribute columns follow the common
columns and differ per offer. Read header names rather than positions.

## 5. Validation rules the agent applies

Apply these to Query API output and to any Bulk API file an operator pastes
back.

1. Offer code resolved from the live catalog or index, never assumed.
2. `publicationDate` and version captured and emitted; every downstream
   report must cite them.
3. Currency asserted: rows without a USD price are excluded and counted;
   a source with zero USD rates fails validation and becomes a DATA GAP.
4. Prices parse as non-negative decimals.
5. Tier ranges (`StartingRange`/`EndingRange`, `beginRange`/`endRange`)
   preserved verbatim so cost math can sum tier by tier.
6. Term types restricted to known values (`OnDemand`, `Reserved`);
   unknown types are kept but flagged in the summary.
7. Zero-price rows are retained (legitimate: free tiers, all-upfront
   reserved recurring rates) but never silently treated as "free service";
   interpret with the per-service reference.
8. Freshness: cite the `publicationDate` of the data used in the report.
   Re-fetch rather than reuse figures older than 24 hours.

## 6. Known pitfalls

- **`location` uses human names** ("US East (N. Virginia)"), not region
  codes. Using region-scoped files avoids needing the mapping at all.
- **Attribute names differ between SKU families** within one offer
  (MediaLive input SKUs vs output SKUs carry different attribute sets:
  codec, resolution, bitrate tier, videoQuality). Match SKUs by
  productFamily plus attributes, never by description text alone.
- **Tiered rates**: CloudFront egress and several data-transfer families
  are tiered. Multiplying total volume by the first-tier rate understates
  nothing and overstates cost at scale; always sum per tier.
- **Reserved $0.00 rows**: an all-upfront reservation shows a $0.00
  recurring dimension plus a Quantity-unit upfront dimension. Read
  termAttributes before concluding anything is free.
- **"Initialize from source" frame-rate trap** (MediaLive): a channel
  configured to initialize from source provisions for >30fps and bills at
  the higher rate tier even when actual content is 30fps or lower. The
  30fps vs 30-60fps distinction also applies to reservation matching.
- **Idle vs running SKUs are distinct usage types** in the MediaLive
  offer. Match rates to observed resource state, not just resource type.
- **Fixed vs metered dimensions**: unit values vary (Hrs, GB, Count,
  Quantity). Never assume hourly.

## 7. Alternatives and when to mention them

- **Query API**: with the `pricing:` read actions granted for this skill,
  `aws pricing get-products --service-code <code> --region us-east-1` with
  a `regionCode` filter returns the same SKUs and terms without any file
  download. This is the path SKILL.md Step 1 uses. The validation rules in
  section 5 apply to its output just as they do to the bulk files.
- **SNS price-change notifications**: customers wanting standing pricing
  automation can subscribe to the AWS price list SNS topics. Mention only
  if asked about keeping estimates current.
- **Cost Explorer / CUR**: billing-grade actuals. Customer-driven only;
  state the per-request charge and access caveats whenever mentioning it.
