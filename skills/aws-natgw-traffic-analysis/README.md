# aws-natgw-traffic-analysis skill

An AWS NAT Gateway traffic analysis skill. It traces NAT Gateway traffic to its actual destination, explains why it takes that path, surfaces network architecture issues (endpoints that exist but aren't used, internal services talking over public IPs, unintended cross-region data paths), and identifies which portion of the traffic — and cost — is addressable. Flags risky fixes before they're recommended. Provides **read-only** analysis, categorization, and read-only validation commands grounded in VPC Flow Log data, read-only API calls, and public AWS documentation.

## What it does

* Categorizes NAT Gateway destination traffic into AWS Service, customer-owned public IP, RFC1918-initiated, and third-party/CDN buckets, with a verified (not just tag-trusted) AWS Service attribution — and labels AWS traffic it cannot attribute to a specific service as such, instead of guessing.
* Verifies Gateway Endpoint (S3/DynamoDB) existence, route table coverage, and — critically — whether apparent "missing coverage" is actually cross-region traffic a same-region endpoint cannot intercept.
* Checks Interface Endpoint coverage for other AWS service traffic: identifies which APIs cross NAT from CloudTrail, then whether existing endpoints are actually used (private DNS, VPC DNS attributes, AZ coverage), including the ECR image-pull pattern.
* Gates any Cross-Region S3 Interface Endpoint recommendation on a CopyObject/UploadPartCopy activity check, since enabling one without checking can break cross-region copies VPC-wide.
* Traces customer-owned public IPs (including BYOIP) back through ASN ownership, EIP/ENI mapping, peering status, and route table coverage to find traffic that should be on a private path.
* Flags non-addressable traffic (CDN, legitimate internet egress) so it isn't chased as a false "optimization opportunity."

## Prerequisites

* No write permissions required — the skill is read-only.
* VPC Flow Logs that capture the **NAT Gateway ENI specifically** (not instance ENIs — see SKILL.md Hard Rule 5 for why this distinction matters). Flow logs on the NAT Gateway ENI, its subnet, or its VPC all work; the skill finds them with `describe-flow-logs` and filters every query to the NAT Gateway ENI.
* Where the flow logs are delivered decides how the skill reads them:
  * **CloudWatch Logs** — read with CloudWatch Logs Insights. Works with read-only logging permissions.
  * **Amazon S3** — needs an existing Athena table over the flow-log bucket, plus permissions that are not in the default agent policy (`s3:GetObject`/`s3:ListBucket` on the bucket, `kms:Decrypt` for customer managed keys, or `athena:StartQueryExecution` with a workgroup that uses managed query results). Without them, the skill asks you for a per-destination summary.
  * **No flow logs** — the skill says so, recommends enabling them, and reports only what CloudWatch metrics and configuration checks can show.
* `ce:GetCostAndUsage` on the account being analyzed — the CopyObject/UploadPartCopy check that runs before any Cross-Region S3 Interface Endpoint recommendation calls `aws ce get-cost-and-usage` (see `references/endpoint-coverage-and-cross-region.md`, Step 3).
* To run the suggested validation commands, read-only access to the relevant networking and logging APIs (e.g., `ec2:Describe*`, managed prefix-list reads, CloudTrail lookups).

## Uploading to AWS DevOps Agent

Set up the flow logs and permissions in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until they're in place. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand traffic and cost analysis and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-natgw-traffic-analysis`, or filter by AWS service **Amazon VPC**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change how destinations are categorized in `references/traffic-categorization.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-natgw-traffic-analysis/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-natgw-traffic-analysis.zip
   zip -r aws-natgw-traffic-analysis.zip aws-natgw-traffic-analysis/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-natgw-traffic-analysis.zip | tail -1   # expect 7 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-natgw-traffic-analysis.zip
   └── aws-natgw-traffic-analysis/
       ├── SKILL.md                      # required: frontmatter with name and description
       └── references/
           ├── flow-log-location.md
           ├── traffic-categorization.md
           ├── endpoint-coverage-and-cross-region.md
           ├── interface-endpoints.md
           ├── customer-ip-tracing.md
           └── output-and-limitations.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-natgw-traffic-analysis.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to use it

Ask NAT Gateway traffic or cost questions in natural language, for example:

* "Why is our NAT Gateway bill so high this month?"
* "What's actually going through our NAT Gateway?"
* "We have an S3 Gateway Endpoint but still see S3 traffic on NAT — why?"
* "Our EKS cluster is in private subnets — which AWS API traffic should be on Interface Endpoints?"
* "Is it safe to add a cross-region S3 endpoint to cut this NAT traffic?"
* "This IP hitting our NAT Gateway looks like it's ours — can we route it privately?"

The skill will categorize the traffic, apply the coverage and cross-region logic, cite the relevant reasoning and hard rules, and suggest read-only commands to validate each finding.

## Structure

```
aws-natgw-traffic-analysis/
├── SKILL.md            # Activation metadata + instructions
├── references/         # Detailed procedures, patterns, and caveats
├── README.md           # This file
├── CHANGELOG.md        # Version history
└── evals/              # Functional and trigger tests
```

## Maintainers

- [abitnar1](https://github.com/abitnar1)

## Disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate all findings in a non-production environment first, and confirm the flow log data source (NAT Gateway ENI vs. instance ENI) before trusting any categorization. Recommendations are based on public AWS documentation and field-verified patterns and may change as AWS services evolve.
