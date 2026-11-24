---
name: opsai-bedrock-agentcore
description: Review the health of the agent layer on AWS, covering Amazon Bedrock AgentCore and the legacy
  Bedrock Agents. Use this skill when an agent will not start or cannot be invoked, when a gateway or
  action group fails, when an agent returns nothing or produces no traces, when it behaves differently
  in production than in test, or when someone asks which agent version is actually live, even if they
  do not mention runtime roles, VPC endpoints, service control policies, OTLP telemetry or aliasing by
  name. Findings carry LLM-AC and LLM-AGT check-ids with a severity and an AWS-doc citation, from read-only
  APIs.
metadata:
  author: ydimawae
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Reviews Amazon Bedrock AgentCore and Bedrock Agents health: invocation, gateways, action groups, traces and live versions."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock AgentCore, Amazon Bedrock, Amazon CloudWatch, AWS X-Ray"
  aws-devops-agent-skills.technical-domains: "AI/ML, Observability"
---

# OpsAI — Agent & Runtime Health

You review the health of the **agent layer** on AWS. The **primary surface is Amazon Bedrock AgentCore**
— the runtimes, gateways, memories, and workload identities you deploy and operate for your own agent
code. **Amazon Bedrock Agents Classic** — the older managed agents with action groups and aliases — is
covered as **legacy, maintenance-mode** surface. Your job is to find the configuration and observability
gaps that make an agent fail to invoke, fail a tool call, run unguarded, or become impossible to debug —
and to report each gap with evidence, a stable check-id, and a severity, before anyone prescribes a fix.

This skill works on its own. Other skills are optional; see *Related skills (optional)*.

Every finding is grounded in the catalogs under `references/`: `checks-agentcore.md` (LLM-AC-001..014,
the primary AgentCore family) and `checks-agents.md` (LLM-AGT-001..011, Bedrock Agents Classic). Each
catalog row carries a stable `check-id`, a severity, a detection rule, a remediation, and an AWS-doc
citation. You never invent a threshold: if AWS publishes no number, the catalog marks it
`workload-specific` and you report it as `INFO`. This skill uses **read-only APIs only** — it never
mutates a resource.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## Bedrock AgentCore (primary) vs Bedrock Agents Classic (legacy, maintenance mode)

These are two different services with different resources and different checks, and the first thing to
establish is which one the user is running. **AgentCore is where new work goes.** Bedrock Agents Classic
is in **maintenance mode**: per the AWS product-page End of Support Notice it is "no longer available to
new customers", and for existing customers it remains available with **no planned end-of-life date** but
"no new features are planned", and AWS recommends migrating to AgentCore. Classic still runs real
production workloads and existing customers still raise cases, so the Classic checks remain in force —
but a reader must know that half of this skill is **not growing**.

| | **Bedrock AgentCore** (family LLM-AC, primary) | **Bedrock Agents Classic** (family LLM-AGT, legacy / maintenance mode) |
|---|---|---|
| What it is | A runtime you deploy and operate for your own agent code | Managed agents orchestrated by Bedrock, closed to new customers |
| Core resources | runtimes, gateways, memories, workload identities | agents, action groups, aliases, prompts, memory |
| How prod behaviour is set | the deployed **runtime version** | an **alias** points at a published **version** |
| Primary collection client | `bedrock-agentcore-control` (IAM prefix `bedrock-agentcore:`) + `iam` + `ec2` + `organizations` | `bedrock-agent` (IAM prefix `bedrock:`) |
| Representative checks | runtime role permissions, VPC endpoints, gateway targets, OTLP telemetry | guardrail attached, action-group Lambda scope, alias pinning, tracing |

If the user says "my runtime cannot invoke," "gateway error," or "missing VPC endpoint," start in
**LLM-AC**. If they say "my agent returns empty," "which agent version is live," or "my action group
fails," they are almost certainly on **Bedrock Agents Classic** — start in **LLM-AGT** and keep the
maintenance-mode framing in mind. If it is unclear, resolve which service is in play before collecting —
do not run both catalogs blindly.

