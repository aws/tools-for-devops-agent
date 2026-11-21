# IAM Quota & Policy-Size Auditor (DevOps Agent skill)

Read-only, report-only DevOps Agent skill that audits an account's IAM roles,
users, and policies for objects approaching their IAM limits (managed policies
per role/user, policy/inline/trust document size, versions, entity counts) and
produces a prioritized consolidate-vs-draft-increase plan.

Pairs with the demo scenario stack `scenarios/cfn-iam-scenario.yaml`, which
provisions a role at 9/10 managed-policy attachments and a customer-managed
policy near the 6,144-character limit.

Taskei: V2392080106.

> **Non-production disclaimer.** This skill is provided for demonstration and
> evaluation. It is read-only and report-only — it never writes, merges, or
> rewrites IAM policies and never submits a quota increase. Review all findings
> and apply any changes through your own change-management and IaC process.
> Not an AWS service; no warranty.

## Use

Load into a DevOps Agent Agent Space (Chat tasks + Incident RCA), then ask it
to audit IAM limits. See `SKILL.md` for the full workflow and `evals/` for the
evaluation scenarios.
