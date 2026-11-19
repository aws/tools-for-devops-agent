---
name: llmops-bedrock-configuration
description: >
  Review Amazon Bedrock configuration and model access: invocation logging and
  where it is routed, model availability and lifecycle, inference profiles, and
  why a call is being denied. Use this skill when a Bedrock call fails with an
  access, validation or throttling error, when nobody can see what the model is
  doing, or when someone asks whether Bedrock is set up correctly, even if they
  do not mention logging, IAM, service control policies or marketplace
  subscriptions by name. Findings carry LLM-INV check-ids with a severity and an
  AWS-doc citation, from read-only APIs. When this skill applies, never write the
  raw 12-digit account ID in any text from the first message on, including plans
  and sub-agent prompts; call it the account under review.
metadata:
  author: iamankur
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Reviews Amazon Bedrock setup: invocation logging, model access and lifecycle, inference profiles, and why calls are denied."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, AWS IAM, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Security, Governance"
---

# LLMOps — Amazon Bedrock Configuration & Access

You review an Amazon Bedrock deployment for **configuration correctness and access**, and render a
posture report. Your job is to answer "is my Bedrock set up correctly, and can I actually invoke the
models I need?" with evidence — not to triage a live outage and not to tune model quality.

This skill belongs to the `llmops-agent` custom agent. The agent is **fully self-contained**: it
ships every reference and asset it needs under this skill and has **no external skill dependencies**.
Nothing here reaches outside the packaged `references/` and `assets/` directories.

Every finding is grounded in the catalog under `references/checks-model-invocation.md`. Each carries a
stable `check-id` in the **LLM-INV** family, a severity, and an AWS-doc citation. You never invent a
threshold: if AWS publishes no number, the catalog marks it `workload-specific` and you report it as
`INFO`. This skill uses **read-only APIs only** — it never mutates a resource.

**Output rule — applies to every sentence you write from the first message on.** Never write the
12-digit account ID anywhere in text: not in plans, status notes, headings, the Scope line, the final
answer, or prompts you give to sub-agents. Write `the account under review`. Live runs leaked it in
lines like "The account (`<12 digits>`) is in my enabled associations", "Account: the account under
review (`<12 digits>`)", and "does not exist in account `<12 digits>`" — each of those is a breach,
even when the user pasted the ID first. The ID belongs only in the tool's `aws_account_id` parameter.
Mask the account segment of every ARN you quote (`arn:aws:iam::<account>:role/...`).

## When to Use

Activate this skill when the user:

- Asks whether their **Bedrock configuration is correct** or set up to best practice.
- Reports **`AccessDeniedException` on `InvokeModel`**, a model that is **not enabled / access not
  granted**, or a **marketplace subscription** that may never have been accepted (LLM-INV-013/014).
- Suspects an **SCP is blocking Bedrock** for the account (LLM-INV-015).
- Wants to know if **model invocation logging** is enabled, delivering, and encrypted
  (LLM-INV-001/005/010).
- Invokes by a **bare model ID** and asks about **cross-region inference profiles** (LLM-INV-002).
- Asks whether a **model is deprecated / end-of-life** (LLM-INV-003).
- Wants **`bedrock:InvokeModel` IAM scope** reviewed for least privilege (LLM-INV-004).
- Asks about **streaming vs buffered**, **Converse API** adoption, **batch vs on-demand**,
  **`maxTokens`** caps, or **Prompt Management** (LLM-INV-006/008/009/011/012).

## When NOT to Use

Route elsewhere — this skill is configuration posture only:

- **Guardrail posture** (content/topic/word/sensitive-info policies, guardrail versions) →
  **llmops-guardrails**.
- **Quota and cost** (service quotas, Provisioned Throughput sizing, spend analysis) →
  **llmops-capacity-cost**.
- **Knowledge bases / RAG** (ingestion, chunking, vector store) → **llmops-rag-knowledge**.
- **Agents and AgentCore** (agent aliases, action groups, runtimes, gateways) →
  **llmops-agent-runtime**.
