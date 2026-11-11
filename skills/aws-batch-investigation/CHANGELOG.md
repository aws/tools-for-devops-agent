# Changelog

## 1.0.0 - 2026-10-24

First public release in this repository. Content as of 0.4.0 below; agent types renamed to the API values, author and summary metadata added, and account IDs in eval outputs replaced with `111122223333`.

## 0.3.0 — unreleased

Widened the frontmatter `description` after a functional eval showed the skill failing to
trigger on three of six evals. It covered investigation-style phrasing but not questions
about API choice, IAM permissions, retry semantics or fair-share interpretation. Triggering
went from 3/6 to 6/6.

Pruned assertions the harness flagged `always_passes`, and deleted the
`batch-retrystrategy-effective-attempts` eval entirely: all four of its assertions passed
without the skill, so it measured base-model competence rather than skill value. The
`retryStrategy` guidance stays in SKILL.md because it is correct and useful, but it is no
longer claimed as a differentiator.

Added a `should_trigger: false` negative control asking about Amazon SQS queues — chosen
because "queue" is a Batch trigger word. The skill correctly stays silent.

All three eval tiers now pass; see README.md for the numbers and the remaining caveats.

## 0.2.0 — unreleased

Fixes from the first `best-practices` run, which failed 0/3 iterations at 71-85%:

- Converted reference mentions from backticked paths to markdown links, each stating when to
  load it (BP-04, and the BP-05/BP-06 checks that depend on it).
- Converted the ordered `## Step N` procedure to checkbox checklists, which BP-16 requires
  for procedural skills. This was the only check failing in all 3 iterations.
- Added a "verify before reporting" checklist, addressing the BP-17 warning that the skill
  produced reports with no instruction to self-check them against evidence.

Result: 3/3 iterations passed at 100%, consistency 100%.

## 0.1.0 — unreleased

Initial draft. Content derived from direct observation in an AWS Batch reproduction
environment; see README.md for scope of evidence.

- Silent-failure invariant and the three observed modes.
- Ordered compute environment behaviour and the `MaxSize` 0 diagnostic.
- `SpotMaxPriceTooLow` stall signature.
- `maxvCpus` is not a hard ceiling.
- `minvCpus` idle capacity check.
- `retryStrategy` / `evaluateOnExit` effective-attempts trap.
- Fair-share single-snapshot trap.
- Least-privilege IAM policy, split so silent-failure detection can be granted alone.

### Still outstanding

- Functional eval run at `--iterations 1` only; upstream default is 3.
- Parameterized CloudFormation/Terraform IAM template under `automation/`, which the
  upstream contribution guide requires at PR time.
- `batch-listjobs-carries-reason` fails its `expected_output` judgement despite winning
  2/3 against 0/3 on assertions.

## 0.4.0 — unreleased

Re-ran `functional` at `--iterations 3` (33/33 iterations successful), replacing the
single-measurement results. All six evals trigger 3/3, the skill meets the expected output on
all five positive evals where the base agent meets almost none, and output consistency
favours the skill overall (2.74 against 2.33).

Raising iterations corrected a single-run artefact: `batch-listjobs-carries-reason` failed its
expected-output judgement at one iteration and passes 3/3 at three. The one-iteration numbers
should not be quoted.

Added `automation/cloudformation/aws-batch-skills-iam.yaml`, the parameterized least-privilege
IAM stack the upstream contribution guide requires, with a `PermissionTier` parameter so
silent-failure detection can be granted without `batch:DescribeJobs`.

Still outstanding: one assertion ("the scan works with ListJobs permission alone") never
passes in either variant, and the quality judge prefers the without-skill answer on
`batch-fairshare-single-snapshot` while assertions and expected output favour with-skill.
