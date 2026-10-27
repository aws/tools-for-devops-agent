# MediaPackage Deep Investigation (v1 and v2): AWS DevOps Agent Skill

Deep investigation of AWS Elemental MediaPackage. Auto-detects v1 vs v2, then branches into version-specific diagnosis: ingest health (WebDAV credentials vs SigV4), egress error breakdown with the correct per-version dimensions, latency, CDN authorization, ForceEndpointError awareness, MQCS content quality, harvest jobs, stuck-endpoint reset assessment, and access log analysis via CloudWatch Logs Insights.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat) and Incident RCA investigations. Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "Players are getting 404s from our MediaPackage endpoint but ingest looks healthy."

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaPackageInvestigate` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaPackageInvestigate",
      "Effect": "Allow",
      "Action": [
        "mediapackage:DescribeChannel",
        "mediapackage:ListChannels",
        "mediapackage:ListHarvestJobs",
        "mediapackage:DescribeHarvestJob",
        "mediapackagev2:GetChannel",
        "mediapackagev2:ListChannelGroups",
        "mediapackagev2:ListChannels",
        "mediapackagev2:ListOriginEndpoints",
        "mediapackagev2:GetChannelPolicy",
        "mediapackagev2:GetOriginEndpoint",
        "mediapackagev2:GetOriginEndpointPolicy",
        "mediapackagev2:ListHarvestJobs",
        "mediapackagev2:GetHarvestJob",
        "logs:DescribeDeliverySources"
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

- `references/access-log-analysis.md`
- `references/v1-health-checklist.md`
- `references/v2-health-checklist.md`
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them
- `references/secondary-checks.md`: lower frequency checks, loaded on demand

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent conflates the two MediaPackage APIs and misreads its most common dimension trap. This skill works both v1 and v2 surfaces explicitly, knows that `StatusCodeRange` (4xx/5xx) and `StatusCode` are different dimensions that silently return empty results when swapped, isolates ingest-side from egress-side failure using `IngressBytes`/`EgressRequestCount` before assigning blame, reads the `x-amzn-mediapackage-active-input` header for input failover state, and detects v2 stuck state (recommending, never performing, a customer-run reset, verified afterward via `ResetAt`).
