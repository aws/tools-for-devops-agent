# MediaLive Deep Investigation: AWS DevOps Agent Skill

Deep investigation of a single AWS Elemental MediaLive channel: channel state, per-input-type diagnosis (MediaConnect, RTP/RTMP push, pull, Link devices, SRT), encoding health (ActiveAlerts, DroppedFrames, FillMsec, SvqTime), per-output-group 4xx/5xx analysis, STANDARD pipeline synchronization, schedule verification, and encoder log parsing.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat) and Incident RCA investigations. Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "MediaLive channel alerts are firing and the output looks frozen."

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaLiveInvestigate` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaLiveInvestigate",
      "Effect": "Allow",
      "Action": [
        "medialive:DescribeChannel",
        "medialive:DescribeInput",
        "medialive:DescribeInputDevice",
        "medialive:DescribeSchedule",
        "medialive:ListChannels",
        "medialive:ListAlerts"
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

- `references/alert-retrieval.md`
- `references/channel-health-checklist.md`
- `references/encoder-log-parsing.md`
- `references/input-type-patterns.md`: per input type diagnostic checks for Step 2
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them
- `references/output-destination-checks.md`: per destination type checks for Step 4

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent treats a MediaLive incident as generic metric-reading. This skill knows the channel alert taxonomy and what each alert class implies, that metrics must be read per pipeline (`Pipeline` dimension 0/1) or dual-pipeline failures hide behind healthy averages, how input-switch and failover events appear in the schedule and alert history, and how to separate input-side starvation from encode-side pressure before pointing upstream or downstream.
