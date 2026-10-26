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
3. **Mark images inside each candidate set using the rule's count criterion:**
   - `imageCountMoreThan N`: sort the candidate set by `imagePushedAt`
     descending (newest first). Images at position N+1 and later are marked.
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

Step 2 and 3, per rule (evaluated independently, `now` = 2026-10-21 16:36 UTC):

| Rule | Candidates | Marked |
|---|---|---|
| 10 | none (no untagged images) | none |
| 20 | nightly-20261015, nightly-20261008, nightly-20261001 (3) | newest 2 kept; nightly-20261001 marked |
| 30 | build-12 down to build-1 (12) | newest 5 kept (build-8 to build-12); build-1 to build-7 marked |
| 40 | rc-0.1 to rc-0.4 (4) | none (all 0 days old, threshold 14 days) |
| 100 | all 26 | newest 6 kept: latest, nightly-20261015, nightly-20261008, nightly-20261001, hotfix-2.3.1, v2.5.0; the other 20 marked |

Step 4, apply in priority order:

| Rule | Claims (candidate set minus earlier claims) | Expires (marked and unclaimed) |
|---|---|---|
| 10 | nothing | nothing |
| 20 | 3 nightly images | nightly-20261001 |
| 30 | 12 build images | build-1, build-2, build-3, build-4, build-5, build-6, build-7 |
| 40 | 4 rc images | nothing (claimed, so rule 100 can no longer touch them) |
| 100 | the remaining 7: v2.1.0 to v2.5.0, hotfix-2.3.1, latest | v2.1.0, v2.2.0, v2.3.0, v2.4.0 (marked and unclaimed). The other 16 marked images were claimed by rules 20, 30 and 40 |

Result, `SIMULATED`, 12 images expiring:

- Rule 20: nightly-20261001
- Rule 30: build-1, build-2, build-3, build-4, build-5, build-6, build-7
- Rule 100: v2.1.0, v2.2.0, v2.3.0, v2.4.0

Survivors, 14: build-8, build-9, build-10, build-11, build-12, rc-0.1, rc-0.2,
rc-0.3, rc-0.4, v2.5.0, hotfix-2.3.1, nightly-20261008, nightly-20261015, latest.

This matches ECR's own `GetLifecyclePolicyPreview` output for the same fixture.
Common wrong answers, each caused by skipping a step above:

- Listing rc-0.1 to rc-0.4 and build-8 to build-12 as expiring under rule 100
  (skipped the claim rule in step 4).
- Listing only the four v2.x images or only nine images (forgot that rule 100's
  count runs across all 26 images, or dropped a rule).
- Listing only one image (treated the policy as a single rule).

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

## 6. Documentation URLs

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
- Lifecycle events in CloudTrail (`PolicyExecutionEvent`, `DryRunEvent`):
  https://docs.aws.amazon.com/AmazonECR/latest/userguide/logging-using-cloudtrail.html
