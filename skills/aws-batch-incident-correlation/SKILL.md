---
name: aws-batch-incident-correlation
description: >-
  Correlation guardrail for AWS Batch incidents during triage. Use this skill when deciding
  whether a Batch CloudWatch alarm should be linked to, or made the primary investigation
  for, an existing incident. Batch alarms are dimensioned on a specific JobQueue, and two
  different job queues can share an account, region and compute environments while stalling
  for unrelated reasons. This skill requires the JobQueue dimension of both incidents to be
  compared before linking, and prevents an alarm scoped to one job queue from becoming the
  primary investigation for incidents on a different queue.
metadata:
  author: AWSGolden
  version: "1.0.0"
  summary: "Stops a Batch alarm on one job queue from being linked to incidents on a different job queue."
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE"
  aws-devops-agent-skills.aws-services: "AWS Batch, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "High Performance Computing, Operations"
---

# AWS Batch incident correlation

Batch incidents arrive in bursts that look correlated and often are not. A load of jobs
submitted together will fail together — in time proximity, in the same region, sometimes
across several queues at once — while having unrelated causes.

This skill governs one specific, high-value correlation decision that the agent does not get
right on its own: **do not conflate incidents that belong to different job queues.**

> Scope note. Earlier drafts of this skill carried five rules. Four were removed because
> measurement showed the base agent already applied them (or the rule made results worse).
> Only the cross-queue rule below produced a decisive, repeatable improvement, so it is all
> this skill claims. See README.md for the evaluation that drove the cut.

## The rule: an alarm scoped to one job queue must not become the primary for another

Batch alarms are typically dimensioned on a specific `JobQueue`. Before linking a new Batch
incident to an existing investigation, or making it the primary:

1. Read the `JobQueue` dimension of the new incident's alarm.
2. Read the `JobQueue` dimension of the existing investigation's alarm.
3. **If they differ, do not link and do not make one the primary for the other.** Two Batch
   queues can share an account, a region and a compute environment set and still stall for
   entirely unrelated reasons. Shared infrastructure is not a shared cause.

Schedule the new incident as its own investigation instead.

## State the dimension you compared

When you record correlation reasoning, name the `JobQueue` values you compared. Never assert
that two incidents are on "the same queue" without having actually read and compared the
dimension on both — that specific unchecked claim is the failure this skill exists to
prevent.

## Verify before finalising

Run this check before presenting any link-or-primary decision as final.

- [ ] Confirm the `JobQueue` dimension was read from **both** incidents, not inferred from
      their titles or descriptions.
- [ ] If the two `JobQueue` values differ, confirm the decision is **not** to link and
      **not** to make one primary for the other.
- [ ] Confirm any "same queue" statement in the reasoning is backed by the compared
      dimension values.
