# AWS WAF Log Analysis Skill

This skill enables the AWS DevOps Agent to find out whether AWS WAF is denying legitimate traffic, and to hunt WAF logs for malicious or abusive traffic, including what WAF detected but did not block.

## Purpose

When users, partners, scripts, or mobile apps are denied access to an application behind AWS WAF, the first question is whether WAF is involved and, if so, which rule and why. This skill discovers the Web ACL and its log destination, queries WAF logs, and returns an evidence-backed verdict (false positive, client that can't solve a challenge, correct mitigation, or WAF cleared) with advisory, narrowly scoped fixes. It also supports proactive threat hunting over the same logs. It is read-only and advisory: it never changes a Web ACL, rule, IP set, Shield setting, or logging configuration.

## Key Capabilities

- Rule out AWS WAF quickly for outages and error spikes on CloudFront, Application Load Balancer, and API Gateway
- Attribute Block, Challenge, CAPTCHA, Anti-DDoS, and Shield Advanced automatic mitigation actions to the Web ACL, rule, managed sub-rule, and response code
- Classify each denying rule as false positive, client can't solve the challenge, correct mitigation, or mixed, with confidence and quantified impact
- Hunt for scanners, injection attempts, bots, volumetric abuse, and card-testing patterns, and separate known automation from attacks
- Surface detected-not-blocked findings, such as threat labels on allowed requests and rate-based rules in Count mode
- Query WAF logs with CloudWatch Logs Insights or Amazon Athena, and fall back to WAF metrics and sampled requests when logs can't be queried
- Recommend the narrowest fix first, with a validate-in-Count-mode step

## Prerequisites

- The default `AIDevOpsAgentAccessPolicy`, which covers CloudWatch Logs Insights, AWS WAF, Amazon CloudFront, Elastic Load Balancing, and AWS Shield read access, CloudWatch metrics, CloudTrail `LookupEvents`, and AWS Glue reads.
- Additional permissions for WAF logs in Amazon S3, added to the IAM role of your Agent Space with the policy in [Adding the additional permissions](#adding-the-additional-permissions):
  - `athena:StartQueryExecution`, `athena:GetQueryExecution`, `athena:GetQueryResults`, `athena:StopQueryExecution`, and `athena:GetWorkGroup`, scoped to the Athena workgroup used, plus `athena:ListWorkGroups` (not resource-scoped) to find a workgroup with managed query results enabled. The skill polls `athena:GetQueryExecution` once per query ID, so `athena:BatchGetQueryExecution` is not needed
  - `s3:GetObject` on the WAF log objects and `s3:ListBucket` / `s3:GetBucketLocation` on the WAF log buckets (`aws-waf-logs-*` naming)
  - `kms:Decrypt` on the bucket key, only if the log bucket uses SSE-KMS
  - `wafv2:DescribeManagedRuleGroup`, which returns exact rule names and labels. It is recommended on every path, including CloudWatch Logs, even when you don't use Athena.
- For WAF logs in Amazon S3: an Athena workgroup with managed query results enabled. Otherwise the agent also needs write access to a query-results bucket, which the policy below doesn't grant.
- For WAF logs in Amazon S3: an Athena table over the log bucket. If none exists, the skill continues on the degraded path and includes an advisory `CREATE EXTERNAL TABLE` statement (with partition projection built from your log prefix) for you to review and run.
- For WAF logs in CloudWatch Logs: no extra permissions beyond the default policy. The log group name must start with `aws-waf-logs-`.

### Adding the additional permissions

Attach this policy to the IAM role of your Agent Space (shown in the Agent Space settings), for example as an inline policy. Replace `<ACCOUNT_ID>`, `<ATHENA_WORKGROUP>` (usually `primary`) and `<WAF_LOG_BUCKET>` (for example `aws-waf-logs-<ACCOUNT_ID>`, or `aws-waf-logs-*` for all WAF log buckets). Drop the `AthenaQuery`, `AthenaList`, `WafLogRead` and `WafLogList` statements if your WAF logs go only to CloudWatch Logs.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaQuery",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution",
        "athena:GetWorkGroup"
      ],
      "Resource": "arn:aws:athena:*:<ACCOUNT_ID>:workgroup/<ATHENA_WORKGROUP>"
    },
    {
      "Sid": "AthenaList",
      "Effect": "Allow",
      "Action": "athena:ListWorkGroups",
      "Resource": "*"
    },
    {
      "Sid": "WafLogRead",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<WAF_LOG_BUCKET>/*"
    },
    {
      "Sid": "WafLogList",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::<WAF_LOG_BUCKET>"
    },
    {
      "Sid": "ManagedRuleGroupLabels",
      "Effect": "Allow",
      "Action": "wafv2:DescribeManagedRuleGroup",
      "Resource": "*"
    }
  ]
}
```

If the log bucket uses SSE-KMS, add this statement with your key ARN:

```json
{
  "Sid": "WafLogKmsDecrypt",
  "Effect": "Allow",
  "Action": "kms:Decrypt",
  "Resource": "arn:aws:kms:<REGION>:<ACCOUNT_ID>:key/<KEY_ID>"
}
```

Glue Data Catalog reads (`glue:GetTable`, `glue:GetDatabase`, `glue:GetPartitions`) are already in `AIDevOpsAgentAccessPolicy`. The Athena workgroup must have managed query results enabled, because this policy grants no write access to a query-results bucket.

## Limitations

- CloudWatch Logs Insights can't expand the WAF `labels` array into one row per label. The skill works around this: it first finds the largest number of labels on any record, counts labels at each array position (`labels.0.name`, `labels.1.name`, and so on), and adds the counts per label, so label totals on the CloudWatch Logs path stay complete. Each position is one extra query over the window, so the skill keeps that window narrow.
- Rule and label meanings don't depend on web access. The skill reads them from `DescribeManagedRuleGroup` when permitted, then from the labels in the logs, then from dated tables bundled with the skill; a connected AWS documentation tool can confirm them but is never required. A label found in none of these is reported as "meaning unverified" rather than guessed.
- In AWS DevOps Agent, the main agent's AWS tool refuses CloudTrail calls, and long log analysis in the main agent can time out. The skill works within this: the main agent only does discovery, one log subagent runs all queries and returns compact aggregates, and a change subagent runs every CloudTrail lookup. Request payloads reach the answer only as class and count.
- When WAF logs can't be queried (no logging, no Athena table, or Athena not permitted), the investigation still continues. The skill attributes denials from WAF metrics and sampled requests, caps verdicts at "likely" confidence, records the gap, and gives the advisory fix: the logging configuration, an Athena table definition built from your log prefix, or the missing permission.
- Findings are AI-generated. Every verdict carries its evidence (counts, query IDs, CloudTrail events) so a human can verify it, and every fix is advisory, scoped narrowly and validated in Count mode first, so nothing changes until someone reviews and applies it.

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/aws-waf-log-analysis` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository — including this one — even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `aws-waf-log-analysis/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-waf-log-analysis.zip aws-waf-log-analysis/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `aws-waf-log-analysis.zip` file (max 6 MB).
5. Select the agent type: **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for CI/CD pipelines or automation workflows. Assign the skill to the `INCIDENT_RCA` agent type. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

Start an investigation in AWS DevOps Agent. No alarm is needed: you can start one from an alarm or incident, or by describing a symptom or a hunting question yourself. The skill works best with a symptom or a question, a resource, and a time window in UTC. The agent works in a single pass, so it applies documented defaults for anything you leave out and lists them in an Assumptions block.

The result is the investigation itself: symptoms, one Cause finding per denying rule or threat finding (with exact rule and sub-rule IDs), one Root Cause, supporting observations, and gaps. A threat hunt also writes a Markdown threat-hunt report artifact (findings table, detected-not-blocked, known automation, attacker residue, WAF-layer and application-layer mitigations, coverage and gaps) when the runtime supports artifacts; otherwise the same sections are in the investigation's final message.

### Access-denied triage

- "Investigate the CloudFront 4xx error rate alarm."
- "Since 17:30 UTC customers get errors submitting checkout on my CloudFront distribution. Find out whether AWS WAF is involved."
- "A partner integration calling our API Gateway stage gets 403 responses since this morning. Investigate whether AWS WAF is blocking it, and which rule."
- "Our mobile app gets 202 responses with an empty body from the ALB since yesterday's release. Investigate whether AWS WAF is involved."
- "The checkout API timed out for 10 minutes. Make sure AWS WAF isn't the cause."

### Threat hunting

- "Investigate the AWS WAF logs for the last 7 days: what looks malicious, including anything WAF detected but didn't block."
- "Investigate whether scanners or bots are hitting our public ALB, and what AWS WAF caught and missed."
- "Investigate which rate-based rules in our Web ACL are in Count mode and whether they would have fired on traffic from the last 24 hours."

## Disclaimer

This is sample code and is not intended for production use without additional review and testing. Validate the skill and its recommendations in a non-production environment first.
