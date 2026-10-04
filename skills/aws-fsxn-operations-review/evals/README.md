# Evaluations — aws-fsxn-operations-review

This directory holds the evaluation inputs for this skill and is where the DevOps Agent
`skill-eval` tool writes its recorded results.

## Inputs (committed)

- `evals.json` — functional eval definitions (prompts, expected output, `should_trigger`, and
  assertions) following the skill-eval `evals.json` schema.
- `additional-permissions.json` — the read-only `fsx` / `cloudwatch` / `backup` / `ec2` permissions
  the review needs beyond the default DevOps Agent role, supplied to the functional test.

## Running the evaluation

Use the DevOps Agent SDK/CLI skill-eval tool (see the Community Hub **Quality & Security** tab):

```bash
# Static structure checks (STRUCT-01…12) — no AWS account needed
devops-agent skill-eval structure ./skills/aws-fsxn-operations-review

# Best-practices checks (BP-01…17) — needs Bedrock access
devops-agent skill-eval best-practices ./skills/aws-fsxn-operations-review --aws-profile <profile>

# Functional checks — runs the agent with and without the skill against evals.json
devops-agent skill-eval functional ./skills/aws-fsxn-operations-review --aws-profile <profile>
```

## Results (generated)

The tool creates and populates these subdirectories; commit the generated results alongside the
inputs so reviewers can see the recorded run:

- `structure/structure-tests-results-*.json`
- `best-practices/benchmark.json` and `best-practices/iteration-*/best-practices-tests-results.json`
- `functional/benchmark.json`, `functional/_metadata.json`, and
  `functional/iteration-*/<eval>/{with-skill,without-skill}/functional-tests-results.json`

> The skill must pass all **Gate** structure and best-practices tests, and the functional
> `quality.comparison.winner` must be `with_skill`, before a maintainer review.
