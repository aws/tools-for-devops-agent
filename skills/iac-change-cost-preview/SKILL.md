---
name: "iac-change-cost-preview"
description: "Use this skill whenever a pull request, merge request, branch, or diff changes infrastructure-as-code: CloudFormation, SAM, CDK-synthesized templates, or Terraform. Run it automatically inside every Release Readiness Review that touches those files, even if nobody asks about cost, and load it before writing the cost section of a review. Also use it when someone asks what a change adds or removes and what it will do to the AWS bill, even without saying cost (for example 'what does this PR spin up?'), including repos with no CI/CD pipeline. Don't use it for past or current spend, invoices, Cost Explorer, budgets, or rightsizing running resources."
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
- **Not** when a user in chat only asks to start a Release Readiness Review: start the review and don't run this skill in chat; the review runs it. Run it in chat only when the user also asks about cost or what the change adds or removes.

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

**Identify the change first, on every path.** Before Step 2, establish the repository (`owner/repo`), the PR number or branch, and the base and head revisions. In a review, take them from the review itself (it names `<base>@<sha> → <head>@<sha>`); in chat, from the user's request or the PR. If your working copy has no git history or no base, get the base version with the repository tools (fetch the repository at the base branch or commit, or compare the two revisions through the Git provider) and diff against it. A missing local history is never "no base": classify every resource as Added only when the base branch really has no such template.

This skill has two entry paths:

- **Review path (default):** a Release Readiness Review is running on a change that touches IaC template files. Use whatever diff the review already has for the change under review, then proceed to Step 2. If you are planning or running the review's verification tests, always add a test named "IaC cost impact", run Steps 2 to 7 in it, and report the full dashboard as the test result. Verification testing has a shell and internet access, so when the Price List API fails, price every line from the offer files (5b) instead of stopping.
- **Ad hoc path:** a user asks directly about a PR's cost impact outside of a review, including repos with no CI/CD pipeline at all.
  1. Identify the repository and PR/MR number or branch from the user's request. If it's ambiguous, ask.
  2. Fetch the before/after state of the IaC templates touched by the PR with repository tools directly (list repositories, get the PR/branch diff, read file contents). Don't wait for or assume a pipeline-triggered review will supply this. Rely on branch/ref diffs rather than commit-history search, which may be unavailable on shallow clones.
  3. Proceed to Step 2 with the diff you fetched.
  4. If the PR touches no IaC template files at all, say so plainly: there's nothing to price. Don't guess at resources from application code changes.

**What this skill can price.** It prices templates: CloudFormation and SAM YAML/JSON, the CloudFormation templates CDK synthesizes (`cdk.out/*.template.json`), and Terraform configuration. It does not read CDK source code (`.ts`, `.py`, `.java`, `.go`, `.cs` under a CDK app), because one construct expands into resources and defaults that only appear after `cdk synth`.

**CDK source without a synthesized template (both paths):** if the PR changes CDK code and the diff contains no `cdk.out/*.template.json`, do not infer resources from the code. In a Release Readiness Review, verification testing can run `cdk synth` on the base and PR branches and diff the generated templates, if its sandbox has Node, the CDK CLI and the app's dependencies; then proceed to Step 2 with those templates. In chat, or when synth isn't possible, say plainly that the change can't be priced until a synthesized template is available, and suggest committing `cdk.out` or having CI attach the synthesized template to the PR. Still produce the Step 7 dashboard with the ❔ section listing the CDK stacks as not determinable.

**Terraform** (diff touches `.tf`, `.tf.json` or `.tfvars`):
- **Plan JSON first.** If the PR has `terraform show -json plan.out` attached, use it and skip HCL reading: `resource_changes[].address` is the identity; `change.actions` gives the class (`create` Added, `delete` Removed, `update` or `delete,create` Resized when a cost property changed, `no-op` Unchanged); sizing comes from `change.after` (Removed: `change.before`); a cost property listed in `change.after_unknown` is known only at apply, so that line is not determinable.
- **HCL otherwise.** Identity is the resource address (`aws_db_instance.ledger`, `module.db.aws_db_instance.this[0]`); a `moved {}` block is a rename, not Removed plus Added. Variables resolve lowest to highest: `variable` default → `terraform.tfvars` → `*.auto.tfvars` → `-var`/`-var-file` on the deploy command → `TF_VAR_*` in the workflow. An absent attribute takes the provider default (for example `aws_db_instance` without `multi_az` is single-AZ).
- Verification testing may run `terraform init && terraform plan` only if its sandbox has the Terraform CLI, provider downloads and backend credentials; don't assume it does.

