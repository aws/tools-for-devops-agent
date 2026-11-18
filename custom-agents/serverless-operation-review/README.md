# Serverless Operation Review — Custom Agent

> ⚠️ **Non-Production Notice**: This custom agent is sample code, not intended for production use
> without additional review and testing. Validate in a non-production Agent Space first, and review
> the tool assignments and IAM permissions against your organization's policies.

## What It Does

Runs the [`serverless-operation-review`](../../skills/serverless-operation-review/) skill on a weekly
schedule and reports both the current posture and what changed since the previous run.

The one-off skill answers "what is wrong right now". This agent answers the questions a weekly cadence
makes possible:

- What broke, or got fixed, since last week?
- Which findings have been open for three runs and need an owner decision rather than another reminder?
- Which metrics are trending toward a threshold they have not yet crossed — error rate creeping up,
  `Duration` p99 closing on the timeout, memory utilization growing, concurrency runway shrinking?
- Did a new function arrive already non-compliant?

## Prerequisites

- An AWS DevOps Agent Agent Space with custom agents enabled
- The `serverless-operation-review` skill uploaded to the same Agent Space
- No extra IAM permissions if the Agent Space uses the default role: `AIDevOpsAgentAccessPolicy`
  already grants every action the skill uses. For a custom, narrower role, see the permission list in
  the [skill README](../../skills/serverless-operation-review/README.md#iam-permissions)
- A delivery destination configured for the report

## Setup

1. Upload the skill first — the agent depends on it:

   ```bash
   cd skills
   zip -r serverless-operation-review.zip serverless-operation-review/ \
     -x '*/evals/*' '*/README.md' '*/CHANGELOG.md' '*/.skilleval.yaml' '*/eval_results.json'
   ```

   Upload the zip in the Agent Space **Skills** page and select the **Chat tasks** and **Evaluation**
   agent types.

2. Create the custom agent in the Agent Space **Custom agents** page, using `SYSTEM_PROMPT.md` in this
   directory for the system prompt. Assign the following tools: CloudWatch, CloudWatch Logs, Lambda,
   API Gateway, Step Functions, DynamoDB, SQS, SNS, EventBridge, IAM, Cost Explorer, Service Quotas.
   Assign the `serverless-operation-review` skill. Set the schedule to `0 7 * * 1` (Mondays at
   07:00 UTC).

3. Confirm the schedule. The default is `0 7 * * 1` — Mondays at 07:00 UTC. Move it so the report
   lands before your weekly operations review rather than during it.

4. Run it once manually before trusting the schedule. The first run has no previous report to diff
   against and will say so.

## Configuration

| Setting | Default | Notes |
|---|---|---|
| Schedule | `0 7 * * 1` | weekly; more frequent runs produce noisier deltas without much added signal |
| Scope | all configured Agent Space Regions | narrow it to the Regions that actually hold serverless workloads to cut runtime and API cost |
| Skill | `serverless-operation-review` | required |
| Tools | CloudWatch, CloudWatch Logs, Lambda, API Gateway, Step Functions, DynamoDB, SQS, SNS, EventBridge, IAM, Cost Explorer, Service Quotas | all read-only |

To scope the agent to one application rather than a whole account, add a line to the system prompt
naming the tag or stack boundary, for example: "Restrict scope to resources tagged
`Application=checkout`."

## Sample Application for Testing

`sample-app/` contains a SAM template that deploys a deliberately misconfigured serverless workload —
one fault per check family — so you can confirm the skill and agent actually detect what they claim
to. See [`sample-app/README.md`](sample-app/README.md).

**It creates real, billable AWS resources and deliberately insecure configuration.** The two faults
that would create internet-reachable endpoints — an unauthenticated function URL and an API stage with
no authorizer — are gated behind the `SeedPublicExposureFaults` parameter, which defaults to `false`,
so a default deployment exposes nothing anonymously. Deploy only in an isolated non-production
account, and delete the stack when you are done.

## Limitations

- **Trend depth is bounded by report retention.** The agent can only diff against reports it can
  retrieve. If reports are not retained, every run behaves like a first run.
- **A weekly window can miss short incidents.** The agent reviews a 7-day metric window; a two-hour
  outage that resolved itself may not move any weekly aggregate. It complements alarms, it does not
  replace them.
- **Inherits every skill limitation** — configuration and telemetry only, estimated per-resource
  costs, sampled log analysis, no code inspection. See the
  [skill README](../../skills/serverless-operation-review/README.md#limitations).
- **Read-only by design.** It will not fix anything, including findings it has reported for months.

## Version History

See [CHANGELOG.md](CHANGELOG.md).
