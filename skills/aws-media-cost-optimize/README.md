# Media Services Cost Optimization: AWS DevOps Agent Skill

Cost analysis and savings recommendations for AWS Elemental Media Services pipelines: MediaConnect (flows, Router, reserved outbound bandwidth), MediaLive (input and output rates, reservations, channel class, stop scheduling, input specification right-sizing), MediaPackage v1/v2, MediaTailor (ad insertion, Channel Assembly, log sampling), and CloudFront delivery economics. Rates come from live AWS Price List data; usage is modeled from CloudWatch metrics; every recommendation is gated, carries a confidence level, and names the operator action it would become without executing it.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat). Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "We run six MediaLive channels around the clock. Where are we overspending and would reservations pay off?"

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaCostOptimize` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

`pricing:DescribeServices` and `pricing:GetProducts` are the free Price List Query API; there is no per-request charge. Nothing under `ce:*` is granted (Cost Explorer bills per request and cannot be disabled once enabled), and no purchase, update, stop or delete actions are granted. The skill maps its recommendations to those operator actions but never performs them.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaCostOptimizeReadOnly",
      "Effect": "Allow",
      "Action": [
        "pricing:DescribeServices",
        "pricing:GetProducts",
        "medialive:ListChannels",
        "medialive:DescribeChannel",
        "medialive:ListInputs",
        "medialive:DescribeInput",
        "medialive:ListReservations",
        "medialive:DescribeReservation",
        "medialive:ListOfferings",
        "medialive:DescribeOffering",
        "mediaconnect:ListFlows",
        "mediaconnect:DescribeFlow",
        "mediaconnect:ListEntitlements",
        "mediaconnect:ListReservations",
        "mediaconnect:DescribeReservation",
        "mediaconnect:ListOfferings",
        "mediaconnect:DescribeOffering",
        "mediaconnect:ListRouterInputs",
        "mediaconnect:ListRouterOutputs",
        "mediaconnect:GetRouterInput",
        "mediaconnect:GetRouterOutput",
        "mediapackage:ListChannels",
        "mediapackage:DescribeChannel",
        "mediapackage:ListOriginEndpoints",
        "mediapackage:DescribeOriginEndpoint",
        "mediapackagev2:ListChannelGroups",
        "mediapackagev2:ListChannels",
        "mediapackagev2:GetChannel",
        "mediapackagev2:ListOriginEndpoints",
        "mediapackagev2:GetOriginEndpoint",
        "mediatailor:ListPlaybackConfigurations",
        "mediatailor:GetPlaybackConfiguration",
        "mediatailor:ListChannels",
        "mediatailor:DescribeChannel",
        "cloudfront:ListDistributions",
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:GetCachePolicy",
        "cloudfront:ListCachePolicies",
        "cloudfront:GetMonitoringSubscription"
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

- `references/pricing-data-acquisition.md`
- `references/configuration-cost-map.md`
- `references/data-transfer-map.md`
- `references/medialive-cost-levers.md`
- `references/mediaconnect-cost-levers.md`
- `references/mediapackage-cost-levers.md`
- `references/mediatailor-cost-levers.md`
- `references/cloudfront-cost-levers.md`

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent answers a cost question from remembered list prices and a resource count. This skill refuses to quote a rate it has not fetched and validated, knows which configuration fields select a billing tier (MediaLive `InputSpecification`, H.264 `FramerateControl`, MediaConnect protocol family, Router tier, CloudFront cache behavior split), knows which plausible levers are not levers (MediaConnect `MaxBitrate` on TS flows, MediaPackage startover window, DRM), models usage from metric presence with the estimation method stated, applies break-even gates before recommending any commitment, and keeps Cost Explorer out of the loop so the review itself costs the customer nothing.