### Step 2: First check — compare the before and after templates in the repo

The "before" is the template on the PR's base branch; the "after" is the template on the PR branch. Match resources by logical ID (Terraform: resource address) and put each one in exactly one class:
- **Added:** in the after template, not in the before. Cost goes **up** by its monthly cost.
- **Removed:** in the before template, not in the after. Cost goes **down** by its monthly cost.
- **Resized:** same logical ID, and a cost-relevant property changed: instance type/class, engine, Multi-AZ, storage type/size, provisioned IOPS/throughput, node/replica/shard count, desired capacity. Cost changes by **after minus before**.
- **Unchanged for cost:** same logical ID, only non-cost properties changed (tags, policies, descriptions). Not priced; give the count only.

Rules for edge cases (all formats):
- **Whole files:** if the template file itself is new, every resource in it is Added. If the file is deleted, every resource in it is Removed.
- **Resolve every value to a literal.** Follow parameters, variables, locals and module inputs until you reach a literal in the repo or the deploy workflow, on both sides; label the line default-derived when that literal is a default. If the chain reaches a data source, a runtime input, or an expression you can't evaluate with certainty, mark the line not determinable and name the unresolved reference. Never guess.
- **Conditional creation** (`Condition`, `count = var.x ? 1 : 0`, conditional `for_each`): evaluate with the resolved values on both sides. False→true is Added, true→false is Removed. Exclude resources not created at the assumed values and call out any that depend on a non-default input.
- **Quantity is the product of every multiplier on the resource:** instance or task counts, per-task compute and memory, redundancy across zones, the number of subnets or zones, and storage attached per instance.
- **Undeclared billable sub-resources:** some charges come from what a resource implies rather than from a resource the template declares, such as a public address assigned to a resource or to its subnets, resources a transform or construct expands into, and per-zone or per-subnet charges. Derive their count from the declared properties.
- **Omitted cost property:** the provider default applies; label the line "default".
- **Removal is a saving only if the resource is destroyed:** `DeletionPolicy: Retain`/`Snapshot` and `lifecycle { prevent_destroy }` keep it; a snapshot adds storage cost. Deleting a template or moving resources to another IaC tool doesn't destroy anything by itself: unless the change also deletes the old stack, count the new resources as Added and nothing as Removed.
- **Containers that declare no resources** (`AWS::CloudFormation::Stack`, `AWS::Serverless::Application`, Terraform `module`): expand them if the source is in the repo. Otherwise price from inputs that map plainly to one billable resource (`instance_class`, `node_type`, …), labelled module-input-derived, or list the container as not determinable.

The result of this step is the **repo-based estimate**: + Added, − Removed, ± Resized, and the net.

### Step 3: Second check — compare against live topology, only if the repo comparison isn't enough

The repo-based estimate from Step 2 is the default answer. Run this check only if at least one of these is true, and record which one:
- **No usable base version:** the base-branch template couldn't be fetched through the repository tools either (missing branch, API error, truncated diff), not just because the local copy has no git history.
- **New, renamed or moved template with a known stack name:** the repo names the stack it deploys to (deploy workflow, `samconfig.toml`, CDK stack ID), and the base branch has no matching template, so that stack may already exist.
- **Explicit physical names on Added resources** (`RoleName`, `BucketName`, `DBInstanceIdentifier`, `Name`, …): the repo can't tell whether that name is already taken in the account.
- **Conflicting signals:** the template, PR description or commit messages say the change modifies resources the base branch doesn't contain (for example "moves the table to provisioned capacity").
- **The user asks** to compare with the live account.

