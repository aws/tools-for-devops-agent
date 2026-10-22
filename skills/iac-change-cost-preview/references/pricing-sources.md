# Pricing sources: full procedure for 5a and 5c

Read the **5a** section when a `verify_aws_claim` tool exists in the runtime, and the **5c** section when you reach the offer-file fallback.

## 5a. Look up the rate in public AWS pricing documentation (first choice)

- If a `verify_aws_claim` tool is available in this runtime, call it for each price line.
  - Phrase the request as a lookup that contains no price, for example: "Current on-demand price per hour for Amazon RDS for PostgreSQL db.r6g.large, Multi-AZ, in eu-west-1, from the official AWS pricing page."
  - Include the service, the type or class, and the engine, deployment option, OS/tenancy or storage type as relevant. Also include the Region code and the billing dimension (per hour, per GB-month, per key-month, …).
- **Never put a dollar amount in the request.** Any number written into the claim would come from memory. If the tool only accepts a claim with a value to verify and can't return a rate on its own, treat 5a as unavailable for this run and use 5b for every price line.
- **Accept the result only if all of these hold:**
  - It states an explicit numeric rate and its unit.
  - It cites a source URL on an official AWS domain (`aws.amazon.com/…/pricing/` or `docs.aws.amazon.com`).
  - The configuration it priced matches the resource exactly: service, type/class, engine, deployment option, OS/tenancy, storage type, and **Region**.
  - It's the on-demand rate, not a Savings Plans, Reserved Instance, free tier, or "starting at" figure.
- If any check fails, use 5b for that price line and note the reason (for example "docs: Region not stated" or "docs: no rate returned").
- If `verify_aws_claim` is missing or returns an error (not just an unusable result), record the exact error once and use 5b for all remaining price lines. Don't retry it for every resource.
- Rates on pricing pages are usually stated in the unit the template uses (for example per MiBps-month for gp3 throughput). Still confirm the unit before multiplying.

## 5b. AWS Price List API

See SKILL.md Step 5, section **5b**. It contains the mandatory access probe, the endpoint fallback order, the `get_products` query and parsing rules, SKU disambiguation, unit normalization, and the free-tier rule.

## 5c. Last fallback: public Price List offer files (no AWS credentials needed)

Use this for every line still unpriced after 5a and 5b. These files hold the same official on-demand prices the Price List API serves, published for anyone to download.

- **URL:** `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<ServiceCode>/current/<region-code>/index.csv`. Examples: `AmazonEC2` (instances, EBS, NAT gateway), `AmazonRDS`, `AmazonElastiCache`, `AWSELB`, `AmazonVPC` (public IPv4, VPC endpoints), `AmazonDynamoDB`, `awskms`, `AmazonCloudWatch`, `AWSSecretsManager`, `AmazonEKS`.
- **Fetch it with an HTTP GET** from the shell or a Python tool. Some sandboxes block HEAD requests while allowing GET, so never use HEAD to decide that a host is unreachable.
- **Stream the file line by line; never load it whole.** The EC2 file for a single Region is several hundred MB, but a streaming CSV pass needs very little memory.
  - Skip the metadata lines before the header row (the header starts with `"SKU"`), and note the `Publication Date` from those metadata lines.
  - Keep only rows where `TermType` is `OnDemand`.
  - Price all the lines for one service in a single pass over its file.
- **Filter columns:** filter on the CSV columns that correspond to the API attributes: `Product Family`, `Instance Type`, `Operating System`, `Tenancy`, `CapacityStatus`, `Pre Installed S/W`, `License Model`, `Database Engine`, `Deployment Option`, `Cache Engine`, `Volume Type`, `Volume API Name`, `usageType`.
  - The rate is in `PricePerUnit`, with `Unit`, `PriceDescription`, `StartingRange` and `EndingRange`.
  - Usage types carry Region prefixes (for example `EU-BoxUsage:<type>`), so match `usageType` by suffix.
- **Apply the same SKU selection, free-tier and unit rules as 5b.**
- **Pricing trace:** record the filters applied.
- **Download fails:** record the exact error (HTTP status or network message).
