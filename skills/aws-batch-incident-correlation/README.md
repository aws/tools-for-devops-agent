# aws-batch-incident-correlation

> This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

A focused correlation guardrail for AWS Batch incidents, applied during the triage phase: it
stops the agent conflating incidents that belong to different job queues.

## The problem

DevOps Agent triage correlates a new incident against active investigations within a
look-back window, using factors including component similarity, region and timing. For most
services that works well. For AWS Batch it over-links, because a burst of jobs will fail
together — in time proximity, in the same region, sometimes across several queues — while
having unrelated causes.

The specific, repeatable failure this skill fixes, observed in a reproduction environment: an
alarm dimensioned on one job queue, about a job that had **already completed**, became the
primary investigation for a stuck-queue incident plus six job failures on a **different**
queue. The stated reasoning claimed they were on "the same queue" — which was never checked
against the alarms' `JobQueue` dimensions, and was false.

## What this skill does

One rule: **an alarm scoped to one `JobQueue` must not be linked to, or made the primary
for, incidents on another queue.** Compare the `JobQueue` dimension of both incidents first;
if they differ, schedule the new one separately. Shared account, region or compute
environments are not a shared cause.

## Why only one rule

This skill started with five rules. A `skill-eval functional` run at three iterations
(`us.anthropic.claude-sonnet-5`) measured each against the base agent and the result was
unambiguous: only the cross-queue rule earned its place.

| Original rule | 3-iteration verdict | Kept? |
|---|---|---|
| No cross-`JobQueue` primary | decisive win: 3/3 vs 0/3 expected output, 8/9 vs 2/6 assertions | **yes** |
| Require a shared mechanism before linking | no difference — base agent already does this | dropped |
| Silent-failure alarm is not a stall signal | no difference | dropped |
| Distinguish cold-start from stall via ASG activity | no difference | dropped |
| Poller repeats are one incident, earliest primary | **regression** — 1/3 vs 3/3 with the skill | withdrawn |

The three no-difference rules did not just fail to help — the quality judge preferred the
*without-skill* answer on all three, and each with-skill run cost ~8s and ~$0.07 against the
base agent's near-zero. Carrying them made the skill slower, more expensive and no better.
Rule 5 actively made the answer worse and its trigger metric was inconsistent
(`trigger: 0/3` yet differentiated output); it is withdrawn until understood, not silently
kept. A one-rule skill is also cheaper to load and far easier to justify at review.

The dropped content is preserved in git history (`CHANGELOG.md` points at the five-rule
version) in case a future eval shows a way to make any of it pull its weight.

## Agent type

`INCIDENT_TRIAGE` only. Targeting it narrowly keeps it out of RCA and on-demand context,
where it would consume tokens without being relevant.

## Prerequisites

None beyond the agent's default read access — the rule reasons over the `JobQueue` dimension
already present on the incidents being correlated. No extra IAM is required.

## Validation status

The latest `best-practices` and `functional` reports are committed under `evals/`;
`structure` reports are deterministic and regenerable, so they are not committed.

| Tier | Result |
|---|---|
| `structure` | 12/12 checks, 100%, passed |
| `best-practices` | 2/2 iterations passed, 100% score, 100% consistency |
| `functional` | 15/15 iterations successful; both cross-queue evals win; control silent |

Functional results at `--iterations 3`, judged by `us.anthropic.claude-sonnet-5`, after the
cut:

| Eval | Trigger | Expected output (with/without) | Assertions (with/without) |
|---|---|---|---|
| `correlation-no-cross-queue-primary` | 3/3 | 3/3 · **1/3** | 9/9 · **1/9** |
| `correlation-two-queue-alarms-not-one-incident` | 3/3 | 3/3 · **0/3** | 9/9 · **1/3** |
| `unrelated-rds-failover-question` | 3/3 correctly silent | — | — |

Both positive evals now win decisively where the base agent mostly fails, and output
consistency favours the skill (2.83 vs 2.33). The negative control asks about RDS Multi-AZ
failover — unrelated to Batch — and the skill stays silent, so the narrow description does
not cause over-triggering.

Two honest notes from the report:

- One assertion on the second eval (*"does not assert the two alarms are on the same
  queue"*) is flagged `always_passes` — the base agent does not make that specific error
  unprompted, so it is a regression guard rather than a discriminator. Left in deliberately;
  the two discriminating assertions per eval carry the win.
- On `correlation-no-cross-queue-primary` the separate quality judge preferred the
  without-skill answer on the 1 of 3 pairs it could score (the other 2 were skipped because
  the without-skill run failed the expected-output gate). Reported as measured; the
  expected-output and assertion tallies favour the skill.

## Efficacy in triage is still unproven

The measurements were taken in a **chat** context, and that is not where this skill operates.

The eval harness maps `task_type` to agent type — `chat` → `CHAT`, `investigation` →
`INCIDENT_RCA` — and overrides the frontmatter at upload. There is **no triage task type**,
so `INCIDENT_TRIAGE` is unreachable by the harness and the results measure whether the agent
can *state* the rule, not whether triage *acts* on it.

A chat eval asks "should these be linked?", which invites careful reasoning. Triage makes an
automated linking decision against active investigations inside a look-back window without
being asked to reason it through. Passing the chat form does not establish the triage
behaviour changes. Proving that needs two incidents on different queues arriving inside the
look-back window, with the skill Active and then Inactive, comparing the actual triage
decisions. That scenario is reproducible but has not been run. **Do not present this skill as
a proven fix for over-linking until it is.**