If none applies, skip this step, report "topology check not needed" with the reason, and use the repo-based estimate as the final result. When the check does run, it uses read-only calls only. Apply this matching discipline in order:
- **Logical-ID matching ONLY works if the template is deployed as a tracked stack.** Logical IDs live in CloudFormation stack metadata, not on raw resources. First check for a deployed stack (`cloudformation describe_stacks`/`list_stacks` → `describe_stack_resources`); if present, map logical ID → physical ID from the stack and compare.
- **If no stack is deployed, match by the template's EXPLICIT physical name/tags.** Pull the declared name and Tags, and look the resource up by that exact name (e.g. `iam get_role`, `rds describe_db_instances`).
- **Use exact-name equality — never prefix/substring/fuzzy matching.** Accounts often contain suffix-siblings from other provisioning paths (e.g. an SDK that appends `-<suffix>`). Treating `Foo-abc123` as a match for a declared `Foo` would wrongly classify a genuinely-new resource as already-deployed and drop it from the estimate. Require the physical name (ideally plus a managing tag) to match exactly.
- **If the name is auto-generated AND no stack is deployed, there is nothing to match against.** Say so explicitly and keep the Step 2 classification, but flag this as an assumption, not a confirmed topology match.
- **Terraform has no stack.** Match in this order: (1) state, from a committed `.tfstate` or the plan JSON's `prior_state`, address → physical ID; (2) the explicit `name`, `identifier`, `bucket` or `function_name` attribute plus `tags`, exact match, with the provider's `default_tags` as the managing tag; (3) auto-generated name: nothing to match, keep the Step 2 class and flag it as assumed.

Apply the outcomes to the repo-based estimate:
- **Added, not found:** confirmed new; keep it in the cost increase.
- **Added, found (exact match):** already deployed; move it out of the total and list it separately. If it was found by name outside any stack, also warn that a CloudFormation create will fail on an existing name unless the resource is imported.
- **Removed, found:** confirmed; keep it in the cost decrease.
- **Removed, not found:** it was never deployed or is already gone; move it out of the savings and list it separately.
- **Resized, stack deployed:** if the deployed property value (from describing the physical resource) differs from the repo's before value, use the deployed value as "before" and say so.
- **Check needed but account context unavailable:** keep the repo-based estimate unchanged and say explicitly that the second check was skipped, why it was needed, and the error.

The result of this step is the **topology-confirmed estimate**.

### Step 4: Extract sizing inputs from the templates

For Added resources, read the after template; for Removed resources, read the before template; for Resized resources, read both. Pull whatever sizing properties are declared: instance class/type, allocated storage, provisioned IOPS/throughput, memory/CPU, replica count. These drive the pricing query. Resolve `!Ref`/`!Sub`/`!If`, `var.` and `local.` references with the Step 2 rule.

**Region:** take the first literal found in this order: a resource-level provider alias (`provider = aws.<alias>`), the `provider "aws"` block, a template parameter, the deploy workflow environment (`AWS_REGION`/`AWS_DEFAULT_REGION`), `samconfig.toml`, the backend config. If none, ask. For StackSets or multi-Region templates, price each Region separately, or mark the lines not determinable if the Region list is a runtime input.

### Step 5: Get live prices — the only source of dollar figures

For every price line (Added, Removed, and both sides of Resized), use three live sources in this order, and record which one produced each rate:
1. The AWS Price List API, through whatever AWS tool the runtime has (5a). It returns exact, current, machine-readable rates with SKUs.
2. The public Price List offer files, downloaded over HTTPS with no AWS credentials, when 5a can't run (5b). Same data, same precision.
3. Public AWS pricing documentation, through `verify_aws_claim`, only for lines 5a and 5b couldn't price (5c). Pricing pages can be rounded and lag the Price List, so this is the last resort, not the first.

**5a. AWS Price List API (first choice).**

*Probe access once, before pricing the first line (mandatory).* Read the **5a** section of [references/pricing-sources.md](references/pricing-sources.md) before this step; it has the probe call, the AWS tool names it may go through, and the three Price List endpoints to try in order. Use the first endpoint that succeeds for every pricing call in this run.
- If all three endpoints fail, record the **exact error message and code** from each attempt. Then price every line with 5b. A missing AWS tool, an HTTP 500 from the credential endpoint, or "credentials could not be loaded" all mean 5a can't run, but none of them blocks 5b.
- **Never write "pricing unavailable" unless this probe, 5b, and 5c were all actually attempted and failed.** The output must quote each error.

*Attempted means a real call was made.* A source counts as attempted only if you called it and recorded its error. If this phase has no shell, HTTP, or AWS tool, write `not attempted in this phase: <missing tool>` for that source. Do not describe the environment as unreachable, and do not propose a network or IAM fix for a source you never called. In a Release Readiness Review, verification testing may price the change in an "IaC cost impact" test. If that result already exists in your context, build the dashboard from it and cite the test as the source. If not, use the ⏭️ banner from [assets/output-template.md](assets/output-template.md), not the ⛔ one.

*Price each line.* Call `get_products` with the service code and filters that match the resource's declared attributes and its real Region, then apply the rate to the declared quantity. The **5a** section of [references/pricing-sources.md](references/pricing-sources.md) has the filter and attribute-lookup guidance, the JSON path to the rate, and the SKU selection, unit normalization and free-tier rules; read it before the first call and apply it to every result. Those rules also apply to 5b.

