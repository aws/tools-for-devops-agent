# IaC Change Cost Preview

See what a pull request will do to your AWS bill before you merge it.

This skill for AWS DevOps Agent reads the infrastructure-as-code change in a pull request, finds the resources it adds, removes, or resizes, and shows how much more (or less) the account will cost per month. Prices are looked up live on every run. The skill contains no price list of its own, so it never guesses or uses an outdated rate.

## Non-production disclaimer

⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate it in a non-production environment first.

## Purpose

A Release Readiness Review tells you whether a change is safe to deploy. It doesn't tell you that the same PR adds a Multi-AZ database, a NAT gateway, and doubles a worker fleet, for a few hundred dollars a month before a single request is served. This skill puts that number in the review, next to the risk findings, so the reviewer can ask "is this spend expected?" before approving.

## How the estimate is built

1. **Picks up the change.** It runs in Release Readiness Reviews that touch CloudFormation, SAM, CDK-synthesized, or Terraform templates. You can also ask for it in chat. If the PR touches no templates, it says there is nothing to price.

   For CDK, the skill prices the synthesized template (`cdk.out/*.template.json`), not the CDK source. If the PR has no synthesized template, a review can generate one with `cdk synth`; otherwise the skill reports the change as not priced rather than guessing.
2. **Compares the PR with the repo.** It compares the template on the base branch with the template on the PR branch and sorts every resource:
   - **Added:** the cost goes up.
   - **Removed:** the cost goes down.
   - **Resized** (instance type, storage, Multi-AZ, node count, desired capacity…): the cost changes by the difference.
   - **Unchanged for cost** (tags, policies, descriptions): counted, not priced.

   Every value is traced to a literal in the repo or the deploy workflow (parameter defaults, Terraform variables and tfvars, module inputs). Anything that only exists at deploy time, such as a data source or a runtime input, is reported as not determinable rather than guessed. For Terraform, a plan JSON attached to the PR gives exact values; without one the estimate is derived from the HCL. Recommended CI step: `terraform plan -out=plan.out && terraform show -json plan.out > plan.json`, attached to the PR.
3. **Checks the live account, only if the repo comparison isn't enough.** For a normal PR, the comparison in step 2 is the answer and this step is reported as "not needed". It runs, read-only, when:
   - the base version of the template can't be fetched;
   - the template is new, renamed or moved, and the repo names the stack it deploys to;
   - an added resource has an explicit name (`RoleName`, `BucketName`, …) that may already be taken;
   - the template or PR text describes changes to resources the base branch doesn't have;
   - or you ask for it.

   When it runs, an "added" resource that already exists isn't counted as new cost, and a "removed" resource that was never deployed isn't counted as a saving. It matches resources through the deployed CloudFormation stack, or by exact name.
4. **Looks up live prices,** trying three official AWS sources in order:
   1. The AWS Price List API: exact, current rates with SKUs.
   2. The public AWS Price List files, the same data.
   3. Public AWS pricing documentation, through `verify_aws_claim`.

   For each resource it picks the standard on-demand price (not reservation, Extended Support, or free-tier rows), converts units correctly, and multiplies by the size and count declared in the template.
5. **Shows a cost dashboard:** the net monthly change at the top, then tables for added, removed, and resized resources, what the account check changed, and where every price came from. Charges that depend on usage (requests, data transfer, GB processed) are listed without a dollar figure.

## Workflow

```mermaid
flowchart TD
    A["1 · PR touches IaC templates<br/>(Release Readiness Review or chat)"] --> B["2 · Compare base branch vs PR branch<br/>Added · Removed · Resized"]
    A -. no templates touched .-> X["Nothing to price"]
    B --> Q{"Is the repo comparison enough?"}
    Q -- yes --> D["4 · Look up live prices"]
    Q -- "no: missing base, new stack name,<br/>explicit names, conflicting signals" --> C["3 · Check the live account (read-only)<br/>Already deployed? Really deployed?"]
    C --> D
    D --> D1["AWS Price List API"]
    D1 -- no AWS tool / access --> D2["Public Price List files<br/>no credentials needed"]
    D2 -- line still unpriced --> D3["AWS pricing docs<br/>verify_aws_claim"]
    D1 --> E
    D2 --> E
    D3 --> E["5 · Cost dashboard<br/>Net change per month + breakdown"]
```

