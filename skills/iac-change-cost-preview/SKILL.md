---
name: "iac-change-cost-preview"
description: "Use this skill whenever a pull request, merge request, branch, or diff changes infrastructure-as-code: CloudFormation, SAM, CDK-synthesized templates, or Terraform. Run it automatically in every Release Readiness Review that touches those files, even if nobody asks about cost, and load it before writing the cost section of a review. Also use it when someone asks what a change adds or removes and what it will do to the AWS bill, even without saying cost (for example 'what does this PR spin up?'), including repos with no CI/CD pipeline. Don't use it for past or current spend, invoices, Cost Explorer, budgets, or rightsizing running resources."
metadata:
  author: inesttia
  version: "1.0.0"
  summary: "Estimates the monthly cost change of an IaC pull request with live AWS Price List rates, in Release Readiness Reviews or on request."
  aws-devops-agent-skills.agent-types: "RELEASE_READINESS_REVIEW, CHAT"
  aws-devops-agent-skills.aws-services: "Amazon EC2, Amazon RDS, Amazon VPC, Amazon S3, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "Cost Optimization, Operations"
---

# Estimating the Monthly Cost Change of an IaC Diff

## When to Use
- **Default behavior — always run this during Release Readiness Review** whenever the change under review touches CloudFormation, CDK-synthesized, SAM, or Terraform template files.
- A user directly asks "what does this PR add or remove" or "how much more or less will this cost per month" (ad hoc, outside a review).
- A user asks to compare a repo's IaC template against the live account topology.

## Workflow

Copy this checklist and work through it in order:

- [ ] Step 1: Get the diff
- [ ] Step 2: First check — compare the before and after templates in the repo
- [ ] Step 3: Second check — compare against live topology, only if the repo comparison isn't enough
- [ ] Step 4: Extract sizing inputs from the templates
- [ ] Step 5: Get live prices
- [ ] Step 6: Flag usage-based and not-determinable cost separately
- [ ] Step 7: Validate and present the results

### Step 1: Get the diff

This skill has two entry paths:

- **Review path (default):** a Release Readiness Review is running on a change that touches IaC template files. Use whatever diff the review already has for the change under review, then proceed to Step 2.
- **Ad hoc path:** a user asks directly about a PR's cost impact outside of a review, including repos with no CI/CD pipeline at all.
  1. Identify the repository and PR/MR number or branch from the user's request. If it's ambiguous, ask.
  2. Fetch the before/after state of the IaC templates touched by the PR with repository tools directly (list repositories, get the PR/branch diff, read file contents). Don't wait for or assume a pipeline-triggered review will supply this. Rely on branch/ref diffs rather than commit-history search, which may be unavailable on shallow clones.
  3. Proceed to Step 2 with the diff you fetched.
  4. If the PR touches no IaC template files at all, say so plainly: there's nothing to price. Don't guess at resources from application code changes.

### Step 2: First check — compare the before and after templates in the repo

The "before" is the template on the PR's base branch; the "after" is the template on the PR branch. Match resources by logical ID (Terraform: resource address) and put each one in exactly one class:
- **Added:** in the after template, not in the before. Cost goes **up** by its monthly cost.
- **Removed:** in the before template, not in the after. Cost goes **down** by its monthly cost.
- **Resized:** same logical ID, and a cost-relevant property changed: instance type/class, engine, Multi-AZ, storage type/size, provisioned IOPS/throughput, node/replica/shard count, desired capacity. Cost changes by **after minus before**.
- **Unchanged for cost:** same logical ID, only non-cost properties changed (tags, policies, descriptions). Not priced; give the count only.

Rules for edge cases:
- **Whole files:** if the template file itself is new, every resource in it is Added. If the file is deleted, every resource in it is Removed.
- **Honor Conditions and parameter defaults on both sides.** A `Condition`-gated resource only deploys if the condition is true at deploy time.
  - Evaluate conditions against the parameter defaults (or the values the change supplies) for both the before and the after template.
  - A resource whose condition flips from false to true counts as Added; true to false counts as Removed.
  - Exclude resources that would NOT be created at the assumed parameters, and call out any whose creation depends on a non-default parameter.

The result of this step is the **repo-based estimate**: + Added, − Removed, ± Resized, and the net.

### Step 3: Second check — compare against live topology, only if the repo comparison isn't enough

