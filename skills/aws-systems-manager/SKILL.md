---
name: aws-systems-manager
description: Use for AWS Systems Manager Automation tasks. Find an AWS-owned or account-owned
  runbook for an operational problem such as an unreachable EC2 instance, a node missing from
  Systems Manager, a public S3 bucket or a Config finding; prepare a safe start with rate control
  and a stopping alarm; explain why an execution failed, was cancelled or is waiting for
  approval; or review a runbook for security problems. Investigates read-only and prepares
  commands for a person to run.
metadata:
  author: hejn-amzn
  version: "1.0.0"
  summary: "Systems Manager guidance for DevOps Agent: find, run safely, diagnose and harden Automation runbooks."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA, INCIDENT_MITIGATION, PREVENTION, RELEASE_READINESS_REVIEW"
  aws-devops-agent-skills.aws-services: "AWS Systems Manager"
  aws-devops-agent-skills.technical-domains: "Operations, Security"
---

# AWS Systems Manager

Service-owned procedures for Systems Manager tasks. This file routes the request to one chapter
and sets the safety rules every chapter follows. Load only the chapter the request needs.

## Workflow

Copy this checklist and work through it in order:

- [ ] Step 1: Match the request to one row of the routing table
- [ ] Step 2: Load that chapter and follow it
- [ ] Step 3: Apply the safety contract below to everything you propose
- [ ] Step 4: Check the answer against the safety contract, then present it

## Step 1: Route the request

| The request is about | Chapter |
|---|---|
| Whether a runbook exists for a symptom, resource type or finding; which runbook to use; the account's own runbooks | [references/automation/runbook-discovery.md](references/automation/runbook-discovery.md) |
| Starting a known runbook, on one resource or many; rate control, alarms, multi-account runs; the status of an execution; why it failed, timed out, was cancelled or is waiting; stopping or approving one | [references/automation/execution.md](references/automation/execution.md) |
| Reviewing, scanning or hardening a runbook's content (schemaVersion 0.3) before it is published or shared | [references/automation/hardening.md](references/automation/hardening.md) |

Each request has one primary chapter. When a task moves on (for example, a runbook has been
found and the user now wants to run it), load the next chapter then; don't load chapters in
advance.

If the request is about a Systems Manager capability with no chapter here, say so and answer from
the public Systems Manager documentation, following the safety contract.

## Step 2: Follow the chapter

Each chapter has its own checklist, references and report format. Follow it as written.

## Step 3: Safety contract

Every chapter follows these rules:

1. **Investigate read-only first.** Read state with Describe, Get and List calls before
   proposing anything.
2. **Separate facts from hypotheses.** State what an API response showed, and label any cause
   you infer as inferred.
3. **Show the plan before any change:** the exact command, what it changes, the permissions it
   needs, how to roll it back, and how to verify it.
4. **Wait for explicit approval before any change.** A change is any action that writes,
   manages permissions or tags resources, including every `ssm:StartAutomationExecution` and
   `ssm:SendCommand`. The agent prepares the command; a person approves and runs it.
5. **Verify the result before claiming success.** An accepted request is not a success: read the
   resulting state and report it.

For a change, the sequence is: discover → plan → validate → obtain explicit approval → execute →
verify.

This skill guides behaviour; it doesn't grant or enforce permissions. IAM and service-side
controls remain the enforcement boundary.

## Gotchas

- Systems Manager resources are Regional. A runbook, execution or document found in one Region
  says nothing about another; always pass `--region`.
- An accepted `StartAutomationExecution` call returns an execution ID, not a result. The run can
  still fail, time out or be cancelled by an alarm; read its status before reporting.
- A runbook that looks read-only can run a child runbook (`aws:executeAutomation`) or commands on
  an instance (`aws:runCommand`) that change state. Judge it by its steps, not its name.

## Step 4: Check the answer

Before presenting, confirm that every proposed change has a plan with rollback and verification,
that nothing was started or changed without approval, and that every reported fact comes from an
API response in this conversation.
