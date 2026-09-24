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
