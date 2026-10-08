# Project Conventions

This repository consolidates open-source tools for AWS DevOps Agent — skills, custom agents, and MCP servers, plus supporting infrastructure templates. Follow these conventions when contributing. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution workflow.

## Key References

- [Agent Skills spec](https://agentskills.io/home) — the open standard this project follows for skill structure
- [AWS DevOps Agent Skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) — official AWS docs on creating and uploading skills
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html) — official AWS docs on custom agents
- [AGENTS.md specification](https://agents.md/) — the open standard for custom agent definitions
- [Model Context Protocol](https://modelcontextprotocol.io) — the open standard for MCP servers
- [Connecting MCP servers to DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html) — official AWS docs on registering MCP servers

## Repository Structure

```
tools-for-devops-agent/
├── README.md                 # Project overview with skills/agents/MCP tables
├── CONTRIBUTING.md           # Contribution guidelines
├── llms.txt                  # Structured repo overview for AI tools
├── .gitignore                # Root-level ignores
├── cloudformation/
│   └── devops-agent-skill-policies.yaml  # IAM policies skills require
├── docs/                     # GitHub Pages (mkdocs) documentation site
├── skills/
│   ├── .gitignore            # Allowlist for DevOps Agent supported extensions only
│   └── <skill-name>/
│       ├── SKILL.md          # Required: main skill instructions with frontmatter
│       ├── README.md         # Skill documentation (purpose, prompts, upload instructions)
│       ├── CHANGELOG.md      # Version history
│       ├── evals/            # Required: skill evaluation tool output (generated)
│       │   ├── evals.json
│       │   ├── structure/    # structure-tests-results-v<N>.json
│       │   ├── best-practices/  # v<N>/benchmark.json, v<N>/iteration-<n>/
│       │   └── functional/   # v<N>/benchmark.json, v<N>/iteration-<n>/
│       ├── assets/           # Optional: images, diagrams, data files
│       └── references/       # Optional: supplementary reference docs
├── custom-agents/
│   └── <agent-name>/
│       ├── SYSTEM_PROMPT.md  # Required: the agent's system prompt
│       ├── README.md         # Agent documentation
│       └── CHANGELOG.md      # Version history
└── mcp/
    └── <server-name>/
        ├── README.md         # Server documentation and deployment steps
        └── ...               # Server implementation and deployment assets
```

## Writing Skills

Skills live under `skills/` and should follow both the [Agent Skills spec](https://agentskills.io/home) best practices and [AWS DevOps Agent best practices](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html). Skills are the most common contribution type; the guidance below is the most detailed for that reason.

### SKILL.md Requirements

- Must include valid frontmatter with `name` and `description` fields.
- `name`: lowercase letters, numbers, and hyphens only (max 64 characters, no leading/trailing hyphens).
- `description`: written from the agent's perspective, specifying when and why the skill should activate. Be specific about scenarios, services, error types, or symptoms that should trigger the skill. Minimum 100 characters recommended.
- Instructions should be step-by-step, actionable, and include decision trees for different scenarios.
- Include expected outputs and success criteria.
- Reference specific AWS APIs, CLI commands, or tools the agent should use.
- Use tables for structured data (e.g., filtering strategies, relevance scoring).

### SKILL.md Frontmatter Example

```yaml
---
name: my-skill-name
description: Use this skill when investigating [specific scenarios].
  Activate when you observe [specific symptoms, error patterns, or conditions].
  This skill [what it does] by [how it does it] to [outcome].
metadata:
  author: github-username
  version: "1.0.0"
---
```

The `metadata` block with `author` and `version` fields is required. Initial version should be `"1.0.0"`.

### Skill Publishing Check

`.github/workflows/validate-skills.yml` runs `.github/scripts/validate_skills.py` on every pull request. The rules and their reasons are in the "Skill Publishing Rules" section of [CONTRIBUTING.md](../CONTRIBUTING.md).

- The rules live in `.github/scripts/skill_checks.py` as pure functions over an in-memory skill folder (`SkillTree` of `Entry(path, mode, data)`). `validate_skills.py` only reads Git objects, computes the merge base and reports. Keep rules out of the CLI so the conformance cases and unit tests exercise exactly what CI runs.
- Every skill is checked on every PR, because skills on `main` are published as one set. Errors from any skill fail; warnings print only for skills the PR touches.
- Skills are read from Git objects (`git ls-tree -r -z` plus `git cat-file --batch`), never the working tree, so modes are exact and a local run checks only committed changes.
- Rule data lives in `.github/scripts/skill-rules/` and the check fails closed (exit 2) when a file there is malformed: `agent-types.json`, `vocabulary.json` (dimension values; unknown values only warn), `published-files.json` (root names left out of the published set) and `conformance-cases.json`.
- The extension allowlist is not duplicated: it is parsed from the `!*.<ext>` lines of `skills/.gitignore`, read from the merge base, so a new extension takes effect only once its `.gitignore` change has merged.
- Like the repository's other checks, a PR runs its own copy of the script, rules and tests, so it could edit them to pass. Maintainer review of `.github/` changes (CODEOWNERS) and the post-merge run on `main` are the controls; don't describe any in-script measure as stopping a determined PR.
- With `--base-ref`, `check_history` compares each skill with its merge-base copy: no removed folders, no reuse of a path deleted in `main`'s first-parent history (`git log --first-parent --no-renames --diff-filter=D`, skipped with a warning on a shallow clone), and a higher version whenever `content_hash` of the published files changes. The hash function is pinned by the golden fixture under `content_hash` in `conformance-cases.json`, so any other implementation can prove it computes the same hash.
- Secrets in test fixtures are built at runtime (`"AKIA" + ...`) or stored as base64 in the conformance cases, so no file in the repository contains a literal key or invisible character.
- `conformance-cases.json` is a language-neutral contract: every tool that validates or publishes these skills must give each case's `expect` result. The script runs it before checking any skill and exits 2 on a mismatch. A rule change needs a matching case change in the same PR.
- Every rule applies to every skill; nothing is exempted. A rule that existing skills don't meet yet starts as a warning (missing `metadata.summary`, dimension values outside the vocabulary) and becomes an error after a cleanup PR brings every skill into line.
- Runtime agent types (`runtime_agent_types`): `metadata.agent_types` when set, otherwise the display values in `aws-devops-agent-skills.agent-types` mapped through `display_mapping` in `agent-types.json`, otherwise `GENERIC` (all agents), which warns. `display_mapping` must have one entry per display value in `vocabulary.json`; `null` means not agreed yet.
- Exit codes: 0 pass (warnings allowed), 1 a rule broken, 2 could not run. Never report a 2 as the PR's fault.
- PyYAML is the only dependency, pinned by every PyPI hash in `skill-rules/requirements.txt`; actions are pinned by commit SHA.
- Tests: `python3 -m unittest discover -s tests -v`.

### Skill README.md Structure

Each skill must have a README.md following this structure (see `skills/support-cases/README.md` as reference):

1. **Title** — skill name as heading
2. **Purpose** — what the skill does and why it's useful
3. **Key Capabilities** — bullet list of what the skill enables
4. **Prerequisites** — what's needed before using the skill (IAM permissions, service plans, etc.)
5. **Limitations** — known constraints or boundaries
6. **Agent Types** — which DevOps Agent types use this skill
7. **Uploading to AWS DevOps Agent** — zip command and upload steps
8. **How to Use This Skill** — sample prompts organized by agent type/use-case

### Changelog

Every skill must include a `CHANGELOG.md` tracking version history. Use semantic versioning:

```markdown
# Changelog

## 1.1.0

- Added backfill logic for missing data
- Improved error handling for API timeouts

## 1.0.0

- Initial version
```

### Evaluation Tests

Every skill should include evaluation test results using our skill evaluation tool. This tool isn't published in this repo yet — see the "Test Your Skill" section in [CONTRIBUTING.md](../CONTRIBUTING.md) for how to get a skill evaluated (AWS employees follow the internal guidelines; external contributors tag `@aws/tools-for-devops-agent-admins` on the issue or PR).

The only hand-written file under `evals/` is the top-level `evals.json` (the skill's eval definitions). **Everything else is generated by the skill evaluation tool** — contributors run the tool and commit its output. Each run is a new version (`v<N>`, one or more digits), and it's enough to commit the last version of each test type. The full shape the tool produces:

```
skills/<name>/evals/
├── evals.json                                        # hand-written: eval definitions
├── exemptions.json                                   # hand-written, optional: test-type exemptions
├── structure/
│   └── structure-tests-results-v<N>.json             # one file per run
├── best-practices/
│   └── v<N>/
│       ├── benchmark.json                            # scores for the run
│       ├── iteration-<n>/
│       │   └── best-practices-tests-results.json
│       └── cli_debug/                                # gitignored
└── functional/
    └── v<N>/
        ├── benchmark.json                            # scores for the run
        ├── evals.json                                # the evals this run executed
        ├── _metadata.json                            # run metadata
        └── iteration-<n>/
            └── <scenario-name>/                      # named from evals.json
                ├── with_skill/
                │   ├── functional-tests-results.json
                │   ├── outputs/journal_records.json  # committed: the run's agent journal
                │   ├── outputs/{classified_output,metadata}.json  # gitignored
                │   └── sdk_debug/                    # gitignored
                └── without_skill/                    # same shape, skill disabled
```

- `skills/.gitignore` excludes `cli_debug/` and `sdk_debug/` wholesale (debug traces from the eval tool and its SDK), plus `outputs/classified_output.json` and `outputs/metadata.json` (intermediate per-iteration artifacts). Don't add them back. `outputs/journal_records.json` is intentionally kept — it's the DevOps Agent journal for the run and serves as evidence of what the evaluation produced
- Only the last version of each test type belongs in git. The tool retains every run locally, which can reach tens of thousands of files and over a GB for a single skill
- `.github/workflows/validate-skill-evals.yml` (via `.github/scripts/validate_skill_evals.py`) checks, for each skill a PR touches: `evals/evals.json`; at least one `evals/structure/structure-tests-results-v<N>.json`; at least one complete `evals/best-practices/v<N>/` (`benchmark.json` + an `iteration-<n>/best-practices-tests-results.json`); and at least one complete `evals/functional/v<N>/` (`benchmark.json`, `evals.json`, and one `iteration-<n>/<scenario>/` holding both `with_skill/` and `without_skill/functional-tests-results.json`). Iteration numbers and scenario names are wildcards; the with/without pair must come from the same scenario directory
- Validation stops at that depth on purpose. `outputs/*`, `_metadata.json`, iteration counts, and scenario names vary by run and tool version and are deliberately unchecked — don't tighten them without re-checking recent runs of the eval tool first
- A skill that genuinely cannot produce one test type's results can commit `evals/exemptions.json` — `{"<test type>": {"reason": "..."}}`, keys `structure` / `best-practices` / `functional`. That type is then not checked but reported as a warning, so the check passes while staying visible. `evals.json` is never exemptable. The parser fails closed (bad JSON, unknown type, or empty `reason` grants nothing and is reported), and because the file is in the PR diff, exemptions go through normal review. Typical uses: limitations in accessing the skill evaluation tool, or an agent type its functional tests don't support yet. An exemption excuses the tool's results, not the testing — the PR should still carry manual with-skill / without-skill evidence for a maintainer to judge
- The `enforce-evals` label withdraws every exemption claimed by the PR's skills: each exempted type is checked as though the file were absent, and the claimed reason is reported as withdrawn so the log names what was rejected. This is what makes the label a complete lever — forcing the mode alone can't reach a PR that exempts all three types, because an exemption removes the violations whose severity the mode decides. `--strict` deliberately still honors exemptions; withdrawing is a per-PR judgement on a stated reason, not a repo-wide migration push
- Withdrawal is all-or-nothing per PR, by design: `withdraw_exemptions` is computed once from the label and passed to every skill in the run, so one label application refuses every exempted type on every touched skill — including a legitimate exemption sitting beside an unfounded one. There is no per-skill or per-type granularity; say so when a maintainer asks, rather than implying the label targets a single claim
- Contributors can run the check locally: `python3 .github/scripts/validate_skill_evals.py --skill <skill-name>`
- "At least one complete" version means an aborted run committed next to a good one is harmless, while a lone aborted run (e.g. one that never wrote `benchmark.json`) fails the check
- Enforcement is gradual. A skill is **enforced** if any of: its dir is absent on the base branch (the PR adds it); the base branch already has `evals/structure|best-practices|functional` for it; or the PR's own tree introduces one of those markers (so a migration can't land half-finished and fail the next person to touch the skill). Otherwise it's **legacy** — warnings only. Derived from the merge base plus the working tree, so a skill promotes itself to enforced as its migration lands; nothing to maintain by hand
- Two per-PR overrides sit in front of that, in order: the `enforce-evals` label forces enforcement on every skill the PR touches and withdraws their exemptions (a maintainer-only, per-PR `--strict` that also outranks `exemptions.json`; only triage/write can label, and automation never touches it), then `PRS_PREDATING_CHECK` — PRs already open when the check landed — makes every skill they touch legacy. A listed PR is still held to `was_migrated` and `now_migrated`: predating the check waives *producing* results, not deleting existing ones or landing half a migration. Don't reuse `needs-evals` as the enforce label; the labeler clears it on success, which would drop the decision
- `--strict` additionally enforces on unmigrated skills, making every PR that touches one a blocker, and overrides `PRS_PREDATING_CHECK`. It's a lever for *forcing* migration, not a cleanup step for afterwards — once all skills are migrated it does nothing. It does not withdraw exemptions
- Skills should achieve a passing score before being merged
- Run evaluations locally and test with DevOps Agent before submitting changes

## Writing Custom Agents

Custom agents live under `custom-agents/<agent-name>/` and pair a system prompt with the tools and skills the agent uses. See the [DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html) and the [AGENTS.md specification](https://agents.md/).

Each custom agent directory must contain:

- `SYSTEM_PROMPT.md` — the agent's system prompt. Structure it with clear sections (e.g., Goal, Approach, Constraints, Output). Reference any skills the agent relies on by name so it loads them at runtime.
- `README.md` — documents the agent's purpose, key capabilities, prerequisites (IAM permissions, support plans, required skills), step-by-step instructions for creating the agent in the DevOps Agent web app, how to execute it, and related links.
- `CHANGELOG.md` — version history using semantic versioning (same format as skills).

Test the agent by running relevant scenarios with and without it, multiple times, and compare output quality and consistency against asking DevOps Agent the same question via chat.

## Writing MCP Servers

MCP servers live under `mcp/<server-name>/` and connect the agent to external systems and data sources over the [Model Context Protocol](https://modelcontextprotocol.io). Review the [process for connecting MCP servers to DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html) before you build.

Server implementations vary (SAM applications, Lambda deployments, source packages, deploy scripts), so this directory is not held to a fixed file layout. At minimum, each MCP server directory must contain:

- `README.md` — documents what the server does, its tools, prerequisites and IAM scoping, and step-by-step deployment and registration instructions.
- `CHANGELOG.md` — version history (recommended, same format as skills).

Prefer running standard, pinned upstream server packages over forked code where possible, and enforce least-privilege IAM and read-only access by default. There is no MCP-specific evaluation tool yet — test the server manually and document how you validated it.

## Allowed File Extensions

Only these extensions are permitted inside **skill** directories (enforced by `skills/.gitignore` and the DevOps Agent upload validator). This constraint applies to skills because they are uploaded to DevOps Agent as zips; `custom-agents/` and `mcp/` are not subject to it:

.md, .txt, .json, .yaml, .yml, .xml, .csv, .tsv, .html, .htm, .png, .jpg, .jpeg, .gif, .svg, .webp, .pdf

## Disallowed Content

- `scripts/` directories are not supported by DevOps Agent.
- `.claude/` directories should not be committed (except CLAUDE.md).
- `.kiro/` directories should not be committed.
- `.DS_Store` and other OS files should not be committed.

## AWS Identifiers

**Redact real AWS identifiers before committing, rather than leaving it to either piece of tooling.** The repository is public and a commit is permanent — removing a value in a later commit does not remove it from the history. Replace an account ID with `123456789012` or `111122223333`, an instance ID with `i-0123456789abcdef0`, and an ARN by rewriting it whole, account and region and resource name together, since blanking the account field leaves the rest of it standing. Do the same for any other real resource name: a cluster, bucket, database, stack or role name describes the environment to a reader and cannot be told apart from an example by automation. See the "Redacting AWS Identifiers" section of [CONTRIBUTING.md](../CONTRIBUTING.md).

Neither piece of tooling is sufficient on its own:

- The skill evaluation tool's redaction pass rewrites the agent's own output and only that. A hand-written `evals.json` prompt is never touched; neither is the `_metadata.json` the harness writes at the root of each functional version directory, whose stack ARNs name the account the run used (gitignored for that reason). A third-party account inside a returned API payload has been observed passing through unredacted while the operating account in the same sentence was replaced.
- Agent output lands in three files per run: `journal_records.json`, `benchmark.json`, and each scenario's `functional-tests-results.json`, which quotes the output again as the evidence for every assertion. The same identifier usually appears in more than one, so check each rather than fixing the journal and assuming the rest followed.
- The check reports an account ID only where something proves it is one, so a green check means nothing was proved, not that nothing is there.

A pull request check (`.github/workflows/scan-aws-identifiers.yml`, running `.github/scripts/scan_aws_identifiers.py`) reports unredacted AWS identifiers and applies to every file in the repository, not only to skills. See the "Scanning for AWS Identifiers" section of [CONTRIBUTING.md](../CONTRIBUTING.md).

- An account ID is reported only when something proves it is one; twelve digits on their own are not evidence. Measured across the open pull requests, 54% of the twelve-digit runs on their added lines named no account — a `YYYYMMDDHHMM` datestamp in a resource name, the fractional or integer part of a decimal, a zero-padded counter. The scan therefore runs in two passes.
- **Pass one gathers evidence and reports nothing**, from exactly three sources: the account field of an [ARN](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html) (the fifth colon-separated field); an object key inside the `text` field of a `tool_summary` block's tool result, in a `journal_records.json` file, where `text` holds JSON as a string and DevOps Agent keys a per-account API result by account ID, so the key itself is the account; and the value of an `aws_account_id` field, in a `journal_records.json` file. The last two are fields of the DevOps Agent journal schema, which is why they are read only in that file name. Other spellings such as `AccountId` and `accountId` are deliberately not read. Pass one reads every changed file whole, so an ARN in an untouched part of a file still proves an account ID an added line names bare.
- **Pass two reports, on added lines only:** an ARN whose account field holds a non-allowlisted twelve-digit value, reported as the **whole ARN** rather than the account segment (blanking one field would leave the rest of the ARN in place, and a surviving copy of the account ID elsewhere in the file would rebuild it); every occurrence of an account ID pass one proved, in any file type; and an EC2 instance ID as `i-` plus either eight or seventeen hexadecimal characters, which needs no evidence.
- An ARN with no account field is not reported — `arn:aws:s3:::my-internal-bucket`, `arn:aws:iam::aws:policy/...`. There is no reliable way to tell a real bucket from an example one, since anybody may own `arn:aws:s3:::example-bucket`, so reporting them would be noise; redacting a real one is the author's job and catching it is a human reviewer's. Write example ARNs with `123456789012` or `111122223333`, both allowlisted.
- Two known gaps. An account ID appearing only as prose in a file that is not a journal is proved by none of the three sources and is not reported. And an ARN is read only where its fields can be lined up, which works for a `*` wildcard and for a CloudFormation `${...}` expression but not for another placeholder syntax in a field before the resource — `{Region}`, `<region>`, `%REGION%` — where the whole ARN fails to parse and a literal account standing beside one goes unreported. Both passes and the lookalikes that must stay silent are pinned by cases in the scanner's `--self-check`, which the check runs on every pull request.
- **Only the lines a pull request adds are reported on.** `main` already carries real identifiers in committed eval results and example ARNs, so reporting on whole files would fail contributors for content they did not write. Renames are detected, so moving such a file reports nothing.
- Three ways to resolve a finding: redact the value, removing the whole ARN for an ARN finding; add it to `.github/aws-identifier-allowlist.json` with a mandatory reason; or put an `aws-id-ok: <reason>` comment on the line, which works in the comment-bearing file types only. JSON has no comment syntax, so the allowlist is the route for JSON content.
- The allowlist parser fails closed: invalid JSON, a missing key, or a blank reason grants no allowance and fails the check, so a typo cannot silently waive a leak. An allowlisted account ID is dropped from the proven set, which silences both bare occurrences of it and any ARN naming it. The skill evaluation tool's redaction placeholders `012345678901` and `i-1234567890abcdef0` are allowlisted, suffixed forms included.
- The `needs-id-redact` label is applied by automation when the check fails and removed when it passes. Do not add or remove it by hand.
- Identifiers already on `main` are a separate follow-up change. Do not clean them up opportunistically in an unrelated pull request — the check never reports them, since it only reads added lines.

## Adding a New Skill

1. Create a new directory under `skills/` with the skill name.
2. Add a `SKILL.md` with frontmatter and step-by-step instructions following the writing guidelines above.
3. Add a `README.md` following the structure described above.
4. Add a `CHANGELOG.md` starting at version 1.0.0.
5. Add evaluation tests (`evals/` directory).
6. Test the skill with DevOps Agent before submitting.
7. Update the root `README.md` skills table with the new skill's name, agent types, author, and docs link.
8. Update the `llms.txt` file at the repo root — add the new skill to the "Available Skills" section following the existing format: `- [Skill Name](skills/<name>/SKILL.md): One-line description`.
9. If the skill requires IAM permissions beyond the `AIDevOpsAgentAccessPolicy` managed policy, add a new parameter, condition, and inline policy resource to `cloudformation/devops-agent-skill-policies.yaml`, and update the `SkillPolicySummary` output.

## Zipping for Upload

Only skills are uploaded to DevOps Agent as zips (custom agents are created via the web app; MCP servers are deployed and registered as endpoints). When zipping a skill for upload, include only allowed extensions and exclude non-skill files:

```bash
cd skills
zip -r <skill-name>.zip <skill-name>/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
```

## Git Conventions

- Push to a new branch for changes; open a pull request for review.
- Commit messages should be concise and descriptive.
- Do not commit zip files (they are gitignored).
