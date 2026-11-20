# LLMOps Agent — Custom Agent

> ⚠️ **Non-Production Notice**: Sample code, not intended for production use without additional
> review and testing. Validate in a non-production Agent Space first, and review the tool
> assignment and IAM permissions against your organization's policies.

## Purpose

The LLMOps Agent triages and reviews GenAI workloads on Amazon Bedrock, Amazon SageMaker AI and Amazon
Bedrock AgentCore. You ask it a question and it picks the right skill, so you don't have to know which
skill covers which service.

## Key Capabilities

- **Incident triage.** Report a symptom, such as climbing `ThrottlingException`, an agent returning
  empty or `Invocation5XXErrors` on an endpoint. The agent finds the failing component, works out where
  it's hosted, and decides whether the fault sits with AWS, your infrastructure or your application. It
  opens with a `TRIAGE:` line, the most likely cause and the next step.
- **On-demand questions.** Ask "how close are we to the TPM quota?" or "is the guardrail attached?". It
  answers with the value it observed and the check-id behind it.
- **Proactive assessment.** On a schedule or on request, it runs every skill and writes a posture report,
  with a trend section against the previous run.
- **Read-only.** It gives you the command for each fix. You run it.

## Prerequisites

- The eight OpsAI skills from this repository: every folder under [`skills/`](../../skills/) whose name
  starts with `opsai-`. Each one installs as **All agents**, because a custom agent can't load a skill
  installed for a single agent type.
- An Agent Space connected to the account and Region that host the workload.
- The IAM permissions each skill lists in its README.

## Creating the Agent

1. **Upload the skills.** Zip each skill from inside its folder, so `SKILL.md` sits at the root of the
   archive, and upload every zip with the agent type set to **All agents**:

   ```bash
   cd ../../skills
   for skill in opsai-*/; do
     (cd "$skill" && zip -r "../${skill%/}.zip" . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*')
   done
   ```

2. **Create the agent.** Choose **Agents**, **Create agent**, **Form**, and fill in:

   | Field | Value |
   |---|---|
   | Name | `llmops-agent` |
   | System prompt | all of `SYSTEM_PROMPT.md` (plain Markdown, no frontmatter) |
   | Skills | the eight OpsAI skills |
   | Memory stores | optional, for run-to-run trends |

3. **Add the tool.** Tools can only be assigned through chat. On the agent page choose **Edit**, then
   **Chat**, and send `Add the use_aws tool to this custom agent.` Check that `use_aws` appears under
   **Tools**. It covers every API the agent calls.

4. **Add a schedule (optional).** For the proactive assessment, add a schedule trigger on the agent
   page. `0 7 * * 1` (Mondays 07:00 UTC) is a good start. Run it once by hand first: the first run has
   no earlier report to compare with, and says so.

To keep the agent on one workload, add a line to the system prompt, for example "Restrict scope to
Bedrock resources tagged `Application=support-copilot` in `us-east-1`."

## Scheduling through the API

The service API has no run operation. `CreateTrigger` is the only call that reaches a custom agent:

```python
import boto3
c = boto3.Session(profile_name=PROFILE, region_name="us-east-1").client("devops-agent")
c.create_trigger(
    agentSpaceId=SPACE_ID,
    type="TIME_BASED",
    condition={"schedule": {"expression": "rate(7 days)"}},
    action={"actionType": "create:task", "task": {"agent": f"custom:{AGENT_ASSET_ID}"}},
    status="Active",
)
```

`type` takes `TIME_BASED` or `EVENT_BASED`, `status` takes `Active` or `Inactive` (case-sensitive), and
the expression takes `rate(...)` or `cron(...)` but not `at(...)`. For a one-off run, use a `cron()`
expression for a minute in the near future.

## Limitations

- One Region per run. A multi-Region workload needs a run per Region.
- A custom agent runs one invocation at a time, so a scheduled run blocks an ad-hoc one until it
  finishes.
- It never calls `InvokeModel` to test behaviour. A guardrail that looks right in its configuration can
  still act unexpectedly on an input the agent never sent.
- Trends need earlier reports. Without them, every proactive run behaves like the first.
- If a skill isn't installed, the agent says so instead of improvising that area's checks.

## Version History

See the `CHANGELOG.md` file in this directory.