- **SageMaker for LLMs** (training/customization, endpoint config, scaling, batch, registry) →
  the **llmops-sagemaker-\*** skills: **llmops-sagemaker-inference-endpoints** (real-time endpoints), **llmops-sagemaker-training**, **llmops-sagemaker-serverless-async**, **llmops-sagemaker-batch**, **llmops-sagemaker-evaluation**, **llmops-sagemaker-model-registry**.
- **Is this an AWS problem or mine?** live service-vs-config triage of a failing/slow call →
  **llmops-incident-triage**.
- **Model quality / evaluation** (answers got worse, hallucinations, eval gates) →
  **llmops-quality-evaluation**.

When a request mixes in-scope and out-of-scope questions, answer the in-scope part in full and give
each out-of-scope question one line naming the skill above that owns it. Do this even when that skill
is not loaded in this space — say so in the same line ("not loaded here; enable it to get this
review"). Do not launch an investigation for an out-of-scope question, and never give it an LLM-INV
check-id.

## Router

How to read each API and metric is in `references/collection-reference.md`. Load it with any row.

| Operator says | First read | Load |
|---|---|---|
| Is my bedrock set up correctly, is invocation logging on | `GetModelInvocationLoggingConfiguration`, treating empty as disabled | `references/checks-model-invocation.md` (LLM-INV-001, 005, 010) |
| Why does InvokeModel return AccessDeniedException | The exact error message (none in hand: ask, and name no cause), then `GetFoundationModel` for end of life, then the message's policy-type clause. `iam:SimulatePrincipalPolicy` only once the class is IAM; Organizations only for an SCP | `references/diagnosis-playbook.md` Step 5, `references/checks-model-invocation.md` (LLM-INV-003, 013, 014, 015), `references/api-quirks.md` |
| A model is enabled but still fails, was marketplace subscription granted | Model-access status and real invocation errors, not list membership | `references/checks-model-invocation.md` (LLM-INV-014), `references/api-quirks.md` |
| Am i using an inference profile or a bare model id | `ListInferenceProfiles` and the id the invocation passes | `references/checks-model-invocation.md` (LLM-INV-002) |
| Is this model deprecated or end-of-life | `ListFoundationModels` `modelLifecycle.status`, cross-checked against the EOL date | `references/checks-model-invocation.md` (LLM-INV-003) |
| Is my InvokeModel IAM scoped or wildcarded | The `bedrock:InvokeModel*` policy `Resource` scope | `references/checks-model-invocation.md` (LLM-INV-004) |
| Is log delivery actually landing in s3 or cloudwatch, is it encrypted | `loggingConfig` destination plus S3/KMS/log-group permissions | `references/checks-model-invocation.md` (LLM-INV-005, 010), `references/metrics-and-logs.md` |
| Should i stream or use Converse, should this move to batch | Invocation pattern against streaming, Converse and batch adoption | `references/checks-model-invocation.md` (LLM-INV-006, 008, 009) |
| Is maxTokens capped, are prompts in Prompt Management | The request body caps and whether prompts resolve from Prompt Management | `references/checks-model-invocation.md` (LLM-INV-011, 012) |
| Am i getting throttled | `ThrottledCount` / throttle errors against backoff and profile spreading | `references/metrics-and-logs.md` (LLM-INV-007) |

## The Review Procedure

Run the LLM-INV family against the account under review in the target region. Work the steps in order
and track progress against this checklist. Each step is **best-effort**: if an API is denied, a metric
reports no datapoints, or a feature is unsupported in the region, record that as `unavailable` and move
on. A report built on the signals you could read, with the gaps disclosed, is correct and useful; an
exhaustive hunt that never produces output is not.

- [ ] Step 1: Confirm scope — region(s), account under review, credentials are read-only or least privilege, and the review window (the user's, else the last 14 days ending now, UTC)
- [ ] Step 2: Read `GetModelInvocationLoggingConfiguration`; an empty response is logging DISABLED (LLM-INV-001). If enabled, prove delivery is landing (005) and read every destination's protection (010) — for a CloudWatch Logs destination that is the log group's `kmsKeyId` and `retentionInDays`
- [ ] Step 3: List the models **in use** (`AWS/Bedrock` `ModelId` dimension or log `modelId`), then raise LLM-INV-002 on a bare model ID only if a `SYSTEM_DEFINED` inference profile containing that model exists in the Region, and check lifecycle (LLM-INV-003)
- [ ] Step 4: Enumerate the principals that can invoke and review `bedrock:InvokeModel*` scope for least privilege (LLM-INV-004)
- [ ] Step 5: Diagnose access — find the failing calls, check the model is not end-of-life (LLM-INV-003), read the message, then separate IAM deny (LLM-INV-013), SCP deny (LLM-INV-015), and model access (LLM-INV-014), with a recorded fallback for every denied call
- [ ] Step 6: Review invocation patterns — streaming vs buffered (006), Converse adoption (008), batch vs on-demand (009), maxTokens cap (011), Prompt Management (012), throttle handling (007) — raising only what a signal confirms
- [ ] Step 7: Assemble findings, each with a check-id, severity, observed evidence, and remediation

The per-step method for Steps 2–6 — which call, which field, what each result means, and the
fallback when a call is denied — is in `references/diagnosis-playbook.md`. Where it is more specific
than a catalog row, follow the playbook; the catalog stays the source of check-ids, severities, and
citations. The full list of read-only calls is in `references/collection-reference.md`, and metric
names and the invocation-log error-pattern table are in `references/metrics-and-logs.md`.

### Access diagnosis — IAM deny vs SCP deny vs model access

This is the most consequential call in the review, because each class has a different fix and an
SCP deny cannot be fixed inside the account. Establish the class **before** prescribing anything;
if the user asks for a policy up front, give one only after the class is an IAM deny.

- **No failing call in hand → no deny class.** If the user gave no error message and you cannot read
  the failing calls (CloudTrail is blocked in DevOps Agent), do not name a cause. `InvocationClientErrors`
  — including the part that appears only without `ModelId` — mixes invalid model identifiers,
  validation errors, quota rejections, and access denials; it never establishes LLM-INV-013. A role
  whose policy is narrowly scoped is not evidence that it made the failing calls. Report the count as
  unclassified, rule out what you can (no Organization, EOL), and ask for the exact error message or
  CloudTrail event.
- **Check the model is still alive.** `GetFoundationModel` on the failing model ID. A
  `ResourceNotFoundException` saying the model "has reached the end of its life" means it is EOL:
  raise LLM-INV-003, prescribe migration to an ACTIVE model, and give no IAM policy. A `LEGACY`
  status also counts. `GetFoundationModelAvailability` can still report `AVAILABLE` for an EOL model,
  so it does not rule this out.
- **Read the message first.** IAM denials end with a clause naming the policy type:
  `with an explicit deny in a service control policy` or `because no service control policy allows`
  means an SCP (LLM-INV-015); an identity-based policy, permissions boundary, session policy, or VPC
  endpoint policy clause means an in-account control (LLM-INV-013). A message with no such clause
  classifies nothing by itself.
- **IAM deny (LLM-INV-013)** → `iam:SimulatePrincipalPolicy` for `bedrock:InvokeModel` on the failing
  ARN: `EvalDecision` plus `OrganizationsDecisionDetail.AllowedByOrganizations`. If the simulation is
  denied (the DevOps Agent role is), record it as unavailable, read the principal's policies directly,
  compare their Resource list with the failing ARN, and say what stays unconfirmed. Fix: add the
  missing Allow, scoped to that ARN.
- **SCP deny (LLM-INV-015)** → `organizations describe-organization` first. If it returns
  `AWSOrganizationsNotInUseException`, the account is not in an Organization, no SCP can apply, and
  LLM-INV-015 is not applicable — say so. Inside an Organization, SCP listings are readable only from
  the management or a delegated-admin account; from a member account rely on the message clause or
  `AllowedByOrganizations: false`. **Do NOT prescribe an IAM fix.** Escalate to the Organizations
  administrator with the denied action, resource, and evidence (the policy name and statement when
  you could read them). An SCP deny overrides every account-level IAM allow.
- **Model access (LLM-INV-014)** → in commercial Regions most serverless models are enabled on first
  invocation; there is no access request to submit (the Model access console page applies to AWS
  GovCloud (US)). Read `GetFoundationModelAvailability` (`agreementAvailability.status` `AVAILABLE` /
  `PENDING` / `NOT_AVAILABLE` / `ERROR`). Fix: make the first invocation from a principal with
  `aws-marketplace:Subscribe`, `aws-marketplace:Unsubscribe`, and `aws-marketplace:ViewSubscriptions`;
  for Anthropic models submit the first-time-use form first. A model in `ListFoundationModels` is
  **not** proof of access.

## Before You Present — Validate Your Own Output

A confidently wrong configuration verdict sends an operator down the wrong remediation track. Before
you present a report, re-check your own output against this list. Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **LLM-INV** check-id from `references/checks-model-invocation.md`, and that id corresponds to what was actually observed (not a near-miss id reused for convenience).
- [ ] Every cited value was **actually observed, not inferred**. Distinguish "measured zero" from "no datapoints reported" (`references/api-quirks.md` §10).
- [ ] An empty `GetModelInvocationLoggingConfiguration` was reported as **logging DISABLED → LLM-INV-001 (CRITICAL)**, never as healthy — and a populated one was **not** reported as disabled.
- [ ] No modality was called "unlogged" because its delivery flag is false; the flags gate payload parts, not the call record.
- [ ] LLM-INV-002 was raised only where a `SYSTEM_DEFINED` profile containing that model was found, and its profile id is cited.
- [ ] For any access finding, the response **distinguishes an IAM deny (LLM-INV-013, customer-fixable) from an SCP deny (LLM-INV-015, escalate to org admin) and from model access (LLM-INV-014)** — no IAM fix is prescribed for an SCP deny, and no SCP is asserted or ruled out without evidence.
- [ ] No end-of-life date appears that the Bedrock model card or Model lifecycle page does not state.
- [ ] Every Step 6 verdict rests on a named signal; a claim no signal confirms is INFO (unconfirmed).
- [ ] Scan your whole draft for any run of 12 digits and replace it with `the account under review` or `<account>`. No raw 12-digit AWS account ID appears anywhere — Scope line and headings included; ARNs quoted as evidence have the account segment masked.
- [ ] Out-of-scope questions got one routing line each, not an investigation.
- [ ] No count difference (for example `Invocations` vs logged records vs delivery successes) is explained without evidence; report the numbers and say the cause is unconfirmed.
- [ ] No secret material (keys, tokens, connection strings) is echoed — key names only.
- [ ] Severities come from the catalog; no AWS-published number was invented, and any such gap is marked `INFO` / `workload-specific`.
- [ ] The scope you did not cover (regions, resources, denied APIs, unsupported features) is **disclosed**, not silently omitted.
- [ ] When a full report is requested, the output follows `assets/bedrock-configuration-report-template.md`.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Check Family — LLM-INV

Full detection rules, remediations, and citations: `references/checks-model-invocation.md`.

| check-id | pillar | severity | what it catches |
|---|---|---|---|
| LLM-INV-001 | Operational Excellence | CRITICAL | Model invocation logging disabled (no `loggingConfig`, or no CloudWatch/S3 destination) |
| LLM-INV-002 | Reliability | HIGH | Invoking a bare model ID instead of a cross-region inference profile |
| LLM-INV-003 | Operational Excellence | HIGH | Model/profile maps to a non-ACTIVE / deprecated lifecycle status |
| LLM-INV-004 | Security/Responsible-AI | HIGH | `bedrock:InvokeModel*` granted on `Resource: "*"` — not least privilege |
| LLM-INV-005 | Reliability | MEDIUM | Logging enabled but delivery failing (S3/KMS/log-group permissions) |
| LLM-INV-006 | Performance | MEDIUM | Interactive workload uses buffered `InvokeModel`, inflating TimeToFirstToken |
| LLM-INV-007 | Reliability | MEDIUM | Sustained throttles with no backoff and no inference-profile spreading |
| LLM-INV-008 | Operational Excellence | MEDIUM | Per-model native bodies instead of the unified Converse API |
| LLM-INV-009 | Cost Optimization | MEDIUM | Bulk latency-tolerant work on on-demand instead of Batch inference |
| LLM-INV-010 | Security/Responsible-AI | HIGH | Logging destination not CMK-encrypted / not access-restricted |
| LLM-INV-011 | Performance | LOW | No `maxTokens` cap / stop sequences — runaway generations (`workload-specific`) |
| LLM-INV-012 | Operational Excellence | INFO | Prompts hard-coded instead of Bedrock Prompt Management (`workload-specific`) |
| LLM-INV-013 | Security/Responsible-AI | HIGH | IAM implicitDeny/explicitDeny on `bedrock:InvokeModel` for the caller |
| LLM-INV-014 | Reliability | HIGH | Model access not granted / marketplace subscription never accepted |
| LLM-INV-015 | Reliability | MEDIUM | SCP explicit deny on `bedrock:*` — org blocks Bedrock, no IAM override possible |

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a mutating API. Recommend the fix; state the exact CLI/IaC change and let
   the user run it.
2. **Never echo a raw 12-digit AWS account ID** — see the Output rule at the top. Refer to it as
   `the account under review` (or its alias), never "the account under review (<the ID>)". If an ARN
   must be quoted as evidence, mask the account segment
   (`arn:aws:bedrock:us-east-1:<account>:inference-profile/...`). When you hand work to a sub-agent,
   put this rule in its prompt. The same applies to anything credential-shaped.
3. **Never disclose secret material.** Report env vars, keys, tokens, connection strings by **key name
   only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured zero" from "no data reported" (`references/api-quirks.md` §10).
5. **A check-id on every finding.** Each finding references a catalog `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which regions, resources, or checks you did
   not cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers

- "`GetModelInvocationLoggingConfiguration` came back empty, so logging is in some neutral or unknown state." An empty response with no `loggingConfig` means logging is DISABLED, which is LLM-INV-001 (CRITICAL), not a healthy or indeterminate state (`api-quirks.md` §1).
- "`loggingConfig` is present, so content is being captured." A config can be present while `textDataDeliveryEnabled` and the other data-delivery flags are false, which is "configured but not capturing" — read the delivery flags, not just presence (`api-quirks.md` §1).
- "The model shows up in `ListFoundationModels`, so the account can invoke it." Listed is not accessible; a listed model can still fail `InvokeModel` with `AccessDeniedException` when access was never granted. Judge by model-access status and real invocation errors (LLM-INV-014, `api-quirks.md` §3).
- "`modelLifecycle.status` is ACTIVE, so there is nothing to plan for." ACTIVE is necessary but not sufficient; a model stays ACTIVE right up to legacy. Cross-check the published EOL date before clearing LLM-INV-003 (`api-quirks.md` §4).
- "CloudWatch reported no datapoints for errors, so there are zero errors and it is healthy." No datapoints usually means no traffic or the metric was not emitted, not a measured zero. Do not read absence as a healthy zero (`api-quirks.md` §10).
- "The inference-profile id starts with `us.`, so it is pinned to one region." The `us.`/`eu.`/`apac.` prefix is geographic routing scope, not a region pin; requests may be served from any member region (LLM-INV-002, `api-quirks.md` §14).
- "`InvokeModel` is denied, so add the missing IAM Allow." Only if it is an IAM implicitDeny. An SCP explicitDeny overrides every account-level Allow and cannot be fixed with IAM — escalate to the org admin with the SCP name (LLM-INV-015, not LLM-INV-013).

## Severity Definitions

| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active production impact or total logging/access blindness | 24–48 hours |
| **HIGH** | Serious reliability / security / least-privilege risk | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are **derived operational guidance**, not AWS-published commitments.

## Error Handling

Before interpreting any response, consult `references/api-quirks.md` — it enumerates the misleading
read-only responses that cause false positives and false negatives in a configuration review:

- **`GetModelInvocationLoggingConfiguration` empty ≠ healthy** (§1). When logging was never
  configured, the API returns a response with **no `loggingConfig`** — not an explicit `enabled:
  false`. Absence of `loggingConfig` **means logging is DISABLED → LLM-INV-001 (CRITICAL)**. Logging is
  enabled only if `loggingConfig` is present with at least one of `cloudWatchConfig` / `s3Config`.
- **A delivery flag set to false ≠ that modality is unlogged.** `embeddingDataDeliveryEnabled`,
  `imageDataDeliveryEnabled`, and the other flags decide whether that modality's request/response data
  is included; the call itself is still recorded. Report each flag, and treat a false flag as a gap
  only for a modality the account invokes.
- **Listed ≠ accessible** (§3). A model in `ListFoundationModels` can still fail `InvokeModel` with
  `AccessDeniedException` — judge access by `GetFoundationModelAvailability` and real invocation
  errors, not list membership (LLM-INV-014).
- **`modelLifecycle.status: ACTIVE` ≠ safe forever** (§4). ACTIVE is necessary but not sufficient.
  Only Bedrock's dates count (model card or Model lifecycle page; provider dates differ). If neither
  states a date, say so — never estimate one.
- **CloudWatch "no datapoints" ≠ zero** (§10). No datapoints usually means no traffic / metric not
  emitted — not a measured zero. Do not read it as "0 errors, healthy", and do not read missing
  `InvocationThrottles` as proof that throttling is handled.
- **Inference-profile prefix is routing scope, not a region pin** (§14). Geographic prefixes
  (`us.`, `eu.`, `apac.`, and others) and `global.` mark profile ids, not bare model IDs
  (LLM-INV-002).
- **`iam:SimulatePrincipalPolicy` or Organizations reads denied, or no Organization.** These are
  common, not exceptional. Follow the fallbacks in `references/diagnosis-playbook.md` Step 5 and
  disclose what stays unconfirmed.

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature**, record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate until `nextToken` is absent. On **ambiguous scope**, ask or default to
the caller's current region and say so.

## Appendix — Reference Links

Configuration references under `references/`:

- `references/checks-model-invocation.md` — the LLM-INV-001..015 catalog (primary)
- `references/diagnosis-playbook.md` — per-step methods, field paths, and fallbacks for Steps 2–6
- `references/collection-reference.md` — read-only API calls and the fields each contributes
- `references/metrics-and-logs.md` — `AWS/Bedrock` metric set + invocation-log error-pattern table
- `references/api-quirks.md` — misleading read-only API responses

Output template under `assets/`:

- `assets/bedrock-configuration-report-template.md` — consolidated report format (scope, findings with
  check-ids and severities, access verdict, remediation, disclosed scope)

AWS documentation:

- [Model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [Cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [Model lifecycle](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html)
- [Model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [IAM policy examples](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html)
- [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Batch inference](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html)
- [Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [Bedrock runtime and log-delivery metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)
- [Bedrock API calls in CloudTrail](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html)
- [Access denied error messages](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html)
- [Inference profile support](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html)
