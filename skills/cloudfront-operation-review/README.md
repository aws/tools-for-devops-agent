# CloudFront Operational Review — AWS DevOps Agent Skill

A read-only Amazon CloudFront operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). It assesses distributions against the [Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html), and produces a shareable report artifact.

## Purpose

CloudFront distributions collect configuration drift over time: content still reachable over plaintext HTTP, legacy origin access identities, S3 origins left public, certificates close to expiry, no WAF in front of dynamic traffic, logging off, and legacy cache settings that lower the hit rate. This skill gives DevOps Agent a structured, read-only method to find those gaps on every distribution.

It works in two passes. Account-level reads score and rank every distribution. The calls that cost one request per distribution (metrics, WAF, ACM, policy detail) then run only on the worst-ranked set, so the budget goes where a finding may still change. Findings are scoped by origin type, so the report never recommends origin access control for an origin that cannot use it.

## Key Capabilities

- Discovers every distribution and the account's shared edge resources: origin access controls and identities, cache, origin request and response headers policies, real-time log configurations, continuous deployment policies, key groups, and functions
- Classifies every origin (S3, S3 website endpoint, Multi-Region Access Point, Lambda function URL, media, VPC origin, custom) before evaluating origin-access findings
- Checks viewer and origin protocol policies, origin TLS protocols, viewer security policy, ACM certificate validity and alias coverage, WAF association, OAC/OAI posture, signed-URL signer type, and security response headers
- Reads 7 days of `AWS/CloudFront` metrics with the required `Region=Global` dimension. Opt-in metrics (cache hit rate, origin latency) are detected first and never misread as zero
- Detects standard logging (v2) through CloudWatch Logs deliveries, as well as legacy logging
- Uses a three-state verdict (Pass / Inspect / Fail). Settings whose correctness depends on the application, such as origin timeouts and geo restriction, are reported as Inspect, never as Pass
- Covers five pillars: **Security, Reliability, Performance Efficiency, Operational Excellence, Cost Optimization**, with a readiness score that LOW findings do not reduce

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions

Every API the skill calls is covered by the `AIDevOpsAgentAccessPolicy` managed policy (verified against policy version v11). No additional IAM is needed:

- `cloudfront:List*`, `cloudfront:Get*` (`GetDistributionConfig`, `GetMonitoringSubscription`, `GetCachePolicy`, `GetOriginRequestPolicy`, `GetResponseHeadersPolicy`, `GetRealtimeLogConfig`), `cloudfront:DescribeFunction`, `cloudfront:ListTagsForResource`
- `wafv2:GetWebACL`
- `acm:DescribeCertificate`
- `cloudwatch:GetMetricData`, `cloudwatch:DescribeAlarms`
- `logs:DescribeDeliverySources`, `logs:DescribeDeliveries`
- `ce:GetCostAndUsage` (optional; cost findings degrade without it)

The skill is read-only. It never calls `Create*`, `Update*`, or `Delete*` APIs, creates no invalidations, and reads no edge function code.

## Limitations

- **Additional metrics are opt-in and billed.** Cache hit rate, origin latency, and per-status-code error rates exist only for distributions with additional metrics turned on. Without them, those checks are reported as not evaluated.
- **Origin lockdown is not verified.** The skill does not read origin security groups or S3 bucket policies. Origin-restriction findings for custom origins are Inspect items.
- **WAF rules are not evaluated.** The skill reads the web ACL only to answer whether a distribution is protected, and by which rule types.
- **Deferred for v1:** Lambda@Edge concurrency headroom (`lambda:GetAccountSettings` and `lambda:GetFunctionConcurrency` are not in the standard policy), DNS alias-versus-CNAME checks, S3 bucket policy verification for OAC origins, and per-tenant settings on multi-tenant distributions.
- **Cost Explorer** can be empty or denied from a linked account. Configuration-driven cost findings still run.
- **Sustainability is not assessed.** No API provides a CloudFront carbon figure, so the pillar is omitted rather than estimated.

## Agent Types

- **Chat tasks** (`CHAT`): conversational invocation ("review my CloudFront distributions"). This is the agent type the skill is evaluated against.

Select **Generic** if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

```bash
cd skills/cloudfront-operation-review
zip -r ../cloudfront-operation-review.zip . \
  -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

The archive contains:

```
SKILL.md
references/
├── best-practices-checklist.md
├── metrics-thresholds.md
├── origin-classification.md
└── severity-and-scoring.md
assets/
└── report-template.md
```

Confirm with `unzip -l ../cloudfront-operation-review.zip` that `SKILL.md` is at the root, with no leading directory. The total zip size must be 6 MB or less, and `scripts/` directories are rejected.

### 2. Upload via the Operator Web App

1. Open the **Skills** page in your Agent Space Operator Web App.
2. Choose **Add skill** → **Upload skill**.
3. Select `cloudfront-operation-review.zip`.
4. Select agent type **Chat tasks**, or leave **Generic**.
5. Review the validation results and choose **Upload**.

## How to Use This Skill

In DevOps Agent Chat:

- *"Run a CloudFront operational review for this account."*
- *"Review distribution `E1A2B3C4D5E6F7` for best practices."*
- *"Which of my CloudFront distributions still allow HTTP or use old TLS?"*
- *"Audit CloudFront WAF and origin access posture."*
- *"Do a health check on our CDN."*

The agent collects all data automatically, uses only read-only AWS APIs, and writes a report artifact named `cloudfront-review-<distribution-or-account>-<YYYY-MM-DD>.md` to the **Artifacts** page.

## Skill Contents

```
cloudfront-operation-review/
├── SKILL.md                           # skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md                       # version history
├── .skilleval.yaml                    # skill-eval audit config
├── references/
│   ├── best-practices-checklist.md    # every check: P1/P2, pass condition, severity, source
│   ├── metrics-thresholds.md          # AWS/CloudFront metrics, statistics, bands
│   ├── origin-classification.md       # origin class, OAC eligibility, static/dynamic profile
│   └── severity-and-scoring.md        # severity definitions, readiness score formula
├── assets/
│   └── report-template.md             # report structure loaded in Step 6
└── evals/                             # evaluation data (not in the upload zip)
    ├── evals.json
    └── eval_queries.json
```

## Pillars Covered

| Pillar | Checks | Reference |
|---|---|---|
| Security | Viewer and origin protocol, origin TLS, viewer security policy, certificate validity and coverage, WAF, OAC/OAI, public S3 origins, custom-origin lockdown, signed-URL signers, security headers, geo restriction | [Security in CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/security.html) |
| Reliability | Origin failover and criteria, origin timeouts (Inspect), custom error responses, 5xx and 4xx rates, continuous deployment | [Origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html) |
| Performance Efficiency | Cache hit rate, legacy cache settings, compression, origin latency, HTTP version, Origin Shield | [Cache key](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/controlling-the-cache-key.html) |
| Operational Excellence | Access logging (v2 and legacy), alarms, tags, additional metrics, comments | [Standard logging](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/standard-logging.html) |
| Cost Optimization | Dedicated-IP SSL, disabled distributions, real-time log sampling, price class, compression savings, spend breakdown | [CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/) |

## Related

- [AWS DevOps Agent skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate it in a non-production environment first. Distribution changes propagate to every edge location. Test configuration changes on a staging distribution (continuous deployment) or in a non-production account before applying them to production.
