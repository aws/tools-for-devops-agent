# LLMOps Agent — Custom Agent

> ⚠️ **Non-Production Notice**: Sample code, not intended for production use without additional
> review and testing. Validate in a non-production Agent Space first, and review the tool
> assignment and IAM permissions against your organization's policies.

**This is the entry point.** The agent is the deliverable. It carries the persona, the routing
logic, and the model-path triage rules (localize, bind the hosting, rule locus and transience),
and it decides which skill a given task
needs. You do not invoke skills directly; you prompt the agent and it routes.

## What it does

Deployed in an AWS DevOps Agent Space scoped to a single GenAI workload. Three modes, selected
from what you ask:

- **Incident triage.** You report a symptom (`ThrottlingException` climbing, `InternalServerError`,
  an `InvocationsIntervened` spike, an agent returning empty, `Invocation5XXErrors` on an endpoint).
  The agent localizes the failing component, binds the hosting (Bedrock, SageMaker, AgentCore,
  self-hosted or third-party), runs the triage classifier, confirms against live evidence with
  `use_aws`, and leads with a `TRIAGE:` line, the most likely cause and the next action.
- **On-demand investigation.** You ask a question ("how close are we to the Claude TPM quota?",
  "is the guardrail attached?", "do we have any evaluation jobs?"). It routes to the one skill that
  owns the domain, answers with the figure it observed and the check id, and stops.
- **Proactive assessment.** On a schedule or on request, it runs every skill in order and produces
  a posture report with a trend section against the previous run.

## Skill composition

Eight skills, all in this repository's [`skills/`](../../skills/) directory. The agent is
self-contained by design and consumes no skill from outside this repository.

| What the operator raises | Skill loaded |
|---|---|
| Live model-call failures: 5xx, throttling, timeouts, latency, empty responses (Bedrock, SageMaker, AgentCore, self-hosted) | [`opsai-incident-triage`](../../skills/opsai-incident-triage/) |
| Quality regression, quality gates, truncated outputs, Bedrock (model and RAG) and SageMaker (Nova recipe, LLM-as-judge) evaluation jobs | [`opsai-ml-eval-check`](../../skills/opsai-ml-eval-check/) |
| Invocation logging, model access, inference profiles, a failing call denied by IAM, SCP or marketplace | [`opsai-bedrock-review`](../../skills/opsai-bedrock-review/) |
| Who can invoke Bedrock: IAM users, long-term API keys, dormant or root keys, GuardDuty AI Protection findings | [`opsai-bedrock-security`](../../skills/opsai-bedrock-security/) |
| Content filters, PII, denied topics, grounding, version pinning | [`opsai-bedrock-security`](../../skills/opsai-bedrock-security/) |
| Spend, cost attribution, pricing tiers, quota headroom, provisioned throughput | [`opsai-capacity-cost`](../../skills/opsai-capacity-cost/) |
| Knowledge bases, ingestion health, chunking, embedding model | [`opsai-bedrock-review`](../../skills/opsai-bedrock-review/) |
| Bedrock Agents, action groups, AgentCore runtimes and gateways | [`opsai-bedrock-agentcore`](../../skills/opsai-bedrock-agentcore/) |
| SageMaker inference: real-time, serverless and async endpoints, batch transform — failures, scaling, cold start, notifications, backlog, right-sizing, endpoint cost, monitoring, VPC/CMK, deployed-endpoint lineage | [`opsai-sagemaker-inference`](../../skills/opsai-sagemaker-inference/) |
| SageMaker training/customization (Nova, JumpStart) job failures and Model Registry governance of customized artifacts | [`opsai-sagemaker-training`](../../skills/opsai-sagemaker-training/) |


## Files

```
custom-agents/llmops-agent/
├── SYSTEM_PROMPT.md   paste into the agent creation form — this IS the agent
├── README.md          this file
└── CHANGELOG.md
```

`SYSTEM_PROMPT.md` is plain Markdown with **no frontmatter**. DevOps Agent reads only the system
prompt from it. Name, skills, and memory stores are chosen in the creation form. Tools are assigned
through Chat. Schedules are triggers on the agent detail page.

## Setup

### 1. Upload the eight skills

Zip each skill from this repository's `skills/` directory and upload it. Zip from **inside** each directory so `SKILL.md` lands
at the archive root.

```bash
cd ../../skills
for skill in opsai-incident-triage opsai-bedrock-review opsai-bedrock-security \
             opsai-capacity-cost opsai-bedrock-agentcore opsai-ml-eval-check \
             opsai-sagemaker-inference opsai-sagemaker-training; do
  (cd "$skill" && zip -r "../$skill.zip" . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*')
done
```