**5b. Public Price List offer files (no AWS credentials needed).** Use this when 5a can't run, and for any line 5a left unpriced. These are the same official on-demand prices, downloaded over HTTPS from the shell. Read the **5b** section of [references/pricing-sources.md](references/pricing-sources.md) when you reach this step; it has the URL pattern, the fetch and streaming rules, the CSV column names, the service codes, and what to record in the Pricing trace. Apply the same SKU selection, free-tier, and unit rules as 5a.

**5c. Last resort: public AWS pricing documentation.** Only for lines still unpriced after 5a and 5b, and only if a `verify_aws_claim` tool exists in this runtime. Read the **5c** section of [references/pricing-sources.md](references/pricing-sources.md) first; it has the request phrasing and the acceptance checks. Ask for the rate without stating any price, and accept the result only if it passes every check; otherwise the line is not determinable.

### Step 6: Flag usage-based and not-determinable cost separately

Call out resources whose cost is dominated by runtime usage (Lambda invocations, S3 requests, data transfer, NAT Gateway data processing, DynamoDB on-demand) as "usage-dependent — no fixed monthly figure available, cost scales with volume" rather than assigning them any baseline number. For resources that have BOTH a fixed and a usage component (e.g. a NAT Gateway: fixed hourly + per-GB data processing), price the fixed part (×730) and flag the usage part separately.

If none of the three sources returns a usable rate for a fixed-price line, retry 5a once with `get_attribute_values` to find the exact filter value. If it's still unresolved, mark the line *not determinable* and give the reason from each source; never substitute a remembered or estimated number.

### Step 7: Validate and present the results

**One dashboard per diff.** Before writing, check whether this review already contains an IaC cost dashboard for the same diff. If it is priced, don't produce another; reference it. If it is unpriced and yours is priced, produce yours and state that it supersedes the earlier one.

**The cost dashboard below is the only accepted output format.** It is mandatory on every entry path, and it applies whether or not any price could be fetched. You MUST produce exactly this structure: the same nine sections, in the same order, with the same headings and the same table columns. Do not replace any table with prose or bullet points, do not drop, rename or reorder columns, and do not summarize the cost in a sentence or in a short "Metric / Value" table outside this dashboard. In a Release Readiness Review, add the dashboard as its own section of the review output; do not merge it into the risk findings.

Read [assets/output-template.md](assets/output-template.md) before writing the output. It holds the full template with every Summary row, the formatting rules (one row per price line, money format, traceability, Total rows, empty sections), and the rules for the ⛔ and ⏭️ banners. If you can't open it, still produce all nine sections, in this order, with the same headings and columns the asset defines: the `## 💰 IaC cost impact · <owner/repo> · <PR #number or branch> (<base branch> → <head commit>)` heading with the ⛔ or ⏭️ banner when it applies, then 📊 Summary, ➕ Added resources, ➖ Removed resources, 🔁 Resized resources, 🔎 Topology adjustments (second check), 🧾 Pricing trace, 📈 Usage-dependent (not in total), ❔ Not determinable / conditional (not in total), ⚠️ Caveats. Every money table ends with a bold **Total** row; keep every heading when a section is empty and write `_None._` under it.

**Arithmetic check before output:**
- Each table total equals the sum of its rows.
- Repo-based net = Added total + Removed total + Resized total.
- Net change = repo-based net + total topology adjustment.
- Every number in the Summary equals the matching table total.

If any check fails, fix it before presenting.

## Important Caveats to Always Include
- Every dollar figure in the output must be traceable to a specific live lookup made during this run: a `get_products` call, a row read from an AWS Price List offer file downloaded in this run, or a `verify_aws_claim` result with its AWS source URL. Never use a number recalled from training data or a static table.
- Rates taken from AWS pricing pages can be rounded or update later than the Price List API; the Summary's Price source row shows how many lines came from each source.
- The repo-based estimate assumes the base branch matches what is deployed; the topology check runs only when the repo comparison isn't enough, and corrects this only where it can find the resource.
- Conditional/parameterized template resources that only resolve at deploy time may be missed or misclassified.
- Always state which region's pricing the estimate assumes and where it came from (Step 4 order).
- Never present the estimate as a guaranteed bill impact. Use language like "roughly", "estimated", "ballpark", even when sourced from live pricing, because discounts and usage variability aren't captured.
