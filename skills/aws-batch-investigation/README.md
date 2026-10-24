# aws-batch-investigation

> This skill is sample code, not intended for production use without additional review and testing. Users should validate in a non-production environment first.

Investigation procedures for AWS Batch job queues, compute environments and job failures.

## What this enriches

Without this skill, a Batch investigation tends to make four mistakes:

1. **Trusting `status`.** Batch can return `status: SUCCEEDED` with `exitCode: 0` for a job
   it terminated itself on an out-of-memory condition or on its own attempt timeout. An
   investigation that reads only `status` reports the job as healthy.
2. **Expecting ordered compute environments to fail over.** They do not. A compute
   environment that cannot launch instances pins the queue behind it.
3. **Reporting the declared `retryStrategy.attempts` as the effective retry count.** An
   `evaluateOnExit` rule set that matches only host-level failures gives an application
   error exactly one attempt regardless of the declared budget.
4. **Judging fair-share allocation from a single snapshot,** which can show the opposite of
   the run's overall behaviour.

The skill supplies the field-level checks, the diagnostic signature for each case, and an
explicit list of conclusions not to draw.

## Agent types

`CHAT`, `INCIDENT_RCA`.

Not targeted at `INCIDENT_TRIAGE` — correlation behaviour is a separate concern, covered by
the companion `aws-batch-incident-correlation` skill.

## Prerequisites

Attach `references/iam-policy.json` to the IAM role associated with your Agent Space,
replacing `REGION` with the region your Batch resources run in.

Minimum for silent-failure detection alone:

- `batch:ListJobs`
- `batch:DescribeJobQueues`

Additionally for the capacity and job-configuration steps:

- `batch:DescribeComputeEnvironments`
- `batch:DescribeJobs`
- `batch:DescribeSchedulingPolicies`
- `autoscaling:DescribeAutoScalingGroups`
- `autoscaling:DescribeScalingActivities`

`batch:DescribeJobs` is **not** covered by `batch:List*` and is commonly missing from
read-only monitoring roles. The skill instructs the agent to report its absence as a gap
rather than guess around it.

## Evidence

Every claim in this skill and its references comes from direct observation in a
purpose-built AWS Batch reproduction environment. The specific measurements are stated
inline in the reference files, with the configuration that produced them, so a reader can
tell a general property of Batch from an artefact of one setup.

Highlights:

- Three distinct silent-failure modes observed, including one — silent timeout — where
  `container.reason` is null, so an OOM detector alone misses it entirely.
- Ordered-compute-environment behaviour measured over a 45-minute stall with per-ASG
  `MaxSize` and activity history recorded for all three compute environments.
- `maxvCpus` observed exceeded twice.
- Fair-share allocation measured both at early contention and across a whole run, which
  disagree.

## Known gaps

Two checks are described in the skill but need permissions that a read-only monitoring role
often lacks, and that this skill deliberately does **not** ask for:

- `batch:DescribeJobDefinitions` — would settle whether an invalid container command comes
  from the job definition or from a submit-time override.
- `logs:GetLogEvents` on `/aws/batch/job` — would confirm the container's own error output.

Each is a real gap observed during an investigation. They are listed here rather than
granted pre-emptively, so an operator can decide with evidence in hand.

## Unverified

Whether `batch:DescribeJobs` supports resource-level ARNs. The policy uses `Resource: "*"`
narrowed by an `aws:RequestedRegion` condition, which is the correct practical scoping
either way: job IDs are unpredictable, so a monitoring role cannot enumerate future job
ARNs.

## Validation status

All three `skill-eval` tiers pass. The latest `best-practices` and `functional` reports are
committed under `evals/`; `structure` reports are deterministic and regenerable, so they are
not committed (see the workflow doc).

| Tier | Result |
|---|---|
| `structure` | 12/12 checks, 100%, passed |
| `best-practices` | 2/2 iterations passed, 100% score, 94% consistency |
| `functional` | 33/33 iterations successful; 6/6 trigger; skill wins every eval |

Functional results at **`--iterations 3`**, judged by `us.anthropic.claude-sonnet-5`:

| Eval | Trigger | Expected output (with/without) | Assertions (with/without) |
|---|---|---|---|
| `batch-ordered-ce-no-failover` | 3/3 | 3/3 · **0/3** | 15/15 · **2/15** |
| `batch-silent-timeout-field` | 3/3 | 3/3 · **0/3** | 6/6 · **0/4** |
| `batch-listjobs-carries-reason` | 3/3 | 3/3 · **0/3** | 6/9 · **1/9** |
| `batch-silent-failure-invariant` | 3/3 | 3/3 · **0/3** | 6/6 · 3/6 |
| `batch-fairshare-single-snapshot` | 3/3 | 3/3 · 2/3 | 8/9 · 4/9 |
| `unrelated-sqs-queue-question` | 3/3 correctly silent | — | — |

The skill meets the expected output on all five positive evals; the base agent meets it on
almost none. Output consistency also favours the skill overall: 2.74 with against 2.33
without, and on `batch-ordered-ce-no-failover` the base agent is outright `inconsistent`
(1.67) while the skill is `mostly_consistent` (2.67).

The negative control is deliberately sharp — it asks about SQS *queues*, since "queue" is a
Batch trigger word. The skill stayed silent in all three iterations, so the broad description
does not cause over-triggering.

### What raising iterations changed

At `--iterations 1`, `batch-listjobs-carries-reason` failed its expected-output judgement.
At three iterations it passes 3/3. That was a single-run artefact, and it is the reason the
one-iteration numbers should not be quoted.

### What the first functional run changed

The initial run exposed two real defects, both now fixed:

1. **Three of six evals never triggered** — `trigger: 0/1`, runtime 0s, cost $0.00. The
   skill was not loading at all, so those answers came from the base agent. The frontmatter
   description covered investigation-style phrasing but not questions about API choice,
   permissions, retry semantics or fair-share interpretation. Widening it took triggering
   from 3/6 to 6/6.
2. **Several assertions passed without the skill**, which inflates apparent value rather
   than measuring it. The harness flags these as `always_passes`. They were pruned.

One eval was **deleted outright**: `batch-retrystrategy-effective-attempts`. All four of its
assertions passed without the skill — base Sonnet already reasons correctly about
`evaluateOnExit` overriding `attempts`. Keeping it would have implied value the skill does
not add. The `retryStrategy` guidance remains in SKILL.md because it is correct and useful
in an investigation, but it is not a differentiator and is not claimed as one.

### Caveats

- The harness maps `task_type` to agent type (`chat` → `CHAT`, `investigation` →
  `INCIDENT_RCA`) and **overrides the frontmatter at upload**. These results therefore
  measure the skill loaded into a chat agent, not the `CHAT, INCIDENT_RCA`
  targeting declared in SKILL.md.
- One assertion still never passes in either variant: *"the scan works with ListJobs
  permission alone"* on `batch-listjobs-carries-reason`. The eval as a whole wins 6/9 against
  1/9, so the point about ListJobs carrying `container.reason` does land — but the permission
  consequence does not. Either the assertion is too strict or SKILL.md needs to state it more
  plainly. Unresolved.
- On `batch-fairshare-single-snapshot` the separate quality judge preferred the without-skill
  answer on 2 of 3 pairs, while assertions favoured with-skill 8/9 against 4/9 and expected
  output 3/3 against 2/3. Reported as measured rather than reconciled.
- The skill costs real tokens: roughly 7-9s and $0.06-0.08 per invocation against near-zero
  for the base agent on questions it already answers. Worth it where the gap is large, and
  the reason `Generic` targeting was avoided.
