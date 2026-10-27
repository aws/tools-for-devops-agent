# MediaConnect Deep Investigation: AWS DevOps Agent Skill

Deep, evidence-first investigation of a single AWS Elemental MediaConnect flow: source connectivity, protocol-aware packet loss (ARQ/FEC layering), TR 101 290 transport stream health, per-output delivery, content quality monitoring, entitlements, bridges/gateways, routers, and EventBridge events. MediaConnect emits no CloudWatch Logs; the skill works from CloudWatch metrics, `describe-flow` error messages, and EventBridge events, and reports explicit DATA GAPs where a signal is not observable.

> **Non-production disclaimer.** This skill is sample code. It is not intended for production use without additional review and testing. Validate it in a non-production environment first, and review the IAM permissions it uses against your organization's security policies.

## Agent Types

On-demand (Chat) and Incident RCA investigations. Select the relevant agent types in the Operator Web App at upload time, or **Generic** to make the skill available to all agent types.

## Usage

Upload the skill to your Agent Space through the DevOps Agent Operator Web App: zip this directory with `SKILL.md` at the root and select the agent types listed above (see [Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html)). The skill triggers on symptom descriptions and questions in its domain. There is no need to name it. Example: "Our MediaConnect flow is showing packet loss and the failover source didn't take over."

## Prerequisites

The skill is read-only by design and never performs write operations. The DevOps Agent role needs the actions below. They are granted by the opt-in `EnableMediaConnectInvestigate` parameter (default `true`) in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml), together with the CloudWatch metrics and Logs Insights reads the media investigation skills share. Some of these actions may already be granted by `AIDevOpsAgentAccessPolicy`; granting them again is harmless.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MediaConnectInvestigate",
      "Effect": "Allow",
      "Action": [
        "mediaconnect:DescribeFlow",
        "mediaconnect:ListFlows",
        "mediaconnect:ListEntitlements",
        "mediaconnect:ListBridges",
        "mediaconnect:DescribeBridge",
        "mediaconnect:ListRouterInputs",
        "mediaconnect:ListRouterOutputs",
        "mediaconnect:GetRouterInput",
        "mediaconnect:GetRouterOutput",
        "mediaconnect:GetRouterInputSourceMetadata",
        "mediaconnect:GetRouterInputThumbnail",
        "events:ListRules"
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

- `references/eventbridge-events.md`
- `references/flow-health-checklist.md`
- `references/redundancy-patterns.md`
- `references/lookup-tables.md`: metric, status and field tables, loaded by the step that uses them
- `references/secondary-checks.md`: lower frequency checks, loaded on demand

## Evaluation

`evals/evals.json` holds the functional eval definitions and `evals/eval_queries.json` the trigger queries for the skill evaluation tool. Recorded results live under `evals/structure/`, `evals/best-practices/` and `evals/functional/`.

## What this adds over default agent behavior

A baseline agent asked about flow packet loss typically lists generic CloudWatch metrics. This skill knows the transport-layer semantics the metrics encode: that `NotRecoveredPackets` (not `PacketLossPercent` alone) is the signal that loss reached the output, how recovery metrics differ across RTP-FEC, RTT-based, and Zixi protocols, how to verify source-failover and redundancy topology actually engaged, and how to distinguish network-path loss from source-side loss before recommending escalation.
