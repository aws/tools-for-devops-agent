# IAM Access Navigator — AWS DevOps Agent Skill

A reasoning skill for **IAM identity risk**. It looks at an account's IAM
identities and tells you what is risky and in what order, what is safe to change,
what each identity should actually be allowed to do — hands you the artifact to
make the change — and, when something breaks or was changed out of band, works
backwards to explain and reverse it. It teaches as it works.

> **This skill is sample code, not intended for production use without
> additional review and testing. Validate it in a non-production environment
> first.**

## What it does

Activated in Chat, the skill guides the agent to reason through eight
capabilities, all **read-only / advisory** — it diagnoses and produces the change
for a human to apply, and never calls a mutating IAM/STS API:

1. **Risk triage + prioritization** — what's risky, in what order to fix it.
2. **Blast-radius / change-safety** — what breaks if you change or delete an
   identity (trust relationships, dependents, deletion impact).
3. **Least-privilege synthesis** — what a role should be allowed to do, derived
   from observed CloudTrail activity.
4. **Educational / conversational teaching** — explains the *why* with attack
   chains and analogies, offers a guided tour, and states its coverage honestly.
   This is the differentiator, and it is encoded as behavior in `SKILL.md`, not
   as UI.
5. **Identity hygiene / key lifecycle** — access-key classification, age/idle
   flags, and safe deactivate→monitor→delete migration paths.
6. **Policy validation** — Access Analyzer `ValidatePolicy` plus dangerous-action
   and missing-condition checks.
7. **Rollback reasoning** — pre-change snapshot, reversal steps, and trigger
   conditions for any medium+ blast-radius change.
8. **Forensics / backwards-troubleshooting** — reconstruct an out-of-band IAM
   change from CloudTrail and correlate it to a symptom (`AccessDenied`,
   `UnauthorizedOperation`, failed `AssumeRole`), with an explicit confidence
   level. *(Ambitious capability; see "Known limits" below.)*

## Agent types

Targets `CHAT` (on-demand conversational use) and `PREVENTION` (proactive
evaluations and recommendations), set in `metadata.aws-devops-agent-skills.agent-types`.
Select **Generic** at upload time to make it available to all agent types.

## How it works

This is a **control-plane** skill. It reasons from **IAM and CloudTrail** — the
primitives every account has — via the DevOps Agent's built-in `use_aws` tool
(describe/list/get/lookup), with no custom tools and no data-plane access. It
does **not** require IAM Access Analyzer analyzers or Security Hub to be
configured; it derives its own findings. The reasoning, heuristics, thresholds,
and honesty rules live in `SKILL.md` and `references/`.

## Prerequisites

An AWS DevOps Agent Space with the target account configured as a cloud source.
The Agent Space's IAM role needs the read-only permissions below. Do not assume
an AWS managed DevOps Agent policy covers them: as checked on 2026-11-03,
neither `AIDevOpsAgentAccessPolicy` (v12) nor `AIDevOpsAgentReadOnlyAccess` (v2)
grants `iam:ListAccessKeys` or `iam:GetAccessKeyLastUsed`, and the read-only
policy does not grant `cloudtrail:LookupEvents`. Attach a policy with these
actions to the Space's role.

