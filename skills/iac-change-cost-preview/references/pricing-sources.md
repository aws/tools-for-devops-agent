# Pricing sources: SKU, unit and free-tier rules (5a), offer files (5b), docs (5c)

Read the **5a** section before using any Price List API result, the **5b** section when the Price List API can't run and you fall back to the offer files, and the **5c** section when lines are still unpriced and a `verify_aws_claim` tool exists.

## 5a. AWS Price List API (first choice)

SKILL.md Step 5, section **5a**, has the mandates: probe once, record exact errors, fall through to 5b, never write "pricing unavailable" without attempting every source. This section has the mechanics.

**Access probe.** Use whatever AWS tool this runtime provides. It may be named `use_aws`, `call_aws`, or similar, and may take structured parameters (service `pricing`, operation `describe_services` / `DescribeServices`) or an AWS CLI command (`aws pricing describe-services --service-code AmazonEC2 --region us-east-1`).
- Call `describe_services` with `ServiceCode=AmazonEC2` against the Price List endpoint in `us-east-1`.
- If that call fails, retry the same call against `eu-central-1`, then `ap-south-1`. The Price List API is served from all three; the endpoint has nothing to do with where the priced resource runs.
- If all three fail, record the exact error message and code from each attempt (for example `AccessDeniedException ... not authorized to perform: pricing:DescribeServices`, `Region not allowed`, or "no AWS tool available in this runtime").

**Query and parse.**
- Use `get_products` with `ServiceCode` (e.g. `AmazonEC2`, `AmazonRDS`, `AmazonElastiCache`) and `Filters` matching the resource's declared attributes — instance type/class, `location` (the resource's real region, e.g. "US East (N. Virginia)"), operating system, database engine, deployment option, tenancy, etc.
- If unsure of exact filter values or available attributes, call `describe_services` (list attribute names for a service) or `get_attribute_values` (list allowed values for an attribute) first — `get_products` filters require exact string matches.
- Parse the result: `PriceList` entries are JSON strings → `terms.OnDemand` → a term → `priceDimensions` → a dimension → `pricePerUnit.USD`. That's the USD/hour rate for compute-style resources; multiply by 730 for a monthly estimate. Storage/IOPS-billed resources may return a per-GB or per-IOPS rate instead — apply it to the template's declared size.

**Result rules.** Apply the three rules below to every `get_products` result before multiplying a rate. They apply unchanged to 5b offer-file rows.

- **Disambiguate multiple SKUs — select the base usage SKU.** `get_products` often returns several `PriceList` entries for one resource. Pick the base on-demand line (usagetype of the form `[region-prefix-]BoxUsage:<type>`, `InstanceUsage:<type>`, `Multi-AZUsage:<type>`, or `NodeUsage:<type>` for the resource's own region) and DISCARD surcharge/variant SKUs: `ExtendedSupport*`, `UnusedBox`/capacity-reservation, Dedicated Host, etc. Taking the first entry can badly overstate or understate cost, because surcharge SKUs (such as ElastiCache Extended Support) carry a different rate than the base node, and reservation SKUs can show a zero rate.
- **Normalize units before multiplying.** Read the price dimension's `unit` and reconcile it against the human-readable `description` before applying it to a declared size. Units are not always what they appear: EBS gp3 throughput is priced with `unit: GiBps-mo`, while its description states the rate per provisioned MiBps-month and templates declare throughput in MiB/s. Multiplying `pricePerUnit.USD` directly by the declared MiB/s overcharges by the GiB-to-MiB factor; divide the per-GiBps rate by 1024 to get the per-MiBps rate, and confirm it matches the description. Convert the rate and the declared quantity into the same unit (GiB↔MiB, per-hour↔per-month) first.
- **Skip free-tier price dimensions.** Some SKUs carry a zero-priced tier followed by a paid tier on the same SKU. For example, DynamoDB provisioned capacity lists a free first block of read and write units. Use the paid dimension (its description says "beyond the free tier", or its `beginRange` is above zero), because this estimate excludes free tier.

## 5b. Public Price List offer files (no AWS credentials needed)

Use this when 5a can't run, and for any line 5a left unpriced. These files hold the same official on-demand prices the Price List API serves, published for anyone to download.

- **URL:** `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<ServiceCode>/current/<region-code>/index.csv`. Examples: `AmazonEC2` (instances, EBS, NAT gateway), `AmazonRDS`, `AmazonElastiCache`, `AWSELB`, `AmazonVPC` (public IPv4, VPC endpoints), `AmazonDynamoDB`, `awskms`, `AmazonCloudWatch`, `AWSSecretsManager`, `AmazonEKS`.
- **Fetch it with an HTTP GET** from the shell or a Python tool. Some sandboxes block HEAD requests while allowing GET, so never use HEAD to decide that a host is unreachable.
- **Stream the file line by line; never load it whole.** The EC2 file for a single Region is several hundred MB, but a streaming CSV pass needs very little memory.
  - Skip the metadata lines before the header row (the header starts with `"SKU"`), and note the `Publication Date` from those metadata lines.
  - Keep only rows where `TermType` is `OnDemand`.
  - Price all the lines for one service in a single pass over its file.
- **Filter columns:** filter on the CSV columns that correspond to the API attributes: `Product Family`, `Instance Type`, `Operating System`, `Tenancy`, `CapacityStatus`, `Pre Installed S/W`, `License Model`, `Database Engine`, `Deployment Option`, `Cache Engine`, `Volume Type`, `Volume API Name`, `usageType`.
  - The rate is in `PricePerUnit`, with `Unit`, `PriceDescription`, `StartingRange` and `EndingRange`.
  - Usage types carry Region prefixes (for example `EU-BoxUsage:<type>`), so match `usageType` by suffix.
- **Apply the same SKU selection, free-tier and unit rules as 5a.**
- **Pricing trace:** record the filters applied.
- **Download fails:** record the exact error (HTTP status or network message).

## 5c. Last resort: public AWS pricing documentation

Only for lines still unpriced after 5a and 5b, and only if a `verify_aws_claim` tool is available in this runtime. Pricing pages can be rounded and update later than the Price List, so a rate from here is marked `docs` in the Pricing trace.

- Call the tool once per unpriced line.
  - Phrase the request as a lookup that contains no price, for example: "Current on-demand price per hour for Amazon RDS for PostgreSQL db.r6g.large, Multi-AZ, in eu-west-1, from the official AWS pricing page."
  - Include the service, the type or class, and the engine, deployment option, OS/tenancy or storage type as relevant. Also include the Region code and the billing dimension (per hour, per GB-month, per key-month, …).
- **Never put a dollar amount in the request.** Any number written into the claim would come from memory. If the tool only accepts a claim with a value to verify and can't return a rate on its own, treat 5c as unavailable for this run.
- **Accept the result only if all of these hold:**
  - It states an explicit numeric rate and its unit.
  - It cites a source URL on an official AWS domain (`aws.amazon.com/…/pricing/` or `docs.aws.amazon.com`).
  - The configuration it priced matches the resource exactly: service, type/class, engine, deployment option, OS/tenancy, storage type, and **Region**.
  - It's the on-demand rate, not a Savings Plans, Reserved Instance, free tier, or "starting at" figure.
- If any check fails, the line is not determinable; note the reason (for example "docs: Region not stated" or "docs: no rate returned").
- If `verify_aws_claim` is missing or returns an error, record the exact error once. Don't retry it for every resource.
- Rates on pricing pages are usually stated in the unit the template uses (for example per MiBps-month for gp3 throughput). Still confirm the unit before multiplying.
