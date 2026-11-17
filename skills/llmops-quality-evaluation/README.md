# LLMOps Evaluation & Model Quality (AWS DevOps Agent Skill)

> ⚠️ **Non-Production Notice**: This skill is sample code, not intended for production use without additional review and testing. Validate in a non-production environment first, and review the IAM permissions below against your organization's policies before granting them.

This is one of **eight skills** for the `llmops-agent` custom agent — and the project's main differentiator. It owns Bedrock model evaluation, quality gates, and regression detection; this skill owns that **evaluation & model quality** slice, the LLMOps Continuous-Tuning pillar.

## What It Does

Assesses the evaluation discipline that distinguishes LLMOps from running a model and hoping: Bedrock model/RAG/human evaluation jobs, regression gates in CI/CD, promotion quality criteria, A/B model comparison, and whether any evaluation has ever been run. Also reasons about a finish-reason distribution shift (end_turn -> max_tokens) as an early regression signal.

Every assessment is grounded in the check catalogs under `references/`. Each check carries a stable `check-id`, a severity, a detection rule, a remediation, and its AWS documentation citation. The skill never invents a threshold: where AWS publishes no number, the catalog marks the check `workload-specific` and the finding is reported as `INFO`. The skill is **read-only** - it reports findings and the exact command or IaC change to fix them, and never mutates a resource.

Scope: Evaluation (`LLM-EVAL`). Catalog: `checks-evaluation.md` (LLM-EVAL-001..011, the finish-reason regression signal LLM-EVAL-012, the missing-metric-filter check LLM-EVAL-013, and the output-token precursor LLM-EVAL-014), plus the dedicated `finish-reason-analysis.md` reference.

> **Shared references.** The files under `references/` are **symlinks** into the parent `llmops/references/` directory, so updates to the originals propagate to this skill. When packaging for upload, the zip resolves the symlinks so the bundle is self-contained (see below).

## Prerequisites

- AWS DevOps Agent with an active Agent Space.

**If your Agent Space uses the default role, no extra permissions are needed.** The AWS managed policy [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html) already grants the CloudWatch, CloudWatch Logs, IAM read, and `ce:GetCostAndUsage` actions these skills use, and in most Agent Spaces the Bedrock and SageMaker read actions as well.

Confirm or add the following if your Agent Space uses a custom, narrower role - the GenAI control planes are the most likely gap under a hand-scoped policy. A denied call is not always a permissions problem: an Agent Space can return `NO_ELEVATED_ROLE_FOR_ACCOUNT` on a call the role is allowed to make, which is a platform restriction, not an IAM gap. The skill distinguishes the two.

### IAM permissions

```
bedrock:ListEvaluationJobs             bedrock:GetEvaluationJob
s3:ListObjectsV2                       s3:HeadObject
```

Every action is read-only. The skill never calls a mutating API.

## How to Install

Package the skill for upload. Zip **from inside the skill directory** so `SKILL.md` sits at the
archive root (the loader requires `SKILL.md` at the top level — a zip that nests everything under a
`llmops-quality-evaluation/` folder will not load). The `-r` recursion stores the symlinked `references/`
files as their resolved contents, so the uploaded bundle is self-contained:

```bash
cd skills/llmops-quality-evaluation && zip -r ../llmops-quality-evaluation.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

Then in the AWS Console:

1. Open your DevOps Agent Agent Space and go to **Skills**.
2. Upload `llmops-quality-evaluation.zip`.
3. **CRITICAL — set Agent Type to `All agents`.** The `llmops-agent` is a *custom* agent, and a skill
   uploaded for a specific built-in agent type will not be visible to it. Selecting **All agents** is
   what lets the custom `llmops-agent` load this skill. If you scope it to anything narrower, the
   custom agent silently will not see it.
4. Confirm the Agent Space role has the permissions listed above - especially the Bedrock read
   actions if the role is custom-scoped.

## Agent Types

All agents (`GENERIC`), so the [`llmops-agent`](../../custom-agents/llmops-agent/) custom agent can load it. Written for chat questions, incident RCA on a failed eval or quality drop, and scheduled quality-gate reviews.

## How to Use This Skill

```
"My evaluation job failed overnight"
"Model quality dropped - is this a regression?"
"How do I add a quality gate to model promotion?"
"Do we evaluate our models before shipping?"
"Set up an A/B comparison between two models"
"Our outputs are getting truncated - is this a max_tokens regression?"
```

## Role in an Investigation

Outside a live incident this skill leads: an advisory question about how to evaluate, or a standing
review of whether quality is measured and gated, is this skill's from the first turn.

Inside a live incident the DevOps Agent's investigation leads and `llmops-incident-triage` owns the
LLM-path triage within it. This skill is then loaded for **output-quality depth** and returns
`LLM-EVAL` findings rows — not a fault locus, not a root cause, and not the operator-facing answer.

**Hosting caveat.** The finish-reason checks (LLM-EVAL-012, -013, -014) read `stopReason` from
Bedrock model invocation logs. A SageMaker endpoint or a self-hosted model has no equivalent unless
the workload emits the field, so on those hostings the check is reported `not-applicable` with what
the workload would have to emit.


## Version History

See the `CHANGELOG.md` file in this directory.
