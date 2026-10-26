# Report Template for ECR Lifecycle Guard

Load this file at Step 9 of the execution flow, immediately before rendering.
Render every `##` heading below in this order, even when a section is empty. An
empty section says why it is empty (no expiring images, no findings, source not
assessed). Replace every `<placeholder>`. Never leave a placeholder in the output.

## Single repository report

```markdown
# ECR Lifecycle Guard: <repositoryName>

Registry <accountId>, Region <region>, evaluated <YYYY-MM-DD HH:MM UTC>.
Expiring set source: <AUTHORITATIVE (GetLifecyclePolicyPreview) | SIMULATED (skill procedure, confirm with a preview)>.

## Scope

| Item | Value |
|---|---|
| Repository | <repositoryName> |
| Images in repository | <n> (<tagged> tagged, <untagged> untagged) |
| Lifecycle policy | <attached, n rules, lastEvaluatedAt <time> | none attached | draft supplied in chat> |
| Pull recency window | <N> days |
| In use sources checked | ECS tasks and services <status>, ECS task definitions <status>, Batch job definitions <status>, Lambda image functions <status>, App Runner services <status>, EKS presence <status>, CloudTrail pull events <status> |

## Repository Rating

**<Healthy | Attention | AtRisk | Indeterminate>**: <one sentence stating the deciding rule, for example "one expiring image has a recorded pull inside the window" or "expiring set is simulated and Batch job definitions were not readable">.

## Source of Truth

<AUTHORITATIVE: preview started <time>, status COMPLETE, expiringImageTotalCount <n>. | SIMULATED: preview <AccessDenied | cancelled by the agent guardrail and not approved | not available for a draft policy>; the expiring set below was computed with the documented ECR evaluation rules and must be confirmed with StartLifecyclePolicyPreview and GetLifecyclePolicyPreview before anyone relies on it.>
Policy last evaluated by ECR: <lastEvaluatedAt | never | unknown>.

## Expiring Images

<n> images would be <expired | archived> at the next evaluation.

| Tags | Digest | Pushed | Last recorded pull | Claimed by rule | Action | Verdict | Evidence |
|---|---|---|---|---|---|---|---|
| <tag1, tag2> | <sha256:first 12 hex> | <time> | <time | never> | <rulePriority> | <expire | archive> | <Expiring-InUse | Expiring-Unknown | Expiring-Unused> | <running ECS task arn:... | task definition family:rev | Batch job definition name:rev | Lambda function name | App Runner service name | lastRecordedPullTime 2026-10-21 16:34 UTC inside 30 day window | CloudTrail BatchGetImage by <principal type> on <date> | no reference found; Batch not readable | no reference found in any checked source> |

Images that survive this evaluation: <n>. <List their tags on one line, or "none".>

## Rule by Rule

| Priority | Selection | Candidates | Expires now | Keeps | Removes an in use image? |
|---|---|---|---|---|---|
| <10> | <untagged, sinceImagePushed 1 day> | <n> | <n> | <n> | <No | Yes: <tags>> |
| <100> | <any, imageCountMoreThan 6> | <n> | <n> | <n> | <No | Yes: <tags>> |

<One sentence per rule whose "Expires now" is smaller than its marked count, explaining which higher priority rule claimed the difference.>

## Findings

| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| <R1> | <CRITICAL | HIGH | MEDIUM | LOW | INFO> | <what, which images, which rule> | <the operator action, one sentence> |

## Suggested Protective Rule

<Present only when R1 or P4 produced a finding. Otherwise write "No protective rule is needed: no in use or production tagged image is in the expiring set."">

Add the rule below ahead of rule <lowest existing priority>; it keeps the newest <countNumber> images tagged <pattern> and removes them from the catch all's reach.

```json
{
  "rulePriority": <n>,
  "description": "<text>",
  "selection": {
    "tagStatus": "tagged",
    "tagPatternList": ["<pattern>"],
    "countType": "imageCountMoreThan",
    "countNumber": <n>
  },
  "action": { "type": "expire" }
}
```

Apply it with `aws ecr put-lifecycle-policy` or the console after running a preview on the complete policy. This skill does not apply lifecycle policy changes.

## Check Matrix

| ID | Check | Result | Detail |
|---|---|---|---|
| P1 | Lifecycle policy attached | <PASS | INFO> | <n rules | none attached> |
| P2 | `tagStatus: any` rule carries the highest priority number | <PASS | INFO | N/A> | <rule n | no any rule> |
| P3 | Expiring set comes from the ECR preview | <PASS | INFO> | <AUTHORITATIVE | SIMULATED: reason> |
| P4 | Production like tags protected by a tagged rule | <PASS | LOW | N/A> | <tags governed only by the catch all> |
| E1 | Expiring set established and every expiring image has one verdict | <PASS | FAIL> | <n images, n verdict rows> |
| U1 | `lastRecordedPullTime` read for every image | <PASS | FAIL> | <n of n images> |
| U2 | ECS running tasks and services checked | <OK | Partial | AccessDenied | ToolingFailure | NotChecked> | <n clusters, n tasks, n services> |
| U3 | ECS ACTIVE task definitions checked | <OK | Partial | AccessDenied | ToolingFailure> | <n described of n listed> |
| U4 | Batch ACTIVE job definitions checked | <OK | AccessDenied | ToolingFailure> | <n job definitions> |
| U5 | Lambda container image functions checked | <OK | Partial | AccessDenied | ToolingFailure> | <n image functions of n functions> |
| U6 | App Runner services checked | <OK | AccessDenied | ToolingFailure> | <n services> |
| U7 | EKS presence recorded, CloudTrail pull probe status recorded | <OK | NotChecked> | <n EKS clusters (pod references not checked); CloudTrail <status>> |
| R1 | No expiring image is in use | <PASS | HIGH | CRITICAL> | <tags> |
| R2 | No expiring image has an unknown in use status | <PASS | MEDIUM> | <n images; sources not readable: <list>> |

## Not Assessed

| Source | Status | Reason | Effect |
|---|---|---|---|
| <Batch job definitions> | <AccessDenied> | <batch:DescribeJobDefinitions is not in AIDevOpsAgentAccessPolicy> | <n unreferenced expiring images reported as Expiring-Unknown> |
| <Lifecycle policy preview> | <ToolingFailure> | <agent guardrail cancelled StartLifecyclePolicyPreview; approval not given> | <expiring set is SIMULATED; rating capped at Attention> |
| <EKS pod image references> | <NotChecked> | <data plane, out of scope> | <n clusters present; unreferenced expiring images reported as Expiring-Unknown> |

## Next Steps

1. <Operator action for every HIGH or CRITICAL finding, naming the image tags and the rule.>
2. <Grant or approve the preview if the set was SIMULATED, then rerun.>
3. <Grant the denied read actions (name them) and rerun, if any source was AccessDenied.>
4. <"Re-pull or re-tag" guidance for images the operator wants to keep while the policy is fixed, if applicable.>
```