## Dashboard sections

Every run uses the same layout:

| Section | What it shows |
|---|---|
| 📊 Summary | Net monthly change, totals for added / removed / resized, the Region, and the price sources used |
| ➕ Added · ➖ Removed · 🔁 Resized | One row per price line: sizing, quantity, rate, monthly amount |
| 🔎 Topology adjustments | Whether the account check was needed, and if it ran, which resources it moved in or out of the total |
| 🧾 Pricing trace | For every rate: the filters sent, rate, unit, and monthly amount |
| 📈 Usage-dependent | Charges with no fixed monthly figure, and what drives them |
| ❔ Not determinable | Anything that couldn't be priced, with the exact reason |
| ⚠️ Caveats | List-price and baseline assumptions for this run |

If pricing can't be reached at all, a banner at the top quotes the exact error from each source and says what to fix. The resource tables are still filled in.

### Example

Abridged output for a PR that adds a database and a NAT gateway, removes a Redis cache, and doubles a worker fleet. The rates shown are illustrative only; the skill looks up current on-demand rates on every run.

```markdown
## 💰 IaC cost impact · acme/payments-infra · PR #14

### 📊 Summary
| Metric | Value |
|---|---|
| **Net monthly change** | **≈ +$258.43 / month** |
| Repo-based net (first check) | +$258.43 |
| Topology adjustment (second check) | $0.00 · not needed |
| ➕ Added | 4 resources · +$458.41 |
| ➖ Removed | 1 resource · −$334.34 |
| 🔁 Resized | 1 resource · +$134.36 |
| Pricing Region | eu-west-1 · from the deploy workflow |
| Baseline | `main` · topology check: not needed |
| Price source | Price List API: 0 lines · offer files: 8 lines · AWS pricing docs: 0 lines |

### ➕ Added resources
| # | Logical ID | Type | Sizing | Qty | Rate | Monthly |
|---|---|---|---|---:|---|---:|
| A1 | LedgerDb · instance | AWS::RDS::DBInstance | db.r6g.large · PostgreSQL · Multi-AZ | 1 | $0.504 / Hrs | +$367.92 |
| A1b | LedgerDb · storage | AWS::RDS::DBInstance | 200 GB gp3 · Multi-AZ | 1 | $0.254 / GB-Mo | +$50.80 |
| A2 | ReconcilerNatGateway · hours | AWS::EC2::NatGateway | 1 AZ | 1 | $0.048 / Hrs | +$35.04 |
| A3 | ReconcilerNatEip | AWS::EC2::EIP | public IPv4 | 1 | $0.005 / Hrs | +$3.65 |
| A4 | LedgerKey | AWS::KMS::Key | customer managed key | 1 | $1.00 / Keys | +$1.00 |
| | **Total added** | | | | | **+$458.41** |

### ➖ Removed resources
| # | Logical ID | Type | Sizing | Qty | Rate | Monthly |
|---|---|---|---|---:|---|---:|
| R1 | SessionCache | AWS::ElastiCache::ReplicationGroup | cache.r6g.large · Redis | 2 | $0.229 / Hrs | −$334.34 |
| | **Total removed** | | | | | **−$334.34** |

### 🔁 Resized resources
| # | Logical ID | Change (before → after) | Before | After | Delta |
|---|---|---|---:|---:|---:|
| Z1 | WorkerAsg · instances | DesiredCapacity 2 → 4 · m6g.large Linux | $125.56 | $251.12 | +$125.56 |
| Z1b | WorkerAsg · EBS | 50 GB gp3 per instance · 2 → 4 | $8.80 | $17.60 | +$8.80 |
| | **Total resized** | | | | **+$134.36** |

### 🔎 Topology adjustments (second check)
_Topology check not needed: the base and PR versions of the template were both available, and no added resource declares an explicit name. Net change equals the repo-based net._

### 📈 Usage-dependent (not in total)
| Logical ID | Billed on |
|---|---|
| ReconcilerNatGateway | GB of data processed |
| LedgerKey | API requests |
```