Upload all eight. For each, select **"All agents"** as the Agent Type. A custom agent cannot load a
skill unless it is imported as "All agents."

### 2. Create the agent

**Agents** → **Create agent** → **Form**:

| Field | Value |
|---|---|
| Name | `llmops-agent` |
| System prompt | paste all of `SYSTEM_PROMPT.md` |
| Skills | all eight |
| Memory stores | optional; attach a custom store if you want run-to-run trend memory |

### 3. Add the tool

Tools can only be assigned through Chat. On the agent page choose **Edit** → **Chat**, then:

```
Add the use_aws tool to this custom agent.
```

Confirm `use_aws` appears under **Tools** on the agent page. That one tool covers every API the
agent calls; it does not need a per-service list.

### 4. Set a trigger (optional)

Add a schedule trigger on the agent detail page for the proactive assessment. `0 7 * * 1`
(Mondays 07:00 UTC) is a reasonable default. Move it so the report lands before your operations
review rather than during it.

Run once manually first. The first run has no previous report to diff and will say so.

## Configuration

| Setting | Default | Notes |
|---|---|---|
| Scope | the Agent Space's configured Regions | Pin it to one workload by adding a line to the system prompt, e.g. "Restrict scope to Bedrock resources tagged `Application=support-copilot` in `us-east-1`." |
| Schedule | none until you add a trigger | Weekly is enough; GenAI posture changes with deployments, not with traffic |
| Tools | `use_aws` | assign via Chat |
| Skills | 8 | all in this repository's `skills/` directory |

Bedrock and its evaluation APIs are Region-gated. Confirm the Regions in scope actually host the
workload, or the agent will correctly report features as unavailable rather than missing.

## Relevant quotas

| Quota | Value |
|---|---|
| Skills per custom agent | 200 |
| System prompt length | 50,000 characters |
| Concurrent invocations per custom agent | 1 |
| Custom agent invocation timeout | 1 hour |

`SYSTEM_PROMPT.md` is well under the prompt limit. Note the concurrency of 1: a scheduled run in
progress will block an ad-hoc invocation of the same agent until it finishes.

## Limitations

- **Read-only.** It provides the fix command; a human runs it.
- **One Region per run.** Multi-Region workloads need one run per Region.
- **Trend depth is bounded by retention.** If prior reports are not retained, every proactive run
  behaves like a first run.
- **No load-based probing.** It never calls `InvokeModel` to measure behaviour, so a guardrail that
  is attached and configured can still behave unexpectedly on an input the agent never sent.
- **Depends on its skills being present.** If a skill is not in the Space, the agent says so rather
  than improvising that domain's checks.

## Version history

See the `CHANGELOG.md` file in this directory.

## Triggering it through the API

There is no invoke, run or start operation in the service API. Of its 62 operations, the only one that reaches a custom agent is `CreateTrigger`. Chat cannot: `SendMessage` takes `assetIds`, but those are file attachments, and passing a custom agent id returns `Asset '<id>' is type 'CUSTOM_AGENT', expected 'ATTACHMENT'`.

```python
import boto3
c = boto3.Session(profile_name=PROFILE, region_name="us-east-1").client("devops-agent")

c.create_trigger(
    agentSpaceId=SPACE_ID,
    type="TIME_BASED",
    condition={"schedule": {"expression": "rate(7 days)"}},
    action={"actionType": "create:task",
            "task": {"agent": f"custom:{AGENT_ASSET_ID}"}},
    status="Active",
)
```

The `custom:` prefix on the asset id is what selects the agent. Four things the API rejects, none of them visible in the service model:

| Field | Accepted | Rejected |
|---|---|---|
| `type` | `TIME_BASED`, `EVENT_BASED` | `SCHEDULE` |
| `status` | `Active`, `Inactive` | `ACTIVE`, `INACTIVE`, `DISABLED` |
| `action` | the document shape above | every nested variant tried |
| `expression` | `rate(...)`, `cron(...)` | `at(...)` |

Status is mixed case and case-sensitive. The returned `triggerId` is prefixed `goal-`, because triggers are goals underneath, so a trigger also shows up in `ListGoals`.

For a one-off run, a `cron()` expression at a specific future minute works and is the closest thing to on demand. `at()` is refused.

`SendMessage` is boto3 only, absent from the AWS CLI, because it returns an `EventStream`. Read the reply by iterating `responseCreated`, then `contentBlockStart`, `contentBlockDelta`, `contentBlockStop`.

