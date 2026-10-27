# CloudFront Investigation for Media Delivery: AWS DevOps Agent Skill

Investigation of the Amazon CloudFront distribution delivering an AWS Elemental Media Services pipeline (MediaPackage v1 or v2 origin) to viewers. Locates the distribution, verifies origin binding and protocol, reads `AWS/CloudFront` metrics in us-east-1 as percentages, attributes every elevated error rate as CDN-side or origin-surfaced by reconciling against MediaPackage egress metrics, inspects cache behaviors and cache-key hygiene for the manifest-vs-segment split, reads Origin Shield placement, and analyzes access logs when standard logging (v2) delivers to CloudWatch Logs. Emits explicit DATA GAPs for anything opt-in and unconfigured instead of false all-clears.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat) and Incident RCA investigations. Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "Viewers are buffering on our live stream but MediaPackage looks healthy."

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaCloudFrontInvestigate` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

CloudFront IAM actions are global. The CloudWatch metric reads target us-east-1, where `AWS/CloudFront` publishes.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaCloudFrontInvestigate",
      "Effect": "Allow",
      "Action": [
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:ListDistributions",
        "cloudfront:GetCachePolicy",
        "cloudfront:ListCachePolicies",
        "cloudfront:GetOriginRequestPolicy",
        "cloudfront:ListOriginRequestPolicies",
        "logs:DescribeDeliverySources",
        "logs:DescribeDeliveries",
        "logs:DescribeDeliveryDestinations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SharedObservabilityReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:ListMetrics",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "logs:StartQuery",
        "logs:GetQueryResults",
        "logs:StopQuery"
      ],
      "Resource": "*"
    }
  ]
}
```

## Reference Files

- `references/cache-behavior-patterns.md`
- `references/access-log-fields.md`
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent asked "viewers are buffering" reads the CloudFront error rates as counts, queries them in the wrong region, and blames the CDN for whatever appears at the edge. This skill enforces the two CloudFront interpretation traps (us-east-1-only namespace, percentage rates), reconciles every elevated rate against MediaPackage egress before attributing it, knows the manifest-fresh/segment-long caching rule that produces stalls with no error signal, recognizes the MediaPackage v2 HTTPS/SNI 502 signature, and treats absent additional metrics and unconfigured logs as DATA GAPs rather than healthy zeros. Boundaries: origin-side ingest/egress errors, CDN authorization, and ForceEndpointError belong to aws-mediapackage-investigate; ad insertion belongs to aws-mediatailor-investigate.
