# IAM Access Navigator - custom agent

A **read-only** AWS DevOps Agent custom agent for IAM identity review. It wraps
the `iam-access-navigator` skill with a consistent opening, transparent coverage
reporting, a guided tour, and two **scheduled** jobs: an access-key hygiene sweep
and an IAM drift check. It diagnoses and recommends; a human applies every change.

> **This agent is sample code, not intended for production use without
> additional review and testing. Validate it in a non-production environment
> first.**

## What it does

- **Interactive:** introduces what it can do, detects which optional services are
  present, answers IAM risk / blast-radius / least-privilege / key-hygiene /
  validation / rollback / forensics questions, and states what data it did and
  did not use for every answer. It works with IAM and CloudTrail alone; IAM Access
  Analyzer, Security Hub, and Organizations only sharpen answers.
- **Scheduled - key hygiene:** finds access keys that are due for rotation, users
  with more than one active key, and keys that were never used, and files one
  recommendation per finding with a migration path (SSO federation, OIDC, IAM
  role, or rotation).
- **Scheduled - drift:** captures a point-in-time IAM snapshot, computes an exact
  difference against the previous one, and files a recommendation only for changes
  that make the account more permissive. Every run produces an "IAM Drift Report"
  artifact and ends with that report.

## What is in this folder

| File | Purpose |
|---|---|
| `SYSTEM_PROMPT.md` | The agent's system prompt (Goal / Approach / Constraints / Output). The only file imported into the agent. |
| `key-hygiene-prompt.md` | Standing prompt for the key-hygiene schedule. |
| `drift-sentinel-prompt.md` | Standing prompt for the drift schedule. |

## Prerequisites

- An AWS DevOps Agent Space with this agent's tools and skill available (below).
- The `iam-access-navigator` skill uploaded to the Space.
- For the drift job: the `iam-drift-diff` MCP server deployed and registered (see
  `mcp/iam-drift-diff`).
- Read access to IAM and CloudTrail `LookupEvents` for the Space's role,
  including `iam:ListAccessKeys` and `iam:GetAccessKeyLastUsed` for the
  key-hygiene sweep. As checked on 2026-11-03, the AWS managed DevOps Agent
  policies do not grant those two actions, so attach them explicitly. IAM
  Access Analyzer, Security Hub, and Organizations are optional.

## Assign these when you create the agent

| Item | Assign | Needed for |
|---|---|---|
| Skill | `iam-access-navigator` | All reasoning |
| Tool | `use_aws` | Reading IAM and CloudTrail |
| MCP tools | `iam_snapshot_capture`, `iam_snapshot_diff`, `iam_snapshot_list`, `iam_snapshot_get_entity` | Drift job only |
| Memory stores | None | The MCP owns drift persistence |

Assign the least privilege your use needs. If you do not run the drift job, do not
assign the MCP tools.

## How to run it

1. Create a custom agent, paste `SYSTEM_PROMPT.md` as the system prompt, and
   assign the items above.
2. **Interactive:** open a chat with the agent and ask, for example, "what IAM
   risk should I fix first?" or "walk me through an IAM security review".
3. **Scheduled:** add a schedule trigger and paste `key-hygiene-prompt.md` or
   `drift-sentinel-prompt.md` as the user prompt. A weekly cadence such as
   `rate(7 days)` fits both. The first drift run records a baseline and reports no
   changes; drift reporting starts on the second run.

## Outputs

Recommendations appear on the Improvements page (one per actionable finding).
Each drift run also creates an "IAM Drift Report" artifact and sends one
notification. The agent reads and recommends only; it never changes IAM.

## Known limitations

- Runs can take several minutes for large accounts, and a scheduled run is
  bounded by the invocation time limit.
- Drift cannot see groups or customer-managed policies if the Space's role is
  denied those reads; the report states exactly what was not covered.
- Findings reflect a point in time; this agent does not replace continuous
  detection from IAM Access Analyzer.

## Validation

Validated end to end in a DevOps Agent Space against a seeded test account: the
interactive flows, both scheduled jobs, recommendation creation and
de-duplication, and the drift report artifact. The skill's evaluation results are
in `skills/iam-access-navigator/evals/`.
