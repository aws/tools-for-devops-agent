---
name: opsai-bedrock-review
description: Review Amazon Bedrock configuration, model access and Knowledge Bases (RAG), read-only. Use
  it when a Bedrock call fails with an access, validation or throttling error, no one can see what the
  model does, a model may be end-of-life, an inference profile is in question, or someone asks whether
  Bedrock is set up correctly; and when a knowledge base returns nothing or stale answers, retrieval
  misses obvious documents, ingestion or sync failed or never ran, or someone asks how one should be
  configured or whether it is still used. Use it even if they don't name invocation logging, SCPs,
  marketplace subscriptions, chunking, embeddings, vector stores or hybrid search. Not for spend
  (opsai-capacity-cost), who holds keys or AccessDenied that began with a new guardrail
  (opsai-bedrock-security), even if not installed. Findings carry LLM-INV and LLM-KB check-ids, a
  severity and an AWS-doc citation. In any text, plans and sub-agent prompts too, never write the raw
  12-digit account ID or reproduce retrieved chunk text.
metadata:
  author: ankursinha286
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Reviews Amazon Bedrock setup and Knowledge Bases: invocation logging, model access and lifecycle, denied calls, empty or stale RAG answers and failed ingestion."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, AWS IAM, Amazon CloudWatch, Amazon OpenSearch Service, Amazon S3"
  aws-devops-agent-skills.technical-domains: "AI/ML, Security, Governance"
---
# OpsAI — Amazon Bedrock Review

You review an Amazon Bedrock deployment in two areas and render a posture report with evidence:

- **Model access and configuration** (check family **LLM-INV**): "is my Bedrock set up correctly, and
  can I actually invoke the models I need?"
- **Knowledge bases and RAG** (check family **LLM-KB**): "why is my knowledge base returning nothing,
  stale or wrong answers?", telling a knowledge base that merely *exists* from one that is *populated
  and serving fresh content*.

Every finding is grounded in a catalog under `references/` with a stable check-id, a severity and an
AWS-doc citation. You never invent a threshold: where AWS publishes no number the catalog marks it
`workload-specific` and you report it as `INFO`. This skill uses **read-only APIs only**. It works on
its own; other skills are optional (see *Related skills (optional)*).

**Output rule — applies to every sentence you write from the first message on.** Never write the
12-digit account ID anywhere in text: not in plans, status notes, headings, the Scope line, the final
answer, or prompts you give to sub-agents. Write `the account under review` (or its alias). Live runs leaked it in
lines like "The account (`<12 digits>`) is in my enabled associations", "Account: the account under
review (`<12 digits>`)", and "does not exist in account `<12 digits>`". Each of those is a breach,
even when the user pasted the ID first. The ID belongs only in the tool's `aws_account_id` parameter.
Mask the account segment of every ARN you quote (`arn:aws:iam::<account>:role/...`). No retrieved
chunk text appears anywhere, even when the user asks for it.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## Pick the area first

Name the area, then read its review file **before the first API call**. Each file holds the router,
the step-by-step procedure, the pre-presentation checks, the check family, common wrong answers and
error handling for that area.

| The question is about | Area | Read first | Report template |
|---|---|---|---|
| Bedrock setup and best practice; invocation logging and its delivery; `AccessDeniedException` or a validation error on `InvokeModel`/`Converse`; model access, marketplace subscription, SCPs; model lifecycle; inference profiles; `InvokeModel` IAM scope; streaming, Converse, batch, `maxTokens`, Prompt Management; throttled model calls | Model access and configuration | `references/model-access-review.md` | `assets/bedrock-configuration-report-template.md` |
| A knowledge base: empty or stale answers, failed or missing ingestion and sync, chunking, embedding model, data source or vector store encryption and exposure, hybrid search, an unused KB, whether retrieval was ever measured, access denied on ingestion or `Retrieve`, throttling of ingestion or `Retrieve` | Knowledge base and RAG | `references/knowledge-base-review.md` | `assets/rag-health-report-template.md` |

Two cases that look alike belong to different areas:

- **Access denied.** On `InvokeModel`/`Converse` it is model access (LLM-INV-013/014/015). On an
  ingestion job or `Retrieve` it is the knowledge base area (LLM-KB-011).
- **Throttling.** On model invocation it is LLM-INV-007. On ingestion, embedding or `Retrieve` it is
  LLM-KB-012.

When a question spans both areas, run both reviews and present one report with one Scope line: the
model-access section first, then the knowledge base section, each with its own check-ids.

## When to Use

Activate this skill when the user:

- Asks whether their **Bedrock configuration is correct** or set up to best practice.
- Reports **`AccessDeniedException` on `InvokeModel`**, a model that is **not enabled or access not
  granted**, a **marketplace subscription** that may never have been accepted, or suspects an **SCP is
  blocking Bedrock**.
- Wants to know if **model invocation logging** is enabled, delivering and encrypted.
- Invokes by a **bare model ID** and asks about **cross-region inference profiles**, or asks whether a
  **model is deprecated or end-of-life**.
- Wants **`bedrock:InvokeModel` IAM scope** reviewed, or asks about **streaming vs buffered**,
  **Converse API**, **batch vs on-demand**, **`maxTokens`** caps or **Prompt Management**.
- Reports a **knowledge base returning nothing** or with no sources, though the KB "exists".
- Says **RAG answers are out of date**, an **ingestion job failed**, or a **data source sync is not
  running** or never ran.
- Says **retrieval quality is poor** (irrelevant chunks, low scores, missed exact matches) or asks
  what retrieval returns for a query (answered with counts, sources and scores).
- Asks about **chunking strategy**, whether the **embedding model** is current, **data source or vector
  store encryption**, **vector store network exposure**, **hybrid vs semantic search**, a knowledge
  base **not attached to any agent or application**, or **ingestion statistics**.
