# Fixed Check Matrix and Severity Scale for ECR Lifecycle Guard

Load this file at Step 9 of SKILL.md, before evaluating the checks and rendering
the report. Every run reports all 15 checks in the order below. A check that
could not be evaluated shows its source status, never a guessed result.

## Check matrix

| ID | Check | Finding condition | Severity |
|---|---|---|---|
| P1 | Lifecycle policy attached | No policy and no draft | INFO |
| P2 | `tagStatus: any` rule carries the highest `rulePriority` number | The policy violates the documented requirement (expected on a draft; ECR is expected to reject it at `PutLifecyclePolicy`, not verified from docs) | INFO |
| P3 | Expiring set comes from the ECR preview | Set is `SIMULATED` | INFO |
| P4 | Production like tags protected by a `tagged` rule | A tag matching the protected patterns is expiring under a `tagStatus: any` rule | LOW |
| E1 | Expiring set established and every expiring image has exactly one verdict | Set missing, or a digest without a verdict row | rating `Indeterminate` |
| U1 | `lastRecordedPullTime` read for every image | Any `DescribeImages` page missing | FAIL, rating `Indeterminate` |
| U2 | ECS running tasks and services checked | Source not `OK` | status shown |
| U3 | ECS ACTIVE task definitions checked | Source not `OK` (`Partial` allowed, drives Unknown) | status shown |
| U4 | Batch ACTIVE job definitions checked | Source not `OK` | status shown |
| U5 | Lambda container image functions checked | Source not `OK` | status shown |
| U6 | App Runner services checked | Source not `OK` | status shown |
| U7 | EKS presence and CloudTrail probe status recorded | Never a finding; records what was and was not checked | status shown |
| U8 | CloudTrail events excluded as push correlated | At least one CloudTrail event on an expiring image was dropped by the push correlation rule; the detail states how many, across how many images. `PASS` when the probe ran and nothing was dropped, `NotChecked` when it did not run | LOW, informational, never moves the rating |
| R1 | No expiring image is in use | Any `Expiring-InUse` after the evidence hierarchy and the push correlation rule. Push correlated CloudTrail events alone never fail this check | HIGH, or CRITICAL per the verdict table |
| R2 | No expiring image has unknown in use status | Any `Expiring-Unknown` | MEDIUM |

A protective rule is proposed whenever R1 or P4 produces a finding. U8 exists so
the operator can see that the filter worked; it never changes a verdict.

The protected tag patterns tested by P4 are `^prod`, `^release`,
`^v?\d+\.\d+\.\d+`, `^latest$`, `^stable$` and `^hotfix`; see
[ecr-lifecycle-semantics.md](ecr-lifecycle-semantics.md) section 4.

## Severity scale

| Severity | Meaning | Operator SLA |
|---|---|---|
| CRITICAL | A running workload's image will be removed | Before the next lifecycle evaluation (within 24 hours) |
| HIGH | A defined but not currently running workload's image, or a recently pulled image, will be removed | Within 24 hours |
| MEDIUM | In use status unknown because a source could not be read | Grant the read action and rerun this week |
| LOW | Production like tag governed only by a catch all rule (P4), or the informational count of CloudTrail events excluded as push correlated (U8, never moves the rating) | Next policy change (P4); none (U8) |
| INFO | Observations that need no action | none |

Severity of an `Expiring-InUse` image is CRITICAL when the reference is a
running ECS task, an App Runner service in `RUNNING`, or a Lambda function;
otherwise HIGH. See [verdict-model.md](verdict-model.md).
