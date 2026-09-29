# Testing record

Two independent harnesses cover this skill:

| Harness | What it checks | Cost |
|---|---|---|
| `evals/check-consistency.sh` | Maintainer-only deterministic validation of the package itself. Never runs in the agent and is excluded from the upload. | None |
| `devops-agent skill-eval` | Structure, best practices, and functional behaviour against a real agent, per the [Agent Skills spec](https://agentskills.io/specification). | `structure` free; `best-practices` uses Bedrock; `functional` provisions agent spaces |

Re-run both after any change to `SKILL.md`, the runtime references, or the check manifest.

## Maintainer-only deterministic validation

```bash
bash evals/check-consistency.sh
```

Verifies generated-source freshness, 369 canonical row schemas, exact IDs/counts, 49 discovery
areas, remediation ownership, full/targeted routing contracts, false gates, a negative QA repair
probe, one-FAIL shard selection, CP scorecard/query separation, links, the `evals.json` schema,
and package invariants including the upload file count.

Regenerate the derived manifest and remediation index only during local maintenance:

```bash
python3 evals/generate-runtime-indexes.py --write
```

The consistency check invokes the generator in `--check` mode and fails on drift. Neither command
is a runtime skill step.

## skill-eval

```bash
# The CLI requires Python 3.10+ despite its README saying 3.9+: eval/bedrock.py uses
# PEP 604 (`str | None`) at runtime, which raises TypeError on 3.9.
python3.13 -m venv .venv && .venv/bin/pip install -e ./sdk -e ./cli   # in DevOpsAgentSDKCLI

.venv/bin/devops-agent skill-eval structure       <skill-dir>
.venv/bin/devops-agent skill-eval best-practices  <skill-dir> --aws-profile <profile>
.venv/bin/devops-agent skill-eval functional      <skill-dir> --iterations 1 --aws-profile <profile>
```

Each run writes a versioned report under `evals/<tier>/`. Those reports are excluded from the
upload payload.

### Results

| Tier | Result | Notes |
|---|---|---|
| structure | 12/12 (100%) | STRUCT-01…12 |
| best-practices | 92% / 91% / 82%, consistency 94% | one accepted deviation (BP-04) and one harness defect, both below |
| functional | serial: 22/22 skill loaded, 83/83 assertions | run it serially; one parallel invocation loaded the skill in only 13/22 |

### Serial run — the trustworthy path

Use the driver rather than one big invocation:

```bash
python3 evals/run-functional-serial.py --cli /path/to/DevOpsAgentSDKCLI/.venv/bin/devops-agent
python3 evals/run-functional-serial.py --cli ... --only eks-scenario-pending-pods-taint
```

Each eval runs in its own invocation, so at most two agent spaces exist at once. All 22 take
roughly 50 minutes. Reports land in `evals/functional/serial/<eval-id>/` with a `summary.json`.

Latest serial results: the skill loaded in **22/22** runs, expected output **21/22** (the smoke
test declares `should_trigger: false`, so it has none), and **83/83** assertions pass. The same
suite in one parallel invocation loaded the skill in only 13/22 — see the activation race below.

| Eval | Trigger | Expected output | Assertions |
|---|---|---|---|
| `eks-review-smoke-test` | correctly no-trigger | n/a | n/a |
| `eks-review-no-runtime-files` | ok | passed | 4/4 |
| `eks-review-two-phase-model` | ok | passed | 3/3 |
| `eks-review-nine-pillars` | ok | passed | 3/3 |
| `eks-review-read-only-contract` | ok | passed | 4/4 |
| `eks-review-cluster-confirmation-gate` | ok | passed | 4/4 |
| `eks-review-conditional-checklists` | ok | passed | 4/4 |
| `eks-scenario-pending-pods-taint` | ok | passed | 5/5 |
| `eks-scenario-oomkilled-not-leak` | ok | passed | 4/4 |
| `eks-scenario-logging-disabled-na-not-pass` | ok | passed | 5/5 |
| `eks-scenario-429-workload-low-informational` | ok | passed | 4/4 |
| `eks-scenario-missing-pdb-severity` | ok | passed | 4/4 |
| `eks-scenario-403-authz-not-authn` | ok | passed | 4/4 |
| `eks-scenario-healthy-no-invented-findings` | ok | passed | 3/3 |
| `eks-scenario-false-gates-no-load` | ok | passed | 4/4 |
| `eks-scenario-tool-unavailable-stop` | ok | passed | 4/4 |
| `eks-scenario-aws-api-denied-na` | ok | passed | 4/4 |
| `eks-scenario-transient-ledger-final-response` | ok | passed | 5/5 |
| `eks-scenario-full-vs-targeted-routing` | ok | passed | 3/3 |
| `eks-scenario-control-plane-20-rows` | ok | passed | 4/4 |
| `eks-scenario-qa-failure-blocks-finalization` | ok | passed | 4/4 |
| `eks-scenario-one-fail-one-shard` | ok | passed | 4/4 |

No eval requires live cluster access, so a full run needs no `--eks-clusters-file` and writes
nothing to any cluster. It is 44 agent spaces at `--iterations 1`.

### Skill-activation race on large parallel runs

The full 22-eval run completed cleanly — 44/44 iterations, zero failures — but only **13 of 22**
with-skill runs actually had the skill loaded. The other 9 report
`Skill 'aws-eks-operations-review' was NOT triggered ... skill_loads_found: 0`, one of them with
the agent answering *"That skill isn't one I have direct access to"* while loading
`discovering-topology` instead. Those 9 scores measure the skill's absence and must not be read as
skill quality: `eks-scenario-pending-pods-taint` scored 0/5 there against 5/5 in an isolated run of
the identical prompt, and `eks-review-cluster-confirmation-gate` scored 0/4 against passing
earlier.

The same evals trigger reliably when only two or three run at once, so this looks like the
uploaded asset not yet being active when the chat fires, or throttling, when ~44 spaces are
provisioned concurrently. Before trusting a full-run number:

- Check each with-skill run's `tests.trigger.result` and discard any run with `skill_loads_found: 0`.
- Prefer the default `--iterations 3` over 1, so a single bad activation cannot define a score.
- Small subsets remain the reliable way to evaluate one behaviour.

Restricted to the 13 runs where the skill was actually loaded: expected output passed 12/13, and
assertions passed 40/52 (77%).

Record the date and model when re-running; scores move with the judge model. Watch the
"assertions to rewrite" section as closely as the scores: `always_passes` means the assertion is
answerable without the skill, `always_fails` means the assertion or the skill needs work, and
`skill_regression` usually means a negation-blind regex.

### BP-04 — accepted deviation

BP-04 requires a markdown link in the body for **every** file under `references/`. This package has
99 of them, which is roughly 6.2 KiB of link text and would take `SKILL.md` to about 18 KiB against
the 12 KiB ceiling `check-consistency.sh` enforces — around 1.6K extra tokens on every activation.
It also conflicts with the guard that keeps `references/docs/*.md` out of the body except
`minimum-rbac.md`, and satisfying it would un-skip BP-05, which then demands a load condition on
each of the 99 links.

BP-04 and BP-03 pull against each other at this size: BP-03 rewards pushing detail into
`references/` and resolving it at runtime, which is exactly how the pillar definitions and the 52
remediation shards are reached (through `check-manifest.md` and `remediations/index.md`). That
indirection is what keeps the active reference set inside the 18K-token target.

The deviation is therefore intentional. Revisit it only alongside a consolidation of
`references/` into fewer, larger files.

### Known harness defect — gating tests answered `warning`

`BEST_PRACTICES_PASSING_SCORE` is 100, and gating tests accept only `passed`/`failed`
(`ALLOWED_RESULTS`). When the judge answers `warning` on a gating test anyway — which the prompt
explicitly forbids at `best_practices_prompts.py:810` — the runner records an error that caps the
iteration. Observed on BP-01 in one run and BP-12 in another, so it is not tied to a single test.
Treat "0/3 iterations passed" as unreliable and read the per-test table instead.

## evals.json

`evals/evals.json` follows the skill-eval functional schema: a root object with `skill_name` and
`evals`, each case carrying `id`, `task_type`, `prompt`, and `should_trigger`. Regenerate it from
the generator rather than editing it by hand:

```bash
python3 evals/convert-evals.py --write
```

Three constraints are baked into that generator, each learned from a real run:

1. **No fixture upload.** The runner cannot attach `evals/files/*.json` as discovery evidence, and
   the skill refuses to grade from pasted JSON — discovery runs only through `use_kubectl` and every
   verdict needs observed evidence. Asking for graded verdicts over an inline inventory fails by
   contract, not by defect. The false-positive scenarios quote a short evidence line and ask what
   the grading guards (FP1–FP12) require.
2. **Assertions must discriminate.** An assertion answerable from the prompt alone is reported as
   `always_passes` and measures nothing. The original fixture embedded `correct_root_cause` and
   `incorrect_conclusions`, so any model read the answer straight back.
3. **No negation-blind regexes.** `match: absent` cannot see negation, so a correct answer that
   names a wrong conclusion in order to reject it ("this is not a scheduler failure") fails the
   check. Absent-regex is reserved for literals a correct answer never emits; everything else is a
   judged statement.

`evals/eval_queries.json` and `.skilleval.yaml` are read by nothing in this CLI — the yaml's
`STR-016` predates the `STRUCT-01…12` scheme. Keep them only for whatever other harness consumes
them.

## Package limits

The service rejects a skill zip containing more than **100 files**, counting what
`devops_agent_sdk.skills.upload` includes: the allowed extensions minus `README.md`,
`CHANGELOG.md`, `.skilleval.yaml`, `evals/`, `scripts/`, and `.claude/`. Note it does **not**
exclude other root-level documents.

This package sits at exactly 100 (`SKILL.md` plus 99 references), so **adding any reference file
breaks upload** until `references/` is consolidated. A stray root-level report previously pushed it
to 101 and every upload failed with `Zip validation failed: Zip contains 101 files`, while
`check-consistency.sh` reported a compliant payload because its exclusion list did not match the
uploader's. That check now mirrors the uploader and prints the remaining headroom.

`SKILL.md` itself must stay within 8–12 KiB, and the active reference set within the 18K-token
target. Both are enforced by the consistency check.

## Live-run validation (non-production cluster)

Confirm that the agent:

1. Attempts all 49 discovery areas through `use_kubectl` and retains only bounded projections.
2. Loads one canonical unit definition at a time.
3. Adds every completed unit's exact rows and FAIL inputs to the transient ledger before loading
   the next unit.
4. Loads remediation references only after FAIL IDs are known.
5. Produces all 20 Control Plane rows and keeps CP query IDs separate from scorecard IDs.
6. Runs QA and blocks finalization on any missing area, ID, gate, source attempt, or FAIL block.
7. Delivers the complete report with every mandatory section present, in contract order.
8. Creates no inventory JSON, review-state sidecar, report file, disk checkpoint, or Amazon S3 object.
9. On a 500+ pod test cluster, avoids whole-cluster pod JSON and uses scoped projections.

Where the runtime delivers through a cumulative artifact assembled by ordered appends, check the
artifact's **final state** holds every section — intermediate versions are transport, not parts.

## Context-budget measurement

Record actual prompt/input/output token usage per state during the non-production run. The target
remains 45K–70K total tokens for a medium full review, with only 8K–18K of skill/reference material
active at once. Do not claim this target until runner telemetry confirms it.
