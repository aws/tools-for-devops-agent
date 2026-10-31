# ECR Lifecycle Policy Semantics and Simulation Procedure

Load this file at Step 4 of the execution flow, only when the lifecycle policy
preview (`StartLifecyclePolicyPreview` + `GetLifecyclePolicyPreview`) could not
run. The preview is ECR's own evaluator and always outranks this procedure. Any
result produced from this file is labelled `SIMULATED` in the report and the
report tells the operator to confirm it with a preview before acting.

Every rule below is taken from the Amazon ECR User Guide pages listed at the end.
Where a sentence is quoted, it is quoted exactly so the agent can cite it.

## 1. Evaluation procedure (numbered, deterministic)

Inputs: the policy JSON (`lifecyclePolicyText`), the full image list from
`DescribeImages` (every page), and the evaluation time `now` (UTC).

1. **Parse and validate the policy.**
   - Sort rules by `rulePriority` ascending (1 is the highest priority).
   - Confirm priorities are unique.
   - If a rule has `tagStatus: any`, confirm it carries the highest
     `rulePriority` number. The parameters page states this as a requirement;
     ECR is expected to reject a policy that violates it at `PutLifecyclePolicy`,
     but the rejection behaviour is not stated in the public documentation (see
     the unverified facts table in ecr-api-reference.md). Treat a violation in
     an attached policy or a draft the same way: report it under check P2 and
     stop the simulation for that policy.
   - At most one rule may select untagged images.
   - A rule may carry `tagPatternList` or `tagPrefixList`, never both. Lists are
     only valid with `tagStatus: tagged`. `untagged` rules carry neither.
   - Note each rule's `action.type`: `expire` or `archive`. Both remove the image
     from normal pull paths, so both are treated as deletion risk for verdicts.
     Report the action in its own column.
2. **Compute each rule's candidate set independently** (all rules are evaluated
   at the same time, so this step ignores every other rule):
   - `tagStatus: untagged`: images whose `imageTags` is absent or empty.
   - `tagStatus: tagged`: images where **every entry** in the rule's list matches
     **at least one** of the image's tags. Entries are ANDed across the list; any
     tag of the image can satisfy an entry. Prefix entries match when a tag
     starts with the entry. Pattern entries use `*` as a wildcard (up to four per
     entry) and match the whole tag.
   - `tagStatus: any`: every image in the repository.
3. **Mark images inside each candidate set using the rule's count criterion.**
   The candidate set is the full set from step 2. It is never reduced by what
   another rule selected or expired. Do not shrink the pool before applying
   `imageCountMoreThan`.
   - `imageCountMoreThan N`: sort the candidate set by `imagePushedAt`
     descending (newest first). Images at position N+1 and later are marked.
     For a `tagStatus: any` rule the candidate set is every image in the
     repository, so the rule keeps the N newest of the whole repository, not
     the N newest of whatever a higher rule left over.
     If an image was archived and later restored, use `lastActivatedAt` in place
     of `imagePushedAt`.
   - `sinceImagePushed N days`: mark when `now - imagePushedAt > N days`.
   - `sinceImagePulled N days`: mark when `now - lastRecordedPullTime > N days`.
     An image that has never been pulled has no `lastRecordedPullTime`; ECR
     falls back to the push time for this comparison.
   - `sinceImageTransitioned N days`: applies to archived images only, measured
     from `lastArchivedAt`.
