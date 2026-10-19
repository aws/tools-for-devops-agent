# Local validation repo — datalake-access-analyzer

This is a **local mirror** of the PR contents for `aws/tools-for-devops-agent`. It
exists to validate the file layout, JSON, and skill structure locally **before** the
real fork + push. It is not the upstream repo and nothing here is pushed anywhere.

## What it mirrors

The PR adds one directory:

```
skills/datalake-access-analyzer/
├── SKILL.md                   # frontmatter + 7-step methodology
├── README.md                  # overview, prerequisites, usage, limitations
├── references/
│   └── permission-chain.md    # per-layer API + condition detail (doc-cited)
└── evals/
    └── evals.json             # hand-written eval definitions (5 scenarios)
```

## Validation performed

Run `./validate.sh` to re-check. It confirms:

1. All four shippable files are present in the correct layout.
2. `evals/evals.json` is valid JSON and carries exactly 5 scenarios.
3. `SKILL.md` is at or under the 500-line contribution limit.
4. No internal pattern numbers / internal references leaked into shipped files.

## When you do the real PR

1. Fork `aws/tools-for-devops-agent`, branch `feature/datalake-access-analyzer`.
2. Copy `skills/datalake-access-analyzer/` into your fork.
3. Run the internal skill evaluation tool; commit the generated `evals/` result
   subdirectories.
4. `git push origin feature/datalake-access-analyzer` and open the PR using
   `../PR-DRAFT.md` as the body.

See `../PR-DRAFT.md` and `step3-testkit/TEST-EVIDENCE-2026-10-18.md` for full context.