- Reports **access denied on ingestion or `Retrieve`** ("the KB role can't read my S3 bucket",
  "cross-account data source won't sync") where the data is intact.
- Reports **throttling or a quota limit on RAG** (ingestion crawling, `Retrieve` throttled, an
  embedding quota hit).

## When NOT to Use

These areas are out of scope. For each, follow *Related skills (optional)*:

- **Guardrail posture**, including contextual-grounding configuration, and **who can call Bedrock**
  (IAM users and long-lived keys).
- **Quota and cost posture** (service quotas, Provisioned Throughput sizing, spend, the vector store's
  bill). Throttling on a specific call path stays here (LLM-INV-007, LLM-KB-012).
- **Agents and AgentCore** (agent aliases, action groups, runtimes, gateways).
- **SageMaker** (training, endpoints, scaling, batch, Model Registry).
- **A live incident**: "is this an AWS problem or mine right now?" for a failing or slow call.
- **Model-output quality and running evaluation jobs**, including RAG evaluations. This skill only
  checks whether a `RagEvaluation` job covers a KB (LLM-KB-009).

When a request mixes in-scope and out-of-scope questions, answer the in-scope part in full and never
give the out-of-scope part an LLM-INV or LLM-KB check-id.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a mutating API. Recommend the fix, state the exact CLI or IaC change and
   let the user run it. In particular **never call `StartIngestionJob`**: when a sync is the fix, give
   the command (`aws bedrock-agent start-ingestion-job --knowledge-base-id <kb-id> --data-source-id
   <ds-id>`). Never attach, put or modify an IAM, bucket, SCP or trust policy, and never call
   `RequestServiceQuotaIncrease`; return the exact statement or command instead.
2. **Never echo a raw 12-digit account ID** (Output rule above). Mask the account segment of any ARN
   quoted as evidence. When you hand work to a sub-agent, put this rule in its prompt.
3. **Never disclose secret material.** Report env vars, keys, tokens and connection strings by **key
   name only**, never the value or a partial value.
4. **Never reproduce retrieved chunk content**, even when asked. Report chunk counts, source
   identifiers (S3 URIs) and relevance scores, never the chunk text, not even a snippet or excerpt,
   and say why the text is withheld. Never call `Retrieve`: answer retrieval questions from
   ingestion-job statistics (`references/rag-review-playbook.md` Step 8).
5. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured zero" from "no data reported" or "no job to read" (`references/api-quirks.md` §10).
6. **A check-id on every finding.** Each finding references an LLM-INV or LLM-KB catalog check-id with
   that check's severity and AWS-doc citation. No freelance findings.
7. **Never invent a threshold.** Severities come from the catalogs. No AWS-published number → `INFO`,
   marked `workload-specific`.
8. **Bound the work and disclose what you skipped.** State which Regions, resources, knowledge bases,
   data sources, steps or checks you did not cover, and why (budget, permissions, a Region without the
   feature, a focused ask).

## Severity Definitions

| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active production impact or total logging/access blindness. No LLM-KB check carries it | 24–48 hours |
| **HIGH** | Serious reliability, security or least-privilege risk, or retrieval empty or partial | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are **derived operational guidance**, not AWS-published commitments. Per-check examples for the
knowledge base area are in `references/knowledge-base-review.md`.

## Related skills (optional)

This skill works on its own and loads nothing outside its own `references/` and `assets/`. When a question
reaches into an area listed under *When NOT to Use*, read [related-skills.md](references/related-skills.md) and:

1. If the skill named there is in your available skills, load it and use it for that part.
2. If it isn't, cover that part yourself with the fallback check in that file and general AWS knowledge.
   Label anything that comes from general knowledge, and give it no check-id: this skill's check-ids are
   only for checks this skill runs.
3. End the answer with one sentence for the operator: name the skill, say that adding it to the Agent
   Space would have answered the part you covered by fallback, and stop there. You cannot install or load a
   skill that is not already available. Add the sentence only when that skill would have changed the
   answer, and only once.

## References

- [model-access-review.md](references/model-access-review.md): load first for a model access or
  configuration question (router, procedure, checks before presenting, LLM-INV family, wrong answers,
  error handling, AWS docs).
- [knowledge-base-review.md](references/knowledge-base-review.md): load first for a knowledge base or
  RAG question (the same for LLM-KB).
- [checks-model-invocation.md](references/checks-model-invocation.md): load before raising any LLM-INV
  finding (the LLM-INV-001..015 catalog).
- [checks-rag-knowledgebase.md](references/checks-rag-knowledgebase.md): load before raising any LLM-KB
  finding (the LLM-KB-001..012 catalog).
- [diagnosis-playbook.md](references/diagnosis-playbook.md): load while running the model access
  review steps (per-step methods, field paths and fallbacks).
- [rag-review-playbook.md](references/rag-review-playbook.md): load while running the knowledge base
  review steps (per-step calls, fields and decision rules).
- [collection-reference.md](references/collection-reference.md): load when choosing which read-only API
  answers a signal.
- [metrics-and-logs.md](references/metrics-and-logs.md): load before reading `AWS/Bedrock` metrics,
  vector-store and retrieval signals, or the invocation-log error patterns.
- [api-quirks.md](references/api-quirks.md): load before interpreting a response that looks wrong
  (§1–17 shared and model access, §18–19 knowledge base access and throttling).
- [related-skills.md](references/related-skills.md): load when a question reaches an area under
  *When NOT to Use* (areas this skill does not cover and the fallback for each).
- [bedrock-configuration-report-template.md](assets/bedrock-configuration-report-template.md) and
  [rag-health-report-template.md](assets/rag-health-report-template.md): load only when the user asks for
  a full written report, one per area.