**Migration note.** If the workload runs Bedrock Agents Classic, raise the advisory finding
**LLM-AGT-011** (see the Classic procedure, Step 8): Classic is closed to new customers and receives no
new features, and the two recommended migration paths are the **AgentCore harness** (config-based, the
closest analog to Classic) or **code-defined agents on AgentCore**. AWS also ships a migration skill in
the agent toolkit for AWS, invoked with a prompt like "Help me migrate my Bedrock Agent to AgentCore
harness." Knowledge Bases are **not affected** and the underlying resource is unchanged. Guardrails
configured on the model still apply when invoked through AgentCore; agent-level enforcement is available
through AgentCore gateway policies.

**AgentCore coverage scope (known, not silently omitted).** AgentCore consists of Runtime, Memory,
Gateway, Browser, Code Interpreter, Identity, Policy, Observability, and Evaluations. This skill today
covers **Runtime, Gateway, and Observability** (the LLM-AC family), plus the documented **quotas and
session limits** of Runtime, Gateway and Memory (LLM-AC-011), and **AgentCore Memory**: short-term
events, branches, asynchronous long-term extraction and Memory latency (LLM-AC-012), and **Browser and Code
Interpreter** session limits and failures (LLM-AC-013), and **cross-account access** to Runtime,
Gateway and Memory through resource-based policies (LLM-AC-014). It does **not yet cover** **Identity, Policy, or
Evaluations** behaviour — that is stated here as
known scope; do not invent checks for them.

**API namespace note.** The `bedrock-agentcore-control` API namespace is being superseded by
`agent-registry-control` for registry operations, and AWS docs label the `bedrock-agentcore-control`
namespace "to be deprecated" in those examples. Do not write new checks against the older namespace
without accounting for this.

## When to Use

Activate this skill when the user:

- Reports an **AgentCore runtime that cannot invoke or will not start**, **gateway errors**, or a
  **missing VPC endpoint** (primary surface, LLM-AC).
- Reports a **runtime role permission denied**, or asks whether the runtime execution role can reach the
  models and dependencies it needs (LLM-AC-001/002).
- Says there are **no traces from my agent**, or asks whether they can see what the runtime is doing
  across stages (LLM-AC-005/006/007).
- Reports a **Bedrock Agents Classic agent returning empty** or erroring, or an **action group / tool
  call failing** (legacy surface, LLM-AGT).
- Asks **which agent version is live**, or says their **Classic agent has no guardrail** (LLM-AGT).
- Wants a **posture review of a runtime or an agent** against best practice (the AC/AGT catalogs), or is
  **running Bedrock Agents Classic and should hear the migration advisory** (LLM-AGT-011).

## When NOT to Use

These areas are outside the agent/runtime layer. For each, follow *Related skills (optional)*:
- **Bedrock model configuration & invocation logging** (model lifecycle, invocation-logging config,
  inference profiles), and **knowledge bases / RAG** ingestion and retrieval quality.
- **Guardrail policy content** (what the guardrail blocks/masks, strength of filters). This skill only
  checks that a guardrail *is attached* (LLM-AGT-001).
