# Verdict Model for ECR Lifecycle Guard

The full tables behind the Verdict Model section of SKILL.md. The body carries
the same rules as compressed lists; this file is the lookup form, with weights
and rationale. Load it when a verdict is contested or when writing an evidence
string for an unusual case.

## 1. In use evidence hierarchy (strongest first)

| Tier | Evidence | Weight |
|---|---|---|
| (a) | `lastRecordedPullTime` present on the image | Authoritative. ECR maintains it from real pulls. ECR refreshes it at least once every 24 hours, so a pull in the last day may not show yet, and absence is never proof of non use |
| (b) | A reference by tag or digest in a running ECS task, an ECS service or ACTIVE task definition, a Batch ACTIVE job definition, a Lambda image function URI (`ImageUri` or `ResolvedImageUri`), or an App Runner service | Confirmed. A defined consumer names the image |
| (c) | A CloudTrail `BatchGetImage` or `GetDownloadUrlForLayer` event on the digest or tag | Circumstantial. The only tier that needs filtering, because an image push itself emits these events |

Tier (a) and tier (b) evidence is used as found. Tier (c) is used only after the
push correlation rule, which is stated in SKILL.md and explained with the
observed event pattern in
[ecr-lifecycle-semantics.md](ecr-lifecycle-semantics.md) section 6.

## 2. Per image verdict (first match wins)

| # | Verdict | Rule | Severity |
|---|---|---|---|
| 1 | `Safe` | Digest is not in the expiring set for this evaluation | none |
| 2 | `Expiring-InUse` | In the expiring set and at least one piece of evidence from tier (a), tier (b), or tier (c) after the push correlation rule. Tier (a) or (b) evidence gives this verdict regardless of any denied check | CRITICAL when the reference is a running ECS task, an App Runner service in `RUNNING`, or a Lambda function; otherwise HIGH |
| 3 | `Expiring-Unknown` | In the expiring set, tier (a) and (b) empty, no qualifying tier (c) event, and at least one in use source (U2 to U6: ECS tasks and services, ECS task definitions, Batch, Lambda, App Runner) is `AccessDenied`, `ToolingFailure`, `Partial` or `NotChecked`, or an EKS cluster exists in the Region. The optional CloudTrail probe is not an in use source for this row | MEDIUM |
| 4 | `Expiring-Unused` | In the expiring set, tier (a) and (b) empty, no qualifying tier (c) event (push correlated events only, or none), every in use source U2 to U6 `OK`, no EKS cluster | INFO |

A denied or cancelled in use source can never produce `Expiring-Unused`. Unknown
is a real answer and is reported as such. A cancelled or skipped CloudTrail probe
is listed under Not Assessed and changes no verdict; a CloudTrail pull event that
survives the push correlation rule counts as a reference in row 2, and one that
does not survive it is no evidence at all.

### Evidence string examples

Every verdict row names the tier that produced it:

- `tier (a) lastRecordedPullTime 2026-10-27 12:08Z`
- `tier (b) ECS service api-prod, task definition api:42, running task`
- `tier (c) CloudTrail BatchGetImage 2026-10-25 by role batch-worker, 4 days after push`
- `push correlated events only (1 excluded), no tier (a) or (b) evidence`

## 3. Repository rating (first match wins)

| # | Rating | Rule |
|---|---|---|
| 1 | `Indeterminate` | The expiring set could not be established: `DescribeImages` or `GetLifecyclePolicy` failed, or both preview and simulation failed |
| 2 | `AtRisk` | Any image is `Expiring-InUse` |
| 3 | `Attention` | Any image is `Expiring-Unknown`, or any finding of LOW or higher exists other than U8 (informational, never moves the rating), or the expiring set is `SIMULATED` |
| 4 | `Healthy` | Everything else, including "no lifecycle policy attached" (reported as INFO) and an empty expiring set |

A `SIMULATED` set or a denied source never lowers a rating below what the
evidence shows; it caps the rating at `Attention` when nothing in use was found.

Severity meanings and operator SLAs are in [check-matrix.md](check-matrix.md).
