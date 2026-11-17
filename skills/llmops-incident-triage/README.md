# llmops-incident-triage

> **Non-production disclaimer.** This skill is an operational aid for triaging the LLM layer of an
> incident on AWS. It performs **read-only** analysis and returns a fault-locus assessment; it does
> not modify any resource and it does not rule root cause. Assessments and remediations are guidance,
> not guarantees — confirm with AWS Support and the AWS Health Dashboard before acting on a
> provider-side determination. Not an AWS-published commitment. Validate in a non-production context
> before relying on it operationally.

## What It Does

`llmops-incident-triage` triages the **LLM layer** of a live failure on AWS and answers the question
customers ask during an incident — **"is this an AWS problem or mine?"** — with evidence instead of a
guess.

**It does not own the investigation.** The DevOps Agent's investigation discovers the workload, holds
the topology and change history, and writes the operator-facing answer. This skill is loaded once an
LLM call or agent loop is **confirmed from evidence** in the failing path, and it returns an
assessment for the host to reconcile.

It provides:

- **A hosting binding, established before anything is measured.** `bedrock`, `sagemaker`,
  `agentcore`, `self-hosted-alb`, `self-hosted-lambda` or `third-party`. "My agent is broken" does
  not mean AgentCore: an agent loop runs in a Lambda, a container, an EC2 process, or off AWS. An
  unbindable path returns `locus=UNDETERMINED` and names the missing fact rather than guessing.
- **The classifier.** Step 0 binds, then a six-step decision procedure (provider health →
  server-error rate → blast radius → onset timing → provider-side exception signatures →
  client-vs-server dominance) returning `locus` — `PROVIDER`, `INFRASTRUCTURE`, `APPLICATION` or
  `UNDETERMINED` — and `transience` — `TRANSIENT`, `PERSISTENT` or `UNKNOWN`. The ladder rules on
  three abstract signal slots resolved per binding, so the logic is identical across hostings while
  the metric names are not. It stops the agent from telling a customer to fix their config when the
  cause is regional capacity, and from telling them to "wait and retry" when their IAM policy is
  broken.
- **Request-path triage.** Seven stages — caller, ingress, agent loop, model endpoint, retrieval,
  tools, output filter — with symptom → first stage, and stage → the skill that owns depth. Two
  stages deliberately name no skill here: a self-hosted agent loop and the compute beneath it are
  the host investigation's.
- **Incident signatures.** A symptom → first-signal → APIs → likely-locus → trap lookup table
  covering `ThrottlingException`, climbing throttles, `InternalServerError`/5xx,
  `ServiceUnavailableException`, `ModelNotReadyException`, `ValidationException`, intermittent
  timeouts, empty agent responses, empty retrieval, unexplained latency spikes, and
  `TimeToFirstToken` degradation.
- **Telemetry readiness.** The LLM-TEL-001..008 checks that determine whether triage is even possible.
  When they fail, their absence is reported as the reason the incident is hard to diagnose.

Every finding carries an AWS-documented `check-id`, a severity, and a citation. The skill never invents
a threshold and never mutates a resource.

### When NOT to use it

The first two fire most often:

- **Workload discovery.** "Something in production is broken", with no component localized and no
  LLM confirmed in the failing path. That is the host investigation's phase, not a smaller version of
  this skill's job.
- **A failure with no LLM in the failing path**, however the symptom was phrased.
- The **compute beneath a self-hosted model** — instances, containers, cluster scheduling → the host
  investigation. This library has no check for it.
- Configuration **posture reviews** → `llmops-bedrock-configuration` (+ the focused `llmops-*` skills).
- **Access-denied** diagnosis (IAM/SCP/marketplace) → `llmops-bedrock-configuration`.
- **Quality regressions** / eval gating → `llmops-quality-evaluation`.

## Prerequisites

Read-only IAM permissions in the account/region under investigation:

- **Bedrock (read):** `bedrock:Get*`, `bedrock:List*`, `bedrock-agent:Get*`, `bedrock-agent:List*`
  (model lifecycle, invocation-logging config, agent/alias resolution, knowledge-base ingestion jobs).
- **CloudWatch:** `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`,
  `cloudwatch:ListMetrics` (invocation errors, throttles, latency, `TimeToFirstToken`).
- **CloudWatch Logs:** `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`,
  `logs:DescribeLogGroups` (invocation-log error-pattern and `stopReason` scans).
- **AWS Health:** `health:DescribeEvents` (active service events in the affected region/window).

No write, modify, or delete permissions are needed or used.

## Uploading to AWS DevOps Agent

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip
from **inside** the skill directory:

```bash
cd skills/llmops-incident-triage && zip -r ../llmops-incident-triage.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/llmops-incident-triage.zip` containing `SKILL.md` and `references/` at the top level, with
the repo-management files excluded.

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `llmops-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

## Usage Examples

- "We're getting intermittent `InternalServerError` from Bedrock in us-east-1 — is this an AWS issue
  or ours?" → binds `bedrock`, runs the classifier, checks AWS Health + server-error rate across
  models, returns `locus=PROVIDER transience=TRANSIENT`.
- "Throttling is spiking but our config looks right." → signature match on climbing throttles,
  Step 6 confirms client-error dominance → `locus=APPLICATION`, names `llmops-capacity-cost` as the
  quota-posture owner.
- "Our agent is returning empty responses." → **binds first.** On `agentcore`: resolve alias→version,
  check guardrail `InvocationsIntervened` and `stopReason`. On a self-hosted loop there is no alias,
  and the loop's own logs are the source.
- "My agent on the production website is not responding." → declines to assume a hosting, says the
  component and the serving service must be established first, and returns nothing Bedrock-shaped.
- "Our self-hosted vLLM on EKS is returning 503s." → binds `self-hosted-alb`, records provider health
  as `not-applicable`, returns `locus=INFRASTRUCTURE` — not `PROVIDER`, because the customer is the
  provider — and hands the serving layer to the host investigation.
- "Can I even see what my agent is doing?" → telemetry-readiness check (LLM-TEL-001, LLM-TEL-003).
- "Latency spiked and we didn't change anything." → classifier Steps 3–4; broad blast radius + abrupt
  uncorrelated onset leans `PROVIDER`.

## Version History

See the `CHANGELOG.md` file in this directory.
