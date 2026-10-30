# MediaTailor Investigation (SSAI and Channel Assembly): AWS DevOps Agent Skill

Investigation of AWS Elemental MediaTailor covering both SSAI (ad insertion: fill analysis with a three-way diagnostic split, viewer-visible fill behavior such as avail suppression, slate and personalization threshold, ADS health, skipped-ad reasons, stale-manifest decomposition, prefetch use, player-facing HTTP status triage, session/manifest log analysis) and Channel Assembly (channel/schedule/source-resolution state, source access requirements, ListAlerts catalog, As-Run logs). Leads every log step with an observability precheck (session logs are gated by `PercentEnabled`, sampled, filterable by event type, and depend on the delivery strategy) and emits explicit DATA GAPs instead of false all-clears.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat) and Incident RCA investigations. Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "Ads aren't being inserted on our live stream, viewers see slate instead."

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaTailorInvestigate` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

MediaTailor reads are not part of `AIDevOpsAgentAccessPolicy`, so this statement is required for the skill to function.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaTailorInvestigate",
      "Effect": "Allow",
      "Action": [
        "mediatailor:GetPlaybackConfiguration",
        "mediatailor:ListPlaybackConfigurations",
        "mediatailor:ListChannels",
        "mediatailor:DescribeChannel",
        "mediatailor:GetChannelSchedule",
        "mediatailor:DescribeProgram",
        "mediatailor:ListSourceLocations",
        "mediatailor:DescribeSourceLocation",
        "mediatailor:ListVodSources",
        "mediatailor:DescribeVodSource",
        "mediatailor:GetChannelPolicy",
        "mediatailor:ListAlerts"
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

- `references/channel-assembly-checklist.md`: mechanical PASS/FAIL checklist, source access requirements, ListAlerts catalog
- `references/ssai-metric-reference.md`: public metric catalog, fill-rate math, baseline and correlation method
- `references/ssai-log-catalog.md`: ADS/manifest log event types, fields, ready-to-run Logs Insights queries
- `references/ssai-fill-behavior.md`: why the viewer saw slate, source content, or a partial break (suppression, slate, threshold, bumpers, pre-roll)
- `references/playback-errors-and-limits.md`: player-facing status codes, fixed limits and quotas, parameter rules, CDN context
- `references/channel-assembly-procedure.md`: Steps C1 to C4 of the Channel Assembly path
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them
- `references/report-outlines.md`: SSAI and Channel Assembly report outlines for Step F

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent asked "ads aren't playing" checks generic error metrics. This skill follows the SSAI transaction end to end: ADS request/response validation, empty-VAST versus transcode-pending versus never-personalized (avail suppression, personalization threshold) as distinct root causes with different owners, awareness that MediaTailor log emission is gated by `PercentEnabled`, event filters, and the delivery strategy (absence of logs is a configuration fact, not evidence of health), a mapping from player-facing HTTP status codes and the service's fixed timeouts to the layer that produced them, a precheck for the cached-personalized-manifest CDN failure that leaves every metric healthy, and the boundary between origin problems (investigate with aws-mediapackage-investigate), ADS-owner problems, and ad-decision or transcode problems that belong to this layer.