4. **Apply rules in priority order and build the expiring set.** Walk the sorted
   rules from the lowest `rulePriority` number upward and keep a set of
   *claimed* digests, initially empty:
   - For the current rule, every image in its **candidate set** (marked or not)
     is claimed by it unless an earlier rule already claimed it.
   - Every image that this rule **marked** and that was **not claimed by an
     earlier rule** joins the expiring set with `appliedRulePriority` equal to
     this rule's priority and `action` equal to its action type.
   - A marked image that an earlier rule already claimed is skipped. The doc
     wording: "An image that matches the tagging requirements of a rule cannot
     be expired or archived by a rule with a lower priority."
   - Lower priority rules still count claimed images when sorting and counting
     their own candidates, as if nothing had been expired ("can still identify
     them as if they haven't been expired or archived").
5. **Protect manifest list children.** An image referenced by a manifest list
   (`imageManifestMediaType` of an image index or manifest list that lists its
   digest) is not expired while the list exists. Remove such children from the
   expiring set and note it. Reference artifacts (images with a
   `subjectManifestDigest`) are expired by ECR within 24 hours of their subject,
   so list them as "expires with subject" rather than as rule results.
6. **Output.** The expiring set, each entry with digest, all tags, push time,
   `appliedRulePriority`, action. Sort by applied rule, then `imagePushedAt`
   ascending (oldest first, which is also the order ECR expires in). Count the
   entries and state the count once. Label the result `SIMULATED`.

Each image appears in the output zero or one times. If the procedure produces an
image twice, step 4 was applied incorrectly.

## 2. Matching semantics with citations

| Topic | Rule | Source |
|---|---|---|
| Evaluation order | "All rules are evaluated at the same time, regardless of rule priority. After all rules are evaluated, they are then applied based on rule priority." | LifecyclePolicies.html |
| One rule per image | "An image is expired or archived by exactly one or zero rules." | LifecyclePolicies.html |
| Higher rule claims the image | "An image that matches the tagging requirements of a rule cannot be expired or archived by a rule with a lower priority." | LifecyclePolicies.html |
| Lower rules still see claimed images | "Rules can never mark images that are marked by higher priority rules, but can still identify them as if they haven't been expired or archived." | LifecyclePolicies.html |
| List entries are ANDed | "An image is successfully matched if all of the tags in the tagPatternList or tagPrefixList value are matched against any of the image's tags." | LifecyclePolicies.html |
| Pattern wildcards | `prod*` matches `prod`, `prod1`, `production-team1`; `*prod*` matches `repo-production`. "There is a maximum limit of four wildcards (*) per string." | LifecyclePolicies.html |
| One list type per rule | "A lifecycle policy rule may specify either tagPatternList or tagPrefixList, but not both." | LifecyclePolicies.html |
| Expiry order | "Expiration is always ordered by pushed_at_time or transitioned_at_time and always expires older images before newer ones." Restored images use `last_activated_at`. | LifecyclePolicies.html |
| `any` rule placement | "A rule with a tagStatus value of any must have the highest value for rulePriority and be evaluated last." | lifecycle_policy_parameters.html |
| Untagged rule uniqueness | "Only one rule selecting a specific storage class is allowed to select untagged images." | LifecyclePolicies.html |
| Unique prefixes | "The set of all rules selecting a specific storage class must contain a unique set of prefixes." | LifecyclePolicies.html |
| Manifest lists | "If an image is referenced by a manifest list, it cannot be expired or archived without the manifest list being deleted or archived first." | LifecyclePolicies.html |
| Reference artifacts | Lifecycle policies "automatically expire or archive those artifacts within 24 hours of the deletion or archival of the subject image." | LifecyclePolicies.html |
| Execution delay | Images "become expired within 24 hours after they meet the expiration criteria." | LifecyclePolicies.html |
| Console AND note | "If you specify multiple tags, only the images with all specified tags are selected." | lpp_creation.html |

The AND rule across list entries is the most common source of wrong mental
models. A rule with `tagPrefixList: ["prod-", "release-"]` matches only images
that carry both a `prod-` tag and a `release-` tag. It does not match an image
tagged only `prod-2026`. To protect two tag families, write two rules.

## 3. Worked example (regression oracle)

Repository `example-batch-worker`, 26 tagged images, zero untagged, all pushed on
2026-10-21 within one minute. Push order oldest to newest, with illustrative
times that preserve the real order:

| # | Tag | Pushed (UTC) | # | Tag | Pushed (UTC) |
|---|---|---|---|---|---|
| 1 | build-1 | 16:33:21 | 14 | rc-0.2 | 16:33:47 |
| 2 | build-2 | 16:33:23 | 15 | rc-0.3 | 16:33:49 |
| 3 | build-3 | 16:33:25 | 16 | rc-0.4 | 16:33:51 |
| 4 | build-4 | 16:33:27 | 17 | v2.1.0 | 16:33:53 |
| 5 | build-5 | 16:33:29 | 18 | v2.2.0 | 16:33:56 |
| 6 | build-6 | 16:33:31 | 19 | v2.3.0 | 16:33:58 |
| 7 | build-7 | 16:33:33 | 20 | v2.4.0 | 16:34:00 |
| 8 | build-8 | 16:33:35 | 21 | v2.5.0 | 16:34:02 |
| 9 | build-9 | 16:33:37 | 22 | hotfix-2.3.1 | 16:34:03 |
| 10 | build-10 | 16:33:39 | 23 | nightly-20261001 | 16:34:05 |
| 11 | build-11 | 16:33:41 | 24 | nightly-20261008 | 16:34:08 |
| 12 | build-12 | 16:33:43 | 25 | nightly-20261015 | 16:34:11 |
| 13 | rc-0.1 | 16:33:45 | 26 | latest | 16:34:13 |

Policy (five rules, all `action.type: expire`):

| rulePriority | tagStatus | Selection | Count criterion |
|---|---|---|---|
| 10 | untagged | none | sinceImagePushed 1 day |
| 20 | tagged | tagPrefixList `nightly-` | imageCountMoreThan 2 |
| 30 | tagged | tagPatternList `build-*` | imageCountMoreThan 5 |
| 40 | tagged | tagPrefixList `rc-` | sinceImagePushed 14 days |
| 100 | any | all images | imageCountMoreThan 6 |

Evaluation time `now` = 2026-10-21 16:36 UTC. Work through the procedure in
section 1 step by step, writing each intermediate set out in full.

1. **Parse.** Priorities 10, 20, 30, 40, 100 are unique. The `any` rule (100)
   carries the highest number. One untagged rule. Every rule's action is
   `expire`.

2. **Candidate set per rule, computed independently over all 26 images.** No
   rule's set is reduced by another rule at this step.
   - Rule 10 (`untagged`): {} (0 images; every image is tagged).
   - Rule 20 (`tagPrefixList nightly-`): {nightly-20261001, nightly-20261008,
     nightly-20261015} (3).
   - Rule 30 (`tagPatternList build-*`): {build-1, build-2, build-3, build-4,
     build-5, build-6, build-7, build-8, build-9, build-10, build-11, build-12}
     (12).
   - Rule 40 (`tagPrefixList rc-`): {rc-0.1, rc-0.2, rc-0.3, rc-0.4} (4).
   - Rule 100 (`any`): all 26 images. Not "the 7 images no other rule
     selected". `tagStatus: any` matches every image in the repository.

3. **Marked set per rule, from each rule's full candidate set.**
   - Rule 10, `sinceImagePushed 1 day`: {} (no candidates).
   - Rule 20, `imageCountMoreThan 2`: sort the 3 nightly images newest first:
     nightly-20261015, nightly-20261008, nightly-20261001. Keep 2. Marked:
     {nightly-20261001} (1).
   - Rule 30, `imageCountMoreThan 5`: sort the 12 build images newest first:
     build-12, build-11, build-10, build-9, build-8, | build-7, build-6,
     build-5, build-4, build-3, build-2, build-1. Keep 5. Marked: {build-1,
     build-2, build-3, build-4, build-5, build-6, build-7} (7).
   - Rule 40, `sinceImagePushed 14 days`: every rc image is about 3 minutes
     old. Marked: {} (0).
   - Rule 100, `imageCountMoreThan 6`: sort **all 26** images newest first:
     latest, nightly-20261015, nightly-20261008, nightly-20261001,
     hotfix-2.3.1, v2.5.0, | v2.4.0, v2.3.0, v2.2.0, v2.1.0, rc-0.4, rc-0.3,
     rc-0.2, rc-0.1, build-12, build-11, build-10, build-9, build-8, build-7,
     build-6, build-5, build-4, build-3, build-2, build-1. Keep the 6 newest
     of the whole repository: {latest, nightly-20261015, nightly-20261008,
     nightly-20261001, hotfix-2.3.1, v2.5.0}. Marked: the other 20 {v2.4.0,
     v2.3.0, v2.2.0, v2.1.0, rc-0.4, rc-0.3, rc-0.2, rc-0.1, build-12,
     build-11, build-10, build-9, build-8, build-7, build-6, build-5, build-4,
     build-3, build-2, build-1} (20).

4. **Apply in priority order, tracking the claimed set.** Claimed starts
   empty. A rule claims its whole candidate set (marked or not) and expires
   only the marked images not already claimed.
   - Rule 10: claims {}. Expires {}. Claimed so far: {} (0).
   - Rule 20: claims {nightly-20261001, nightly-20261008, nightly-20261015}.
     Expires {nightly-20261001}. Claimed so far: 3 images.
   - Rule 30: claims the 12 build images. Expires {build-1, build-2, build-3,
     build-4, build-5, build-6, build-7}. Claimed so far: 15 images.
   - Rule 40: claims {rc-0.1, rc-0.2, rc-0.3, rc-0.4}. Expires {} (nothing
     marked). The 4 rc images are now claimed, so rule 100 can no longer
     expire them even though rule 40 did not. Claimed so far: 19 images.
   - Rule 100: marked set from step 3 is 20 images. Remove the ones already
     claimed: nightly-20261001 (rule 20), build-1 to build-12 (rule 30),
     rc-0.1 to rc-0.4 (rule 40), 16 images removed. Expires the 4 that remain:
     {v2.1.0, v2.2.0, v2.3.0, v2.4.0}. Rule 100 also claims the remaining 7
     unclaimed images (v2.1.0 to v2.5.0, hotfix-2.3.1, latest), but its keep
     count was already applied over all 26 in step 3, not over these 7.

5. **Manifest lists.** None in this fixture; nothing removed.

6. **Output.** `SIMULATED`, 12 images expiring:
   - Rule 20: nightly-20261001 (1)
   - Rule 30: build-1, build-2, build-3, build-4, build-5, build-6, build-7 (7)
   - Rule 100: v2.1.0, v2.2.0, v2.3.0, v2.4.0 (4)

   Survivors, 14: build-8, build-9, build-10, build-11, build-12, rc-0.1,
   rc-0.2, rc-0.3, rc-0.4, v2.5.0, hotfix-2.3.1, nightly-20261008,
   nightly-20261015, latest. 12 + 14 = 26.

Rule by Rule table for the report, with the column meanings from
report-template.md (Candidates: step 2; Marked: step 3; Expires now: step 4;
Keeps: Candidates minus Expires now):

| Priority | Selection | Candidates | Marked | Expires now | Keeps |
|---|---|---|---|---|---|
| 10 | untagged, sinceImagePushed 1 day | 0 | 0 | 0 | 0 |
| 20 | tagged nightly-, imageCountMoreThan 2 | 3 | 1 | 1 | 2 |
| 30 | tagged build-*, imageCountMoreThan 5 | 12 | 7 | 7 | 5 |
| 40 | tagged rc-, sinceImagePushed 14 days | 4 | 0 | 0 | 4 |
| 100 | any, imageCountMoreThan 6 | 26 | 20 | 4 | 22 |

This matches ECR's own `GetLifecyclePolicyPreview` output for the same fixture,
and the documented Example B on lifecycle_policy_examples.html, where the `any`
rule "identifies images A, B, C, D, and E" (all of them), keeps the newest one,
and "can't mark images A, B, C, or E because they were identified by higher
priority rules", expiring only D.

Common wrong answers, each caused by skipping a step above:

- **9 images (the most frequent error).** Removing the nightly, build and rc
  images from rule 100's pool first, then applying "keep 6" to the 7 leftover
  images (v2.1.0 to v2.5.0, hotfix-2.3.1, latest), which expires only v2.1.0.
  This shrinks the pool before applying `imageCountMoreThan`. The catch all
  keeps the 6 newest of the whole repository, so v2.2.0, v2.3.0 and v2.4.0 are
  outside the top 6 and expire. The right order is: mark over all 26 (step 3),
  then remove claimed images from the marked set (step 4).
- **More than 12**, listing rc-0.1 to rc-0.4 and build-8 to build-12 as
  expiring under rule 100 (skipped the claim rule in step 4).
- **Only the four v2.x images** (dropped rules 20 and 30), or **only one
  image** (treated the policy as a single rule).

If a future revision of the AWS documentation describes the catch all count
differently from the reading above, follow the documentation, note the change
in CHANGELOG.md and re-derive this example.

## 4. Protected tag patterns (heuristic, check P4)

A `tagStatus: any` catch all rule is the usual way an in use or production image
gets deleted: it counts across every tag family and knows nothing about what is
running. When an image in the expiring set was placed there by an `any` rule and
no `tagged` rule claims it, test its tags against these patterns:

| Pattern (regex, case insensitive) | Family |
|---|---|
| `^prod` | prod, prod-2026-10, production-eu |
| `^release` | release-1.4, releases |
| `^v?\d+\.\d+\.\d+` | v2.3.0, 2.3.0, v2.3.0-rc1 |
| `^latest$` | latest |
| `^stable$` | stable |
| `^hotfix` | hotfix-2.3.1 |

A match produces finding P4 at severity LOW even when no runtime reference was
found. The reasoning is that these tag families signal intent to keep, and the
catch all is deleting them only because newer images of other families exist.
The operator may extend or trim this list in the prompt.

## 5. Writing a protective rule (presented, never applied)

A protective rule gives the protected family its own, higher priority rule with a
generous keep count, so the catch all can no longer claim those images. Use
`tagPatternList`, one family per rule, and a priority number lower than every
existing rule so it is evaluated first. Leave a gap for future rules.

```json
{
  "rulePriority": 5,
  "description": "Protect semantic version releases from the catch all",
  "selection": {
    "tagStatus": "tagged",
    "tagPatternList": ["v*.*.*"],
    "countType": "imageCountMoreThan",
    "countNumber": 50
  },
  "action": { "type": "expire" }
}
```

Rules for the suggestion:

- Priority: the lowest existing `rulePriority` minus 5, minimum 1. If that
  collides, renumber in the suggestion and say so.
- `tagPatternList` with one entry per rule. Never put two families in one list
  (they would be ANDed).
- `countNumber` 50 unless the operator states a retention target.
- Keep `tagStatus: any` as the last rule with the highest number.
- Present the complete rule JSON and a one line explanation of where it slots in.
- The operator applies it with `PutLifecyclePolicy` or the console after running
  a preview. This skill never applies it, even when asked.

## 6. In use evidence hierarchy and push correlation

The verdict for an expiring image rests on evidence that the image is still
consumed. Not every signal is equal, so the skill ranks them and only the weakest
tier is filtered.

| Tier | Evidence | Why it ranks here |
|---|---|---|
| (a) | `lastRecordedPullTime` on the image | ECR writes it from real pulls, so it cannot be produced by a push. The `ImageDetail` doc says it is refreshed at least once every 24 hours, so it may lag the newest pull by a day. Present means pulled; absent means "no recorded pull", never "unused" |
| (b) | A tag or digest reference in an ECS running task, service or ACTIVE task definition, a Batch ACTIVE job definition, a Lambda image function URI, or an App Runner service | A consumer has declared the image. The reference exists whether or not it has pulled recently, so it is deliberate intent |
| (c) | A CloudTrail `BatchGetImage` or `GetDownloadUrlForLayer` event on the digest or tag | The same API calls are made by a `docker pull`, by a task launch, and by the push itself. The event alone does not say which |

Why tier (c) needs a filter. When a client pushes an image, the registry
workflow checks layers (`BatchCheckLayerAvailability`), uploads them
(`InitiateLayerUpload`, `CompleteLayerUpload`), puts the manifest (`PutImage`,
which sets `imagePushedAt`), and the client then reads the manifest back
(`BatchGetImage`). All of these land in CloudTrail from the pushing principal
within a few seconds of `imagePushedAt`. On 2026-10-27, 26 of 26 images in the
test repository carried a `BatchGetImage` event 1 to 2 seconds after their push,
every one from the same role that pushed, and ECR's own `lastRecordedPullTime`
was set on one image only. Counting those events as pulls marked 11 of 11
expiring images `Expiring-InUse`, a 100 percent false positive rate, and would
hand a customer with 200 images 200 HIGH findings.

The push correlation rule:

1. Any `BatchGetImage`, `GetDownloadUrlForLayer`, `PutImage`,
   `InitiateLayerUpload`, `CompleteLayerUpload` or `BatchCheckLayerAvailability`
   event whose `eventTime` is within 60 seconds of that image's `imagePushedAt`
   is part of the push workflow and MUST NOT count as a consumer pull. Sixty
   seconds is deliberately wide compared with the observed 1 to 4 seconds; a
   genuine consumer that pulls within a minute of a push is rare, and
   `lastRecordedPullTime` would still catch it in tier (a).
2. Any event whose `userIdentity` matches the principal that performed the push
   is also excluded, regardless of its time. The principal is taken from the
   `PutImage` event for the same digest when one is available, otherwise from
   the events inside the 60 second window. Compare on the role
   (`sessionContext.sessionIssuer.arn`) when present so that two sessions of the
   same CI role are treated as the same principal. A push pipeline that re-reads
   its own image hours later is still not a consumer.
3. What remains is a qualifying pull. One qualifying pull more than 60 seconds
   after push makes the image `Expiring-InUse` on tier (c), and the evidence
   string names the event, time, principal and gap from push.
4. Count the excluded events per image and in total. The total is reported in
   check U8 (LOW, informational) so the operator can see the filter worked. The
   count never changes a verdict or the rating.

How the tiers combine:

- Tier (a) or tier (b) evidence gives `Expiring-InUse` on its own, regardless of
  any denied source or of what CloudTrail says.
- With (a) and (b) empty, tier (c) after the rule decides between `Expiring-InUse`
  (a qualifying pull exists) and the no evidence path.
- With no evidence from any tier, the image is `Expiring-Unused` when every in
  use source U2 to U6 is `OK` and no EKS cluster exists, and `Expiring-Unknown`
  when one of those sources was denied, cancelled or partial. Push correlated
  events alone are the no evidence path; they never produce `Expiring-Unknown`
  by themselves.

## 7. Documentation URLs

- Lifecycle policies and evaluation rules:
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html
- Lifecycle policy parameters (`tagStatus: any` placement, countType values):
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_parameters.html
- Lifecycle policy examples:
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_examples.html
- Creating a lifecycle policy preview (console, AND note, 24 hour note):
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/lpp_creation.html
- `ImageDetail` (`lastRecordedPullTime`, `imageStatus`, `lastActivatedAt`):
  https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_ImageDetail.html
- Lifecycle events in CloudTrail (`PolicyExecutionEvent`, `DryRunEvent`) and the
  `BatchGetImage` event example used for the push correlation rule:
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/logging-using-cloudtrail.html
- CloudTrail `userIdentity` element (`arn`, `sessionContext.sessionIssuer`):
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html