The real output also includes the full pricing trace, with the source and filters for each rate, the not-determinable table, and the caveats. Some columns are trimmed here to keep the example short.

### Pricing basis and discounts

Every rate comes from public AWS on-demand list prices. The estimate doesn't include Savings Plans, Reserved Instances, Enterprise Discount Program or private pricing terms, credits, or free tier, so your actual bill may be lower.

If you have discounts, add them yourself when you clone the skill: put a reference file such as `references/discounts.md` in the skill folder with your rates or percentage discounts per service, and link it from Step 5 of `SKILL.md` with an instruction to apply it after the list price is found. Keep the list-price line in the Pricing trace so reviewers can see both figures. Don't put confidential pricing in a public fork.

## Prerequisites

- **AWS DevOps Agent** with an Agent Space.
- **Release Readiness Review** on the repository, for the automatic path. Automatic reviews run only on private repositories, when "Auto trigger change review" is enabled for the Agent Space and the pull request matches the configured trigger filters; see [the Release Readiness Review documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/release-management-release-readiness-code-review.html). Otherwise, start the review manually or use the chat path.
- **A repository integration** (GitHub or GitLab), so the skill can read a PR's diff and files. No CI/CD pipeline is needed.
- **A pricing source.** The skill tries these in order:

  | Source | What it needs |
  |---|---|
  | AWS Price List API | An AWS tool in the agent with the permissions below |
  | Public Price List files | Outbound HTTPS to `pricing.us-east-1.amazonaws.com` |
  | AWS pricing docs | The `verify_aws_claim` tool available to the agent |

  The Price List API needs `pricing:GetProducts`, `pricing:GetAttributeValues` and `pricing:DescribeServices`, which the default `AIDevOpsAgentAccessPolicy` doesn't grant. Deploy this repository's [`cloudformation/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies.yaml) with the `EnableIacChangeCostPreview` parameter set to `true` (the default); it attaches the `DevOpsAgentSkill-IacChangeCostPreview` inline policy to the Agent Space role. This enables the Price List API in chat and in any agent that has an AWS tool. The report phase of a Release Readiness Review has no AWS tool, so its prices come from verification testing.

  Price List data is public and free to query. The API is called in `us-east-1`, with `eu-central-1` and `ap-south-1` as fallbacks, whatever Region your resources run in. If your AWS tool is restricted to certain Regions, allow one of these.

- **Optional, for the account check** (used only when the repo comparison isn't enough): read-only access to CloudFormation (`DescribeStacks`, `ListStacks`, `DescribeStackResources`) and to describe/get calls on the resource types in your templates. The default read-only managed policy covers this. Without it, the skill still produces the repo-based estimate and says the account check was skipped.

The skill performs no write actions. It never creates stacks, change sets, or any other resource.

## Usage

**In a Release Readiness Review:** once the review runs on a PR (automatically, under the conditions in Prerequisites, or started manually), the cost section appears whenever the PR touches a template.

**In chat:** name the repository, the PR or branch, and ideally the Region:

- "What does PR #14 in acme/payments-infra add or remove, and how much more will it cost per month? It deploys to eu-west-1."
- "Compare `cloudformation/payments-ledger.yaml` on `feature/ledger-rds-nat` against `main` and estimate the monthly change."
- "This repo has no pipeline. Fetch PR #12 yourself and tell me the net monthly cost change."

## Installation

**Option A: GitHub integration.** Fork or copy this repository and import the skill through the Agent Space GitHub integration.

**Option B: Direct upload.** Zip the skill and upload it as a user-defined skill in the Agent Space console.

## Files

```
iac-change-cost-preview/
├── SKILL.md                      # Workflow checklist, both checks, the pricing core, a dashboard skeleton, caveats
├── references/
│   └── pricing-sources.md        # Full procedure for each pricing source (read in Step 5)
├── assets/
│   └── output-template.md        # Full dashboard template and formatting rules (read in Step 7)
├── README.md                     # This file
└── CHANGELOG.md
```