## Multi repository (account or Region sweep) variant

Render an account summary first, then a full single repository report for every
repository that is not `Healthy`. `Healthy` repositories appear only in the
summary table.

```markdown
# ECR Lifecycle Guard: account <accountId>, Region <region>

Evaluated <YYYY-MM-DD HH:MM UTC>. <n> repositories, <n> with a lifecycle policy. In use inventory collected once for the Region: <source statuses>.

## Account Summary

| Repository | Rating | Policy | Expiring | Expiring-InUse | Expiring-Unknown | Source |
|---|---|---|---|---|---|---|
| <name> | AtRisk | <n rules> | <n> | <n> | <n> | <AUTHORITATIVE | SIMULATED> |
| <name> | Indeterminate | <n rules> | <unknown> | <unknown> | <unknown> | <reason> |
| <name> | Attention | <n rules> | <n> | 0 | <n> | <...> |
| <name> | Healthy | <none> | 0 | 0 | 0 | n/a |

Order: AtRisk, then Indeterminate, then Attention, then Healthy. Within a rating, more Expiring-InUse first, then alphabetical.

<Per repository sections follow for every repository rated AtRisk, Indeterminate or Attention, each using the single repository layout from "## Scope" to "## Next Steps".>
```

When the user asked for every enabled Region, repeat the account summary per
Region and add a one line roll up at the top: "<n> Regions swept, <n>
repositories rated AtRisk."

## Pre render validation

Check each item before sending. Fix the report, not the checklist.

1. Every `##` heading above is present, in order, exactly once per repository.
2. The expiring image count is identical in Scope, Source of Truth (when
   AUTHORITATIVE, equal to `expiringImageTotalCount`), Expiring Images, and the
   Rule by Rule "Expires now" column total.
3. Every expiring digest has exactly one row in Expiring Images and exactly one
   verdict from `Expiring-InUse`, `Expiring-Unknown`, `Expiring-Unused`. A multi
   tag digest is one row listing every tag.
4. The word "safe", "not a concern", "currently fine" or any equivalent appears
   only inside a verdict row or the rating sentence, never as free prose about an
   image.
5. The Check Matrix has exactly 14 rows, P1 to P4, E1, U1 to U7, R1, R2.
6. The rating is stated once, in Repository Rating, and matches the first
   matching row of the rating table in SKILL.md.
7. Every source with status `AccessDenied`, `ToolingFailure`, `Partial` or
   `NotChecked` appears in Not Assessed, and none of them is described as having
   returned zero references.
8. No mutating operation (`PutLifecyclePolicy`, `DeleteLifecyclePolicy`,
   `BatchDeleteImage`, `PutImage`, `PutImageTagMutability`, `DeleteRepository`)
   is named as performed. The suggested rule is marked as an operator action.
9. The report ends after Next Steps. No offer to "apply", "clean up", "fix" or
   "dig further" follows it.
10. Account ids, repository names, tags and digests come from API responses in
    this run. No internal tool names, team aliases or Agent Space ids appear.