The repo-based estimate from Step 2 is the default answer. Run this check only if at least one of these is true, and record which one:
- **No usable base version:** the base-branch template couldn't be fetched (no git history, missing branch, API error, truncated diff).
- **New, renamed or moved template with a known stack name:** the repo names the stack it deploys to (deploy workflow, `samconfig.toml`, CDK stack ID), and the base branch has no matching template, so that stack may already exist.
- **Explicit physical names on Added resources** (`RoleName`, `BucketName`, `DBInstanceIdentifier`, `Name`, …): the repo can't tell whether that name is already taken in the account.
- **Conflicting signals:** the template, PR description or commit messages say the change modifies resources the base branch doesn't contain (for example "moves the table to provisioned capacity").
- **The user asks** to compare with the live account.

If none applies, skip this step, report "topology check not needed" with the reason, and use the repo-based estimate as the final result. When the check does run, it uses read-only calls only. Apply this matching discipline in order:
- **Logical-ID matching ONLY works if the template is deployed as a tracked stack.** Logical IDs live in CloudFormation stack metadata, not on raw resources. First check for a deployed stack (`cloudformation describe_stacks`/`list_stacks` → `describe_stack_resources`); if present, map logical ID → physical ID from the stack and compare.
- **If no stack is deployed, match by the template's EXPLICIT physical name/tags.** Pull the declared name and Tags, and look the resource up by that exact name (e.g. `iam get_role`, `rds describe_db_instances`).
- **Use exact-name equality — never prefix/substring/fuzzy matching.** Accounts often contain suffix-siblings from other provisioning paths (e.g. an SDK that appends `-<suffix>`). Treating `Foo-abc123` as a match for a declared `Foo` would wrongly classify a genuinely-new resource as already-deployed and drop it from the estimate. Require the physical name (ideally plus a managing tag) to match exactly.
- **If the name is auto-generated AND no stack is deployed, there is nothing to match against.** Say so explicitly and keep the Step 2 classification, but flag this as an assumption, not a confirmed topology match.

Apply the outcomes to the repo-based estimate:
- **Added, not found:** confirmed new; keep it in the cost increase.
- **Added, found (exact match):** already deployed; move it out of the total and list it separately. If it was found by name outside any stack, also warn that a CloudFormation create will fail on an existing name unless the resource is imported.
- **Removed, found:** confirmed; keep it in the cost decrease.
- **Removed, not found:** it was never deployed or is already gone; move it out of the savings and list it separately.
- **Resized, stack deployed:** if the deployed property value (from describing the physical resource) differs from the repo's before value, use the deployed value as "before" and say so.
- **Check needed but account context unavailable:** keep the repo-based estimate unchanged and say explicitly that the second check was skipped, why it was needed, and the error.

The result of this step is the **topology-confirmed estimate**.

### Step 4: Extract sizing inputs from the templates

For Added resources, read the after template; for Removed resources, read the before template; for Resized resources, read both. Pull whatever sizing properties are declared: instance class/type, allocated storage, provisioned IOPS/throughput, memory/CPU, replica count, region. These drive the pricing query. When a sizing value is a `!Ref` parameter or `!Sub`/`!If` expression rather than a literal, resolve it from the parameter default and label the estimate as default-derived.

### Step 5: Get live prices — the only source of dollar figures

For every price line (Added, Removed, and both sides of Resized), use three live sources in this order, and record which one produced each rate:
1. Public AWS pricing documentation, through `verify_aws_claim` (5a).
2. The AWS Price List API, as the fallback when 5a doesn't give a usable rate (5b).
3. The public Price List offer files, downloaded over HTTPS with no AWS credentials, when 5b can't run (5c).

**5a. Look up the rate in public AWS pricing documentation (first choice).** If a `verify_aws_claim` tool is available in this runtime, read the **5a** section of [references/pricing-sources.md](references/pricing-sources.md) first; it has the request phrasing and the acceptance checks. Then call the tool for each price line, asking for the rate without stating any price. If the result fails any acceptance check, use 5b for that line.

**5b. Fall back to the AWS Price List API.**

*Probe access the first time a price line falls back (mandatory).* Use whatever AWS tool this runtime provides. It may be named `use_aws`, `call_aws`, or similar, and may take structured parameters (service `pricing`, operation `describe_services` / `DescribeServices`) or an AWS CLI command (`aws pricing describe-services --service-code AmazonEC2 --region us-east-1`).
- Call `describe_services` with `ServiceCode=AmazonEC2` against the Price List endpoint in `us-east-1`.
- If that call fails, retry the same call against `eu-central-1`, then `ap-south-1`. The Price List API is served from all three; the endpoint has nothing to do with where the priced resource runs. Use the first endpoint that succeeds for every pricing call in this run.
- If all three fail, record the **exact error message and code** from each attempt (for example `AccessDeniedException ... not authorized to perform: pricing:DescribeServices`, `Region not allowed`, or "no AWS tool available in this runtime"). Then price every remaining line with 5c. A missing AWS tool, an HTTP 500 from the credential endpoint, or "credentials could not be loaded" all mean 5b can't run, but none of them blocks 5c.
- **Never write "pricing unavailable" unless 5a, this probe, and 5c were all actually attempted and failed.** The output must quote each error.

