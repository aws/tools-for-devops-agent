# AWS Systems Manager Runbook Hardening

Review an Automation runbook's content and return a report and a hardened document. Every check
in this chapter is grounded in a public Systems Manager or IAM documentation page, cited in
[references/automation/hardening-detection-rules.md](references/automation/hardening-detection-rules.md).

This review is static. It reads the document only. It doesn't run the runbook, and it doesn't
check the IAM policy of the role the runbook assumes; review that role separately.

## When to use

- A user asks to review or harden a runbook they wrote, before publishing or sharing it.
- A release or prevention review includes account-owned runbooks.

To choose a runbook for a problem, hand off to
[references/automation/runbook-discovery.md](references/automation/runbook-discovery.md); to run one, to
[references/automation/execution.md](references/automation/execution.md).

## Workflow

Copy this checklist and work through it in order:

- [ ] Step 1: Read the document (Phase 1)
- [ ] Step 2: Scan with every check in the detection rules (Phase 2)
- [ ] Step 3: Apply, propose or flag fixes (Phase 3)
- [ ] Step 4: Write the report and the hardened document (Phase 4)
- [ ] Step 5: Check the output, then present it

## Phase 1: Read the document

1. Get the document. If the user names a runbook in their account, call
   `aws ssm get-document --name <name> --region <region>`, and add `--document-version <n>` if
   they named a version. Otherwise use the content the user provides.
2. Note the format (YAML or JSON). The hardened document must use the same format.
3. Check `schemaVersion`. If it isn't `"0.3"`, stop: Automation runbooks must use schema version
   0.3. A `2.2` document is a Command document, which this chapter doesn't cover.
4. List `parameters` (name, type, constraints), `assumeRole`, and every step in `mainSteps`
   (name, action, inputs, `onFailure`, `onCancel`, `timeoutSeconds`, `maxAttempts`), including
   steps nested in `aws:loop`.

## Phase 2: Scan

Open [references/automation/hardening-detection-rules.md](references/automation/hardening-detection-rules.md) and apply every check, in
order:

| # | Check | Severity |
|---|---|---|
| 1 | Command injection: parameters or step outputs interpolated into shell or PowerShell commands | Critical |
| 2 | Secrets: hard-coded credentials, secret values passed as parameters, secrets in outputs | Critical |
| 3 | Parameter validation: missing or weak `allowedPattern`, `allowedValues`, length and item limits | High (Critical for parameters used in commands) |
| 4 | Role: missing `assumeRole` where the runbook needs it | High |
| 5 | Step limits: timeouts beyond documented limits | Medium |
| 6 | Failure and cancel routing: invalid `onFailure` / `onCancel` values or targets | Medium |
| 7 | Approval steps: `aws:approve` misconfiguration | Medium |
| 8 | Cross-account role assumption from a step | Medium |
| 9 | TLS verification disabled in a command or script | High |
| 10 | Document structure: schema version, required fields, parameter types, step names | Low |

For each finding record the check number, severity, the parameter or step (and JSON path), what is
wrong, and the documentation page that backs it.

Never repeat a secret's value in a finding. Give its location and tell the user to rotate it.

## Phase 3: Fix

Use [references/automation/hardening-fix-patterns.md](references/automation/hardening-fix-patterns.md). Fixes come in three kinds:

| Kind | Applies to | What you do |
|---|---|---|
| Apply | Deterministic changes to existing fields: add or tighten `allowedPattern`, fix an ARN pattern's partition, correct a timeout above a documented maximum, correct an invalid parameter type | Change the document directly. Don't add steps |
| Propose | Changes that alter behaviour: rewriting a command that interpolates parameters, moving a secret to Parameter Store, adding `assumeRole`, rerouting `onCancel` | Apply in the hardened document, and show each change as BEFORE / AFTER with the reason |
| Flag | Problems that need a redesign, or where the right fix depends on facts outside the document | Don't change the document. Describe the problem and what a redesign must address |

Flag rather than fix when proposed changes would touch most of the steps; patching that much
leaves a document that is harder to review than a rewrite.

Don't weaken an existing control to make the document pass, and don't remove a parameter the
document needs; change how it is used instead.

## Phase 4: Report

Write the report with the structure in
[references/automation/hardening-report-template.md](references/automation/hardening-report-template.md): a summary table by severity,
applied fixes, proposed fixes as BEFORE / AFTER with their source, flagged items, checks with no
findings, what the review didn't cover, and the complete hardened document in the input's format.

## Phase 5: Check the output

Before presenting the report, confirm:

- The hardened document parses as YAML or JSON, and every `allowedPattern` in it is still a
  valid regular expression.
- Every finding names a check from the detection rules and its source page.
- No secret value from the input appears anywhere in the report or the hardened document.
- Every difference between the input and the hardened document is listed as an applied or
  proposed fix.

Fix anything that doesn't hold before you answer.

## Gotchas

- Steps inside an `aws:loop` (`inputs.Steps`) are steps too; scan them.
- A parameter name containing "key" is often an identifier (`KeyName`, `KmsKeyId`, `S3Key`), not a
  secret.
- `allowedPattern` protects parameters only. A value from `{{StepName.OutputName}}` is never
  validated by it.
- Patterns must work in both Java regex and Go `regexp`: avoid lookahead and backreferences.
- In JSON documents every backslash in a pattern is doubled; in YAML, single-quote the pattern.

## Constraints

- Report only findings backed by a check in the detection rules.
- Never print a secret's value.
- Keep the document's behaviour, apart from the fixes you list.
- The hardened document must still parse: in JSON, escape backslashes in regular expressions
  (`\` becomes `\\`); in YAML, single-quote patterns that contain `\`, `{` or `}`.