**Required (the skill's baseline):**

- `iam:Get*`, `iam:List*`, `iam:GenerateServiceLastAccessedDetails` /
  `iam:GetServiceLastAccessedDetails`
  - Access-key hygiene specifically needs `iam:ListAccessKeys` and
    `iam:GetAccessKeyLastUsed` (both covered by the wildcards above). Without
    them the skill reports which one was denied and does not report keys as
    clean.
- `cloudtrail:LookupEvents`
- `sts:GetCallerIdentity`
- `access-analyzer:ValidatePolicy`, `access-analyzer:CheckAccessNotGranted` —
  on-demand policy-validation APIs. These need **no analyzer configured** and no
  Security Hub; they're a stateless call, used only by the policy-validation
  capability.

**Optional (enrichment only — the skill works fully without them):**

- `access-analyzer:ListAnalyzers`, `access-analyzer:ListFindings`,
  `access-analyzer:GetFinding` — if the account already runs Access Analyzer,
  its external-access and unused-access findings corroborate the skill's own
  analysis.
- `securityhub:GetFindings` — if Security Hub is on, its IAM-related findings add
  severity context.

The skill degrades honestly when a permission or data source is missing — it
reports what it checked rather than guessing (see "The coverage contract" in
`SKILL.md`). The absence of Access Analyzer or Security Hub is **not** treated as
a gap, and the skill never tells the user to enable a service.

## Usage

In DevOps Agent Chat, natural language:

- *"Audit my IAM and tell me what to fix first."*
- *"Is it safe to delete the `payments-batch` role? What depends on it?"*
- *"Generate a least-privilege policy for `analytics-runner` from the last 90
  days."*
- *"Review my access keys for hygiene issues."*
- *"Validate this policy: { … }"*
- *"Why did `report-generator` start getting AccessDenied yesterday? What
  changed?"*
- *"Walk me through an IAM security review."* (guided, teaching tour)

## Skill contents

```
iam-access-navigator/
├── SKILL.md                          # frontmatter + reasoning behavior (required)
├── README.md                         # this file
├── CHANGELOG.md                      # version history
├── references/
│   ├── risk-scoring.md               # triage/prioritization models
│   ├── blast-radius.md               # change-safety / dependency reasoning
│   ├── least-privilege.md            # synthesis + the CloudTrail nuances
│   ├── policy-validation.md          # validation layers and verdict
│   ├── key-hygiene.md                # key classification + migration ladder
│   ├── rollback.md                   # snapshot / reversal / triggers
│   ├── forensics.md                  # backwards-troubleshooting + confidence rubric
│   └── educational-behavior.md       # the teaching persona and tone guardrails
└── evals/                            # evaluation data (not part of the upload zip)
```

## Packaging for upload

From the `skills/` directory:

```bash
zip -r iam-access-navigator.zip iam-access-navigator/ -i '*.md' -x '*/README.md' '*/CHANGELOG.md' '*/evals/*'
```

`SKILL.md` and `references/` are what the agent needs at runtime. `README.md`,
`CHANGELOG.md`, and `evals/` are repository/documentation artifacts and are
excluded from the runtime zip. Total zip must be ≤ 6 MB; a `scripts/` directory
is not allowed.

## Skill vs MCP server

v1 is **skill-only**. Every capability except deep forensics is control-plane
reasoning over `use_aws`, which needs no MCP server. The one capability that
could outgrow a skill is **forensics over a long horizon or high event volume**:
CloudTrail `LookupEvents` covers roughly the last 90 days page-by-page, which is
fine for recent incidents but not for bulk historical reconstruction. That
workload — CloudTrail Lake or Athena over an S3 trail, queried in bulk — is where
a companion MCP server (FastMCP, Lambda-in-VPC, Streamable HTTP + SigV4, a query
allowlist, Secrets Manager) would earn its place. It is **not** built here, and
an MCP server is explicitly *not* a fix for conversational or teaching quality.
See `references/forensics.md`.

## Known limits

- **Forensics correlation is advisory and probabilistic.** It states a confidence
  level and a confirming test; it does not prove causation. Treat "candidate
  cause" as a hypothesis to verify.
- **Least-privilege depends on CloudTrail coverage.** If CloudTrail history is
  unavailable for the window, the skill refuses to propose a policy rather than
  strip permissions blindly.
- **Management events only.** The skill reads CloudTrail through `LookupEvents`,
  which never contains data events. S3 object calls (`GetObject`, `PutObject`,
  …) are invisible to it, so granted S3 object actions are kept and flagged as
  unverified rather than removed, and a role is never called unused on that
  basis.
- **Key last-used gaps.** SES SMTP sends are not logged in CloudTrail, and
  S3 object calls are data events. Whether IAM's key last-used date reflects
  either is not verified here, so the skill lowers its confidence in NEVER_USED /
  IDLE flags when those uses are plausible, and warns that rotating a key breaks
  SES SMTP until new SMTP credentials are generated.
- **Read-only by design.** The skill never applies a change. Applying policies,
  deactivating keys, or executing a rollback would be a future, separately
  reviewed MCP write path with an action allowlist — out of scope for v1.

## License

Internal proof of concept. Not yet submitted to a public repository.
