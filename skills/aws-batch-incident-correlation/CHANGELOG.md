# Changelog

## 1.0.0 - 2026-10-24

First public release in this repository. Content as of 0.4.0 below; agent types renamed to the API values, author and summary metadata added, and account IDs in eval outputs replaced with `111122223333`.

## 0.4.0 — unreleased

Cut from five rules to one. The 0.3.0 `functional` run at three iterations showed only the
cross-`JobQueue` rule produced a decisive, repeatable improvement; three rules made no
measurable difference (and the quality judge preferred the base agent), and one regressed.
Acting on that evidence:

- **Kept** the cross-queue rule: an alarm scoped to one `JobQueue` must not be linked to, or
  made primary for, incidents on another queue; compare the dimension first.
- **Dropped** "require a shared mechanism", "silent-failure alarm is not a stall" and
  "distinguish cold-start from stall" — the base agent already reasons through these, so they
  added cost and latency without changing outcomes.
- **Withdrew** "poller repeats are one incident" — it regressed the answer (1/3 vs 3/3) and
  its trigger metric was inconsistent. Preserved in git history in case a later eval finds a
  way to make it help.

Consequences: the frontmatter description is narrowed to the cross-queue scenario (so it
triggers on the right prompts and not others); the skill needs no extra IAM now that the ASG
checks are gone; `evals.json` is reduced to the two cross-queue evals plus the RDS negative
control. Re-validated — structure 12/12, best-practices passing, functional shows the
retained rule winning with the negative control silent; see README.md and the committed
`evals/` reports.

Triage efficacy remains unproven for the same structural reason as before: the harness has no
triage task type, so `Incident Triage` is unreachable and every measurement was taken in a
chat context.

## 0.3.0 — unreleased

Re-ran `functional` at `--iterations 3` (33/33 iterations successful). **The result was worse
than the one-iteration run and reversed a conclusion.**

- Cross-`JobQueue` rule: decisive win, 3/3 vs 0/3 expected output, 8/9 vs 2/6 assertions.
- "Shared mechanism", "silent-failure not a stall", "cold-start vs stall": no difference — the
  base agent already reasons correctly — and the quality judge preferred the *without-skill*
  answer on all three.
- "Poller repeats, earliest primary": **inverted** from an apparent one-iteration win to 1/3
  vs 3/3 expected output and 5/9 vs 9/9 assertions, with an inconsistent `trigger: 0/3`.

The earlier claim that value "concentrates in Rules 2 and 5" was wrong and was corrected.
Recommendation recorded to cut to the cross-queue rule alone — executed in 0.4.0.

## 0.2.0 — unreleased

Added a "verify before finalising a decision" checklist, addressing the BP-17 warning that
the skill produced linking decisions with no instruction to re-check them. Best-practices
went to 3/3 iterations at 100%.

Rewrote `evals.json` against the real schema (root object with `skill_name`/`evals`,
`task_type`, `should_trigger`, LLM/regex assertions), and added a `should_trigger: false`
negative control.

First functional run recorded — mixed, later superseded by the 0.3.0 three-iteration run.

## 0.1.0 — unreleased

Initial draft. Five triage correlation rules for AWS Batch, derived from two observed
mis-correlations in a reproduction environment.