- **Quota, throttling economics, and cost.**
- **SageMaker** endpoints, batch, training and Model Registry.
- **Is-this-AWS-or-mine incident triage** (live failure, service-vs-config ruling).
- **Model-output quality / evaluation** (answers got worse, eval gating).
- **Future price quotes** — direct to the [AWS Pricing Calculator](https://calculator.aws/).

## Router

How to read each API and metric is in `references/collection-reference.md`. Load it with any row.
AgentCore (LLM-AC) is the primary surface; the Bedrock Agents Classic (LLM-AGT) rows below are legacy,
maintenance-mode coverage.

| Operator says | First read | Load |
|---|---|---|
| AgentCore runtime will not start / cannot invoke | `ListAgentRuntimes` / `GetAgentRuntime` for status, version, role ARN | `references/checks-agentcore.md` (LLM-AC-001) |
| Runtime role permission denied | The runtime role's identity policies, action by action (`iam:SimulatePrincipalPolicy` only where the runtime allows it) | `references/checks-agentcore.md` (LLM-AC-001), `references/api-quirks.md` |
| It is denied even though the role looks right (for example an admin role) | How the caller got its credentials: Full method: [`references/router-details.md`](references/router-details.md) §1 | [Session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html#policies_session), `references/checks-agentcore.md` (LLM-AC-002) |
| An SCP denies `InvokeModel` only when the call goes through an application inference profile, while direct model calls succeed | The SCP `Deny` statement itself (`DescribePolicy`): Full method: [`references/router-details.md`](references/router-details.md) §2 | [Condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html), `references/checks-agentcore.md` (LLM-AC-002) |
| Missing VPC endpoint / no private path | `ec2:DescribeVpcEndpoints` for bedrock-runtime, bedrock-agent-runtime, S3, logs, monitoring | `references/checks-agentcore.md` (LLM-AC-003) |
| Gateway target is failing | `GetGateway` / `ListGateways` and each target (`ListGatewayTargets` / `GetGatewayTarget`): endpoint, credential provider, schema | `references/checks-agentcore.md` (LLM-AC-004, LLM-AC-008) |
| A call through a gateway returns 403 / `insufficient_scope` or another token error | The gateway's `authorizerConfiguration.customJWTAuthorizer`: Full method: [`references/router-details.md`](references/router-details.md) §3 | [Inbound JWT authorizer](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/inbound-jwt-authorizer.html), `references/checks-agentcore.md` (LLM-AC-004) |
| Deploy, create or update of a runtime fails with a credentials or AccessDenied error, while model calls with the same identity work | The deploying identity's policies for `bedrock-agentcore:*` control-plane actions and `iam:PassRole` on the execution role (`bedrock:*` does not cover the `bedrock-agentcore` prefix) | [Runtime permissions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html), `references/checks-agentcore.md` (LLM-AC-001) |
| Access denied / 403 on an S3 bucket in another account (runtime code artifact or gateway target schema) | Which account owns the bucket vs the runtime/gateway, and the exact S3 field used | `references/api-quirks.md` §15 |
| HTTP 429 / throttling on invoke, under parallel or load tests, or requests slow down when sent concurrently to one session | Which layer throttled (`InvokeAgentRuntime` 429 with no runtime log line, vs the agent's own model call, gateway or memory) and the call rate vs the documented quota; whether callers mint a new session ID per call; whether concurrent requests share one session | `references/checks-agentcore.md` (LLM-AC-011), `references/api-quirks.md` §16 |
| A principal in another account cannot invoke, stop sessions on, or use a runtime, gateway or memory; or 429s and active sessions pile up while a cross-account caller stops sessions | For **each action** the caller uses (`InvokeAgentRuntime`, `StopRuntimeSession`, `InvokeGateway`, Memory actions): Full method: [`references/router-details.md`](references/router-details.md) §4 | `references/checks-agentcore.md` (LLM-AC-014), `references/api-quirks.md` §19 |
| Cold start, or lost in-memory state between calls | Which session ID the client sends, and in which header for the runtime's protocol | [`references/runtime-sessions.md`](references/runtime-sessions.md) |
| The agent (or an orchestrator and its sub-agents) forgets earlier turns although the session ID is stable; memory branches, long-term records or Memory latency behave unexpectedly | Whether the code writes (`CreateEvent`) and reads (`ListEvents`) memory events per turn, on which memory resource and actor/session scope; for latency, the Memory metrics over the window | `references/checks-agentcore.md` (LLM-AC-012), `references/api-quirks.md` §17 |
| A Browser tool (or Code Interpreter) session crashes, slows or changes size after running for a while; or a console page or dashboard stays loading in the operator's own web browser | Which browser it is: the managed Browser tool (session age, task count, recording on or off, `viewPort`) or the operator's own browser (does it load in a private window, another browser, for a colleague) | `references/checks-agentcore.md` (LLM-AC-013), `references/api-quirks.md` §18 |
| No traces from my agent | OTLP / AgentCore Observability config and trace propagation | `references/checks-agentcore.md` (LLM-AC-005, 006, 007), `references/metrics-and-logs.md` |
| My bedrock agent returns nothing (legacy, Classic) | `GetAgent` for guardrail, model, prompt-override config | `references/checks-agents.md` (LLM-AGT-001) |
| Agent output changes between turns with the same prompt and config, for example citation or formatting style flips (legacy, Classic) | Treat it as orchestration nondeterminism until a trace shows otherwise: Full method: [`references/router-details.md`](references/router-details.md) §5 | [Advanced prompts](https://docs.aws.amazon.com/bedrock/latest/userguide/advanced-prompts.html), `references/checks-agents.md` (LLM-AGT-005) |
| Which agent version is live (legacy, Classic) | `ListAgentAliases` / `GetAgentAlias` resolved to the served version | `references/checks-agents.md` (LLM-AGT-007), `references/api-quirks.md` |
| Action group lambda is failing (legacy, Classic) | `GetAgentActionGroup` and the executor Lambda role scope | `references/checks-agents.md` (LLM-AGT-002, LLM-AGT-006) |
| Agent looks idle / is this still used (legacy, Classic) | `AWS/Bedrock/Agents` invocation metrics over the window | `references/checks-agents.md` (LLM-AGT-004), `references/metrics-and-logs.md` |
| We are still on Bedrock Agents Classic (legacy) | Whether any Classic agent exists in scope | `references/checks-agents.md` (LLM-AGT-011, advisory) |

## Procedure — Review an AgentCore Runtime (LLM-AC) — primary

Run these steps in order against the catalog `references/checks-agentcore.md`. The permission checks
depend on reading the runtime first, so do not skip ahead. If an AgentCore read is denied under the
default Agent Space role, that is a **disclosed permission gap**, not an absent resource (see Error
Handling and `api-quirks.md`).

- [ ] Step 1: Read the runtime with `bedrock-agentcore:ListAgentRuntimes` / `GetAgentRuntime` — status,
  version, endpoint, and the execution **role ARN** (mask the account segment when quoting it).
- [ ] Step 2: Check the runtime role for every action it exercises (`bedrock:InvokeModel*`, `s3:GetObject`
  for sources, `logs:CreateLogStream`/`PutLogEvents`, gateway target actions); any required action
  denied is **LLM-AC-001 (CRITICAL)**. `iam:SimulatePrincipalPolicy` is refused in the DevOps Agent
  runtime, so read the role's inline and attached policies (`ListRolePolicies`/`GetRolePolicy`,
  `ListAttachedRolePolicies`/`GetPolicyVersion`) and check each required action against them; report
  the result as "read from policy documents, not simulated". Use the simulation only where it runs. Count `bedrock:InvokeModel*` as
  required only for a runtime that calls a model (a model ID in its environment or configuration).
- [ ] Step 3: If a required action is denied, read effective SCPs
  (`organizations:ListPoliciesForTarget` / `DescribePolicy`) and correlate — an explicit SCP `Deny`
  overriding an otherwise-correct role is **LLM-AC-002**. When the denied caller uses temporary
  credentials from `AssumeRole`, also name the session policy as a cause to check: the session's
  permissions are the intersection of the role's policies and the session policy, so a role with admin
  access is still denied anything the session policy omits. The fix is in the code or auth system that
  calls `AssumeRole` (allow the needed actions in its session policy), not a broader role policy. Check
  the role's permissions boundary the same way.
- [ ] Step 4: For a VPC-deployed runtime, check required endpoints with `ec2:DescribeVpcEndpoints`
  (`bedrock-runtime`, `bedrock-agent-runtime`, S3 gateway, `logs`, `monitoring`); any absent is
  **LLM-AC-003**.
- [ ] Step 5: Check the gateway and its targets (`GetGateway` / `ListGateways`, `ListGatewayTargets` / `GetGatewayTarget`) for an
  unconfigured gateway or an invalid/failing target (LLM-AC-004), and for unrotated/long-lived target
  credentials (LLM-AC-008).
- [ ] Step 6: Check observability — OTLP/AgentCore Observability enabled with stage-level spans
  (LLM-AC-005, CRITICAL), trace-context propagation across hops (LLM-AC-006), and structured JSON logs
  (LLM-AC-007).
- [ ] Step 7: Check runtime version currency (LLM-AC-009) and session recording/replay (LLM-AC-010);
  both are `workload-specific`.
- [ ] Step 8: For throttling (429) or slowdown under load, name the throttling layer and the documented
  quota it hit before recommending anything (**LLM-AC-011**); same-session slowdown is shared session
  compute, not a network limit.
- [ ] Step 9: For lost context, memory branches, long-term records or Memory latency, name the Memory
  part involved (short-term events, branch, asynchronous extraction, service latency) with its evidence
  (**LLM-AC-012**); a stable session ID is not conversation storage.
- [ ] Step 10: For a Browser / Code Interpreter session or a console page that will not load, name which
  browser is involved and use that surface's own limits (**LLM-AC-013**); a page that loads elsewhere is client-side first.
- [ ] Step 11: For a caller in another account, check each action it needs in both its identity policy
  and the resource-based policy (runtime and endpoint) and name the missing allow (**LLM-AC-014**).
- [ ] Step 12: For every gap, record the check-id, severity, and the concrete observed value; assemble
  per the report template.

## Procedure — Review a Bedrock Agents Classic agent (LLM-AGT) — legacy, maintenance mode

**These checks apply to Bedrock Agents Classic, which is in maintenance mode** (closed to new customers,
no new features, no end-of-life date). The checks remain in force for existing customers. Run these steps
in order against the catalog `references/checks-agents.md`. Each step collects with a read-only API (see
`references/collection-reference.md`) and maps the observed state to a check-id. Do not conclude what
production runs until the alias is resolved (Step 2) — a prepared DRAFT is not what the alias serves.

- [ ] Step 1: Enumerate agents with `bedrock:ListAgents`; for each, `bedrock:GetAgent` to read
  `guardrailConfiguration`, `foundationModel`, `memoryConfiguration`, and prompt-override config.
- [ ] Step 2: Resolve each alias with `ListAgentAliases` / `GetAgentAlias` to the **version** it serves;
  treat that version — not the latest prepared DRAFT — as production behaviour (LLM-AGT-007). *(Alias /
  prepared-version concepts are Bedrock Agents Classic, maintenance mode.)*
- [ ] Step 3: Check the guardrail attachment — no `guardrailIdentifier`/`guardrailVersion` on a prod
  agent is **LLM-AGT-001 (CRITICAL)**. (Guardrail *strength* is out of scope; see *Related skills
  (optional)*.)
- [ ] Step 4: Inspect each action group (`ListAgentActionGroups` / `GetAgentActionGroup`); read the
  executor Lambda's role (`lambda:GetPolicy` / `iam:GetRolePolicy`) for over-broad scope
  (LLM-AGT-002); note Code Interpreter enablement and its surrounding controls (LLM-AGT-006). *(Action
  groups are a Bedrock Agents Classic concept, maintenance mode.)*
- [ ] Step 5: Check prompt management and versioning (`ListPrompts` / `GetPrompt`) — inline/in-place or
  DRAFT-referenced prompts are LLM-AGT-003; test-alias (`TSTALIASID`/DRAFT) use in prod is LLM-AGT-007.
- [ ] Step 6: Check agent-level tracing (LLM-AGT-005), model resilience via inference profile
  (LLM-AGT-008), memory / session TTL (LLM-AGT-009), and whether an idle agent has had zero
  `InvokeAgent` activity over the window (LLM-AGT-004) — distinguish "no datapoints" from a measured zero
  (`api-quirks.md` §10). *(Agent-level tracing is a Bedrock Agents Classic concept, maintenance mode.)*
- [ ] Step 7: Run the agent/end-to-end regression-evaluation check before any version promotion
  (LLM-AGT-010).
- [ ] Step 8: **Migration advisory — new and advisory.** If any Bedrock Agents Classic agent exists in
  scope, raise **LLM-AGT-011 (INFO/LOW)**: Classic is closed to new customers and receives no new
  features; recommend migrating via the **AgentCore harness** (config-based, closest analog) or
  **code-defined agents on AgentCore**, and point at the agent-toolkit migration skill ("Help me migrate
  my Bedrock Agent to AgentCore harness"). This is advisory, not an outage: a Classic agent that still
  works is **not** a reason to skip it.
- [ ] Step 9: For every gap, record the check-id, severity, and the concrete observed value; assemble
  per the report template.

## Before You Present — Validate Your Own Output

A finding with no evidence, or one that leaks sensitive material, is worse than no finding. Before you
present an agent/runtime review, re-check your own output against this list. Treat it as a gate, not a
suggestion.

- [ ] Every finding carries a matching `check-id` from `checks-agents.md` (LLM-AGT-###) or
  `checks-agentcore.md` (LLM-AC-###), and that id actually corresponds to what was observed.
- [ ] Every cited value was **actually observed, not inferred**. Distinguish "measured zero" from "no
  datapoints" (`references/api-quirks.md` §10), and `PREPARED` DRAFT from what the alias serves (§6).
- [ ] For any Bedrock Agent conclusion about production behaviour, the **alias was resolved to a
  version** first (LLM-AGT-007) — you did not report the DRAFT as production.
- [ ] No raw 12-digit AWS account ID appears anywhere, and every role/resource ARN has its account
  segment masked.
- [ ] No secret material is reproduced — no agent session content, no prompt-override text, no gateway
  tokens or credential values.
- [ ] Any AgentCore read that was **denied** (e.g. `bedrock-agentcore` not in the default role) is
  disclosed as a permission gap, not reported as an absent resource.
- [ ] Scope you did not cover (regions, resources, checks blocked by permissions) is stated explicitly.
- [ ] Every statement of *why* something happens is either backed by an AWS-doc citation or an observed
  value, or labelled as a hypothesis together with the read or test that would confirm or rule it out.
- [ ] Every LLM-AC-001 finding for a missing `bedrock:InvokeModel*` names the model ID found in that
  runtime's own environment or configuration. Drop the finding for a runtime with no model ID, even if
  it shares a role with one that has, and list it as not calling a model.
- [ ] When a full report is requested, the output follows `assets/agent-runtime-report-template.md`.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a mutating API. Recommend the fix; state the exact CLI/IaC change and let
   the user run it.
2. **Never echo a raw AWS account ID.** Never reproduce a raw 12-digit account ID. If an ARN must be
   quoted as evidence, mask the account segment
   (`arn:aws:iam::<account>:role/...`, `arn:aws:bedrock:us-east-1:<account>:agent/...`).
3. **Never disclose secret material.** Report env vars, keys, tokens, and connection strings by **key
   name only** — never the value, never a partial value. Specifically, **never reproduce agent session
   content, prompt-override text, or gateway tokens.**
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. If you did not
   observe a value, you do not report the finding.
5. **A check-id on every finding.** Each finding references a catalog `check-id` (LLM-AGT-### or
   LLM-AC-###) and carries that check's severity and AWS-doc citation. No freelance findings.
6. **Never invent a threshold.** Severities come from the catalogs. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which regions, resources, or checks you did
   not cover, and why (budget, permissions, region-unsupported feature).

8. **Hypothesis is not fact.** When the evidence does not establish the cause, say so. Do not call
   a mechanism "known", "documented" or "expected behaviour" unless you cite the AWS page that says it,
   and do not invent service internals, limits or quotas. List the likely causes as hypotheses, most
   likely first, each with the read-only check or isolation test that would confirm or rule it out
   (for example: a test target without auth to separate network from OAuth failures). If only AWS can
   see the cause (service-side logs, microVM internals), say that it needs a support case.

## Common wrong answers

- "This is a known, documented behaviour of the service." Without a cited AWS page or an observed value,
  this is a guess presented as fact. State it as a hypothesis with the check that would confirm it, and
  say plainly when the cause cannot be determined from what you can read.

- "`GetAgent` shows `PREPARED`, so that config is what production runs." An agent's live behaviour is its **alias → version** resolution, not the latest prepared DRAFT. Always resolve the alias to the version it serves before concluding what production runs (LLM-AGT-007).
- "Model invocation works, so the deploy-time credentials error is a client-side credential problem." `InvokeModel` needs `bedrock:` actions; creating or updating a runtime needs `bedrock-agentcore:` control-plane actions, `iam:PassRole` for the execution role, and (for the AgentCore CLI) CloudFormation, S3, ECR and CodeBuild. A role with `bedrock:*` but no `bedrock-agentcore:` grant can call models and still fail to deploy. Read the deploying identity's policies first; re-authenticating alone does not fix a missing grant. Add the scoped `bedrock-agentcore` actions (not `*`), then retry the deploy.
- "The AgentCore read returned AccessDenied, so no runtime exists." The standard `AIDevOpsAgentAccessPolicy` does **not** include the `bedrock-agentcore` namespace, so an AgentCore read that is denied is a **disclosed permission gap**, not an absent resource. Report "grant `bedrock-agentcore` read permissions separately (template parameter `EnableOpsaiBedrockAgentCore`)."
- "The Classic agent still works, so we can skip the migration advisory." Bedrock Agents Classic is in maintenance mode — closed to new customers, no new features. A still-working agent is **not** a reason to skip LLM-AGT-011; raise it anyway as advisory.
- "CloudWatch returned no datapoints, so the agent is idle — decommission it." No datapoints and a measured zero are different (`api-quirks.md` §10). Confirm a measured zero over the window before calling an agent abandoned (LLM-AGT-004).
- "There is a guardrail configured somewhere, so the agent is protected." This skill only checks that a guardrail **is attached** to the agent (LLM-AGT-001); strength is out of scope. An unattached guardrail protects nothing — for strength, follow *Related skills (optional)*.
- "I'll write the new AgentCore check against `bedrock-agentcore-control`." That namespace is being superseded by `agent-registry-control` for registry operations and is labelled "to be deprecated"; account for the newer namespace before adding checks.

## Severity Definitions

| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active production impact or total triage blindness | 24–48 hours |
| **HIGH** | Serious reliability/observability/security risk | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are operational guidance (derived), not AWS-published commitments.

## Error Handling

Before interpreting any response, consult `references/api-quirks.md` — it enumerates the misleading
responses that cause false positives and false negatives. Two traps are decisive for this skill:

- **An agent's LIVE behaviour is its alias→version resolution, NOT the latest prepared DRAFT**
  (`api-quirks.md` §6). `GetAgent` showing `agentStatus: PREPARED` does not mean the latest config is
  live — applications invoke an alias that maps to a specific published version. **Always resolve
  alias→version before concluding what production runs** (LLM-AGT-007). Reporting a freshly prepared
  DRAFT as production is a false positive.
- **The standard `AIDevOpsAgentAccessPolicy` does NOT include the `bedrock-agentcore` namespace.** Under
  the default Agent Space role, AgentCore reads (`GetAgentRuntime`, gateway reads, OTLP config
  inspection) may be **denied**. Report that as a **disclosed permission gap** — "AgentCore read denied;
  grant `bedrock-agentcore` read permissions separately (template parameter `EnableOpsaiBedrockAgentCore`)"
  — **not** as an absent runtime. Concluding "no
  runtime exists" from an access denial is a false negative.

Other quirks that matter here: **CloudWatch "no datapoints" ≠ zero** (§10) — an idle-agent conclusion
(LLM-AGT-004) must distinguish no traffic from a measured zero; **listed ≠ accessible** (§3).

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature**, record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate. On **ambiguous scope** (which agent? which region? AgentCore or Agents
Classic?), ask or default to the caller's current region and say so.

## Related skills (optional)

This skill works on its own and loads nothing outside its own `references/` and `assets/`. When a question
reaches into an area listed under *When NOT to Use*, read `references/related-skills.md` and:

1. If the skill named there is in your available skills, load it and use it for that part.
2. If it isn't, cover that part yourself with the fallback check in that file and general AWS knowledge.
   Label anything that comes from general knowledge, and give it no check-id: this skill's check-ids are
   only for checks this skill runs.
3. End the answer with one line recommending the missing skill and what it would add. Add it only when
   that skill would have changed the answer, and only once.

## Appendix — Reference Links
- [`references/router-details.md`](references/router-details.md): the full first-read method for the longer Router rows.
- [`references/runtime-sessions.md`](references/runtime-sessions.md): documented AgentCore session facts (microVMs, session headers, quotas, timeouts).

Catalogs and references under `references/`:

- `references/checks-agents.md` — LLM-AGT-001..010 Bedrock Agents / action-group checks (primary)
- `references/checks-agentcore.md` — LLM-AC-001..014 AgentCore runtime / gateway / memory / browser / cross-account / telemetry checks (primary)
- `references/collection-reference.md` — the exact read-only APIs per family and the fields they feed
- `references/metrics-and-logs.md` — CloudWatch metric set (incl. `AWS/Bedrock/Agents`) + log patterns
- `references/api-quirks.md` — misleading read-only API responses (alias→version §6, no-datapoints §10)

Output template under `assets/`:

- `assets/agent-runtime-report-template.md` — consolidated review output (scope, findings with
  check-ids and severities, remediation, disclosed gaps)

AWS documentation:

- [Bedrock Agents](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Agents and guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-guardrails.html)
- [Create an action group](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-action-create.html)
- [Deploy an agent (versions & aliases)](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-deploy.html)
- [Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Agentic AI Lens — observability (AGENTREL08-BP02)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel08-bp02.html)