*Attempted means a real call was made.* A source counts as attempted only if you called it and recorded its error. If this phase has no shell, HTTP, or AWS tool, write `not attempted in this phase: <missing tool>` for that source. Do not describe the environment as unreachable, and do not propose a network or IAM fix for a source you never called. In a Release Readiness Review, verification testing may price the change if the repository's `AGENTS.md` asks for an "IaC cost estimate" test (the README shows the snippet). If that result already exists in your context, build the dashboard from it and cite the test as the source. If not, use the ⏭️ banner from [assets/output-template.md](assets/output-template.md), not the ⛔ one.

*Price each line that fell back.*
- Use `get_products` with `ServiceCode` (e.g. `AmazonEC2`, `AmazonRDS`, `AmazonElastiCache`) and `Filters` matching the resource's declared attributes — instance type/class, `location` (the resource's real region, e.g. "US East (N. Virginia)"), operating system, database engine, deployment option, tenancy, etc.
- If unsure of exact filter values or available attributes, call `describe_services` (list attribute names for a service) or `get_attribute_values` (list allowed values for an attribute) first — `get_products` filters require exact string matches.
- Parse the result: `PriceList` entries are JSON strings → `terms.OnDemand` → a term → `priceDimensions` → a dimension → `pricePerUnit.USD`. That's the USD/hour rate for compute-style resources; multiply by 730 for a monthly estimate. Storage/IOPS-billed resources may return a per-GB or per-IOPS rate instead — apply it to the template's declared size.
- **Disambiguate multiple SKUs — select the base usage SKU.** `get_products` often returns several `PriceList` entries for one resource. Pick the base on-demand line (usagetype of the form `[region-prefix-]BoxUsage:<type>`, `InstanceUsage:<type>`, `Multi-AZUsage:<type>`, or `NodeUsage:<type>` for the resource's own region) and DISCARD surcharge/variant SKUs: `ExtendedSupport*`, `UnusedBox`/capacity-reservation, Dedicated Host, etc. Taking the first entry can badly overstate or understate cost, because surcharge SKUs (such as ElastiCache Extended Support) carry a different rate than the base node, and reservation SKUs can show a zero rate.
- **Normalize units before multiplying.** Read the price dimension's `unit` and reconcile it against the human-readable `description` before applying it to a declared size. Units are not always what they appear: EBS gp3 throughput is priced with `unit: GiBps-mo`, while its description states the rate per provisioned MiBps-month and templates declare throughput in MiB/s. Multiplying `pricePerUnit.USD` directly by the declared MiB/s overcharges by the GiB-to-MiB factor; divide the per-GiBps rate by 1024 to get the per-MiBps rate, and confirm it matches the description. Convert the rate and the declared quantity into the same unit (GiB↔MiB, per-hour↔per-month) first.
- **Skip free-tier price dimensions.** Some SKUs carry a zero-priced tier followed by a paid tier on the same SKU. For example, DynamoDB provisioned capacity lists a free first block of read and write units. Use the paid dimension (its description says "beyond the free tier", or its `beginRange` is above zero), because this estimate excludes free tier.

**5c. Last fallback: public Price List offer files (no AWS credentials needed).** Use this for every line still unpriced after 5a and 5b. Fetch `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<ServiceCode>/current/<region-code>/index.csv` with an HTTP GET from the shell (never HEAD; some sandboxes block HEAD while allowing GET). Stream the file line by line, keep only rows where `TermType` is `OnDemand`, and apply the same SKU selection, free-tier, and unit rules as 5b. Read the **5c** section of [references/pricing-sources.md](references/pricing-sources.md) when you reach this step; it has the CSV column names, the service codes, and what to record in the Pricing trace.

### Step 6: Flag usage-based and not-determinable cost separately

Call out resources whose cost is dominated by runtime usage (Lambda invocations, S3 requests, data transfer, NAT Gateway data processing, DynamoDB on-demand) as "usage-dependent — no fixed monthly figure available, cost scales with volume" rather than assigning them any baseline number. For resources that have BOTH a fixed and a usage component (e.g. a NAT Gateway: fixed hourly + per-GB data processing), price the fixed part (×730) and flag the usage part separately.

If none of the three sources returns a usable rate for a fixed-price line, retry 5b once with `get_attribute_values` to find the exact filter value. If it's still unresolved, mark the line *not determinable* and give the reason from each source; never substitute a remembered or estimated number.

### Step 7: Validate and present the results

**One dashboard per diff.** Before writing, check whether this review already contains an IaC cost dashboard for the same diff. If it is priced, don't produce another; reference it. If it is unpriced and yours is priced, produce yours and state that it supersedes the earlier one.

**The cost dashboard below is the only accepted output format.** It is mandatory on every entry path, and it applies whether or not any price could be fetched. You MUST produce exactly this structure: the same nine sections, in the same order, with the same headings and the same table columns. Do not replace any table with prose or bullet points, do not drop, rename or reorder columns, and do not summarize the cost in a sentence or in a short "Metric / Value" table outside this dashboard. In a Release Readiness Review, add the dashboard as its own section of the review output; do not merge it into the risk findings.

Read [assets/output-template.md](assets/output-template.md) before writing the output. It holds the full template with every Summary row, the formatting rules (one row per price line, money format, traceability, Total rows, empty sections), and the rules for the ⛔ banner. If you can't open it, build the dashboard from this skeleton, keeping all nine sections:

```markdown
## 💰 IaC cost impact · <repo> · <PR number or branch>
> ⛔ **Pricing not available in this run.** <source: exact error> · <source: exact error> · <source: exact error>. **Fix:** <one specific action>   ← only when every source was actually called and failed; then write `not priced` in every money cell
> ⏭️ **Not priced in this phase.** <source: not attempted (<missing tool>)> · … **If verification testing ran the "IaC cost estimate" test, its dashboard is the priced result; otherwise re-run with pricing access.**   ← when this phase lacks the tools; no Fix line
### 📊 Summary
| Metric | Value |
| **Net monthly change** | **≈ <+/−>$<amount> / month** |   ← then rows for Repo-based net, Topology adjustment, ➕ Added, ➖ Removed, 🔁 Resized, Unchanged for cost, 📈 Usage-dependent, ❔ Not determinable, Pricing Region, Baseline, Price source
### ➕ Added resources
| # | Logical ID | Type | Sizing | Qty | Rate | Monthly | Price ref |   ← every money table ends with a bold **Total** row
### ➖ Removed resources   ← same columns as Added, with R<n> refs and negative amounts
### 🔁 Resized resources
| # | Logical ID | Type | Change (before → after) | Before monthly | After monthly | Delta | Topology check | Price refs |
### 🔎 Topology adjustments (second check)
| Ref | Logical ID | First-check class | Finding | Effect on total |   ← or `_Topology check not needed: <reason>._` when it didn't run
### 🧾 Pricing trace
| Ref | Used by | Query or filters sent | Rate (USD) | Unit | Monthly |
### 📈 Usage-dependent (not in total)
| Logical ID | Type | Billed on | Fixed part priced in |   ← keep every heading when empty and write `_None._` under it
### ❔ Not determinable / conditional (not in total)
| Logical ID | Type | Reason | Candidates seen |
### ⚠️ Caveats
```

**Arithmetic check before output:**
- Each table total equals the sum of its rows.
- Repo-based net = Added total + Removed total + Resized total.
- Net change = repo-based net + total topology adjustment.
- Every number in the Summary equals the matching table total.

If any check fails, fix it before presenting.

## Important Caveats to Always Include
- Every dollar figure in the output must be traceable to a specific live lookup made during this run: a `verify_aws_claim` result with its AWS source URL, a `get_products` call, or a row read from an AWS Price List offer file downloaded in this run. Never use a number recalled from training data or a static table.
- Rates taken from AWS pricing pages can be rounded or update later than the Price List API; the Summary's Price source row shows how many lines came from each source.
- The repo-based estimate assumes the base branch matches what is deployed; the topology check runs only when the repo comparison isn't enough, and corrects this only where it can find the resource.
- Conditional/parameterized template resources that only resolve at deploy time may be missed or misclassified.
- Always state which region's pricing the estimate assumes (ask if not inferable from the template).
- Never present the estimate as a guaranteed bill impact. Use language like "roughly", "estimated", "ballpark", even when sourced from live pricing, because discounts and usage variability aren't captured.
