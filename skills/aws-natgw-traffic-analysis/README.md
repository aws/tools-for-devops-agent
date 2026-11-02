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

To deploy this skill to your Agent Space, use any of these:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, import this skill directly from the repository. In the DevOps Agent web app, go to Settings -> Add Skill -> Import from repository, then point to the `skills/aws-natgw-traffic-analysis` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

**Option B: Upload as a zip file**

1. Zip the `aws-natgw-traffic-analysis/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-natgw-traffic-analysis.zip aws-natgw-traffic-analysis/ -i '*.md' '*.json' '*.yaml' '*.yml' -x '*/README.md' '*/.skilleval.yaml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** -> **Upload skill**.
4. Drag and drop the `aws-natgw-traffic-analysis.zip` file (max 6 MB).
5. Select the agent type: **Chat tasks**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage the skill programmatically. Assign it to the `CHAT` agent type. See [Managing assets](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html) for the API workflow.

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
