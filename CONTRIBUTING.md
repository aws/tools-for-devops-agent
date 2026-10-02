# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.

## General Guidelines

Before contributing a new tool or to an existing tool (skill, custom agent, MCP server or any other contribution), make sure you check the following:

1. Check existing tools, issues, and pull requests, to make sure that the tool or functionality you want to contribute doesn't already exist. Note that a new tool might sometimes better fit as an update to an existing tool
2. Create a setup in your AWS account, that can be used to test your tool (meaning, create the relevant AWS resources and simulate relevant scenarios)
3. Check if DevOps Agent already has the capability for which you'd like to build the tool (it might be capable of doing what you planned without it). Test it yourself without the tool (more details in the tool-specific guidelines below)
4. If you have concluded that a new tool or update to an existing tool is required, fork the repository, clone the fork, create a [tool request GitHub issue](https://github.com/aws/tools-for-devops-agent/issues/new?template=community-request.yml), and start writing your tool
5. Follow tool-specific guidelines below. Note - in some cases, you may build multiple tools that fit together to serve a specific purpose. For example, a skill for an operations review with a custom agent to run it on schedule, or a skill for investigation of issues in a specific AWS service, with an MCP server that gives it access to additional data sources. In those cases, follow the tool-specific guidelines for each of the tools you intend to contribute
6. Once you're happy with the result, create a PR (see [Contributing via Pull Requests](CONTRIBUTING.md#contributing-via-pull-requests)). A maintainer will review your content


### Build the Tool

Here are some common guidelines for building tools for this repo. Before you begin, review the following docs, depending on the tools you plan to build:

1. If you build a skill, review the [DevOps Agent skills documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html) and the [Agent Skills specification](https://agentskills.io/home)
2. If you build a custom agent, review the [DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html) and the [AGENTS.md format docs](https://agents.md/), to understand how to properly write a custom agent
3. If you build an MCP server, review the [MCP documentation](https://modelcontextprotocol.io), and make yourself familiar with the [process of connecting MCP servers to DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html)

Follow these guidelines for each tool:

1. Create a directory for your skill, custom agent or MCP server, inside the `skills/`, `custom-agents/`, or `mcp/` directory (respectively)
2. If you're building a skill, decide which DevOps Agent subagents are relevant to your skill (e.g., Chat tasks, Incident RCA). If you're building a custom agent, decide which tools and skills are relevant to it
3. Start building your skill, custom agent or MCP server, according to the documentation referenced above. If you're working with an AI tool like Kiro or Claude Code, it would be a good idea to include those links in your prompt
4. Document your tool in a `README.md` file inside your tool's directory
5. Create a `CHANGELOG.md` file for your tool, inside your tool's directory
6. Include a non-production disclaimer in your tool's `README.md` file. Add a note stating that it's a sample code, not intended for production use without additional review and testing, and that users should validate in a non-production environment first

## Tool-Specific Guidelines

### Skills

#### Skill Metadata

Make sure the frontmatter in the `SKILL.md` file includes a `metadata` block with `version`, `author` (your GitHub user) and `aws-devops-agent-skills.*` fields (see examples in existing skills)

#### Test Your Skill

1. Test relevant scenarios with DevOps Agent, with and without skill, to understand what good looks like. Iterate several times and make changes as necessary. Make sure you test relevant functionalities. For example, if your skill is intended for DevOps Agent investigations related to RDS PostgreSQL, then set up relevant AWS resources, simulate issues, and then start DevOps Agent investigations and evaluate the root cause with and without skill. Another example is, if your skill is intended to generate a report using DevOps Agent chat (such as EKS operations review), then set up relevant AWS resources, simulate scenarios that you expect your report to highlight, and then start DevOps Agent chat and evaluate its response with and without skill. Some tips for what you should check when evaluating your skill: for investigation, evaluate the different investigation root cause parts in the "Root cause" investigation tab (root cause, key findings, gaps, evidence) for correctness and quality across multiple iterations with and without skill. For chat, evaluate the chat's final response for actionability, correctness and completeness, with and without skill. Compare with and without skill runs and iterate to see if there are improvements. In both chat and investigation, evaluate multiple iterations for output consistency (investigation root cause or chat final response).

2. Test your skill with our skill evaluation tool. This tool isn't yet published in this repo. If you're an AWS employee, please follow our internal guidelines or contact us. If you're an external contributor, please tag `@aws/tools-for-devops-agent-admins` GitHub team in your GitHub issue or PR, and we'll help you evaluate your skill. The skill evaluation tool tests skills which are intended for chat and investigation, across different types of tests: structure tests (SKILL.md format and fields format), best practices tests (SKILL.md and dir structure best practices), and functional tests (with real DevOps Agent space, testing relevant parts of the investigation and chat outputs against different criteria, similar to the examples above). The tests that are done by this tool are inspired from the [Agent Skill spec](https://agentskills.io/home).

#### Eval Results Layout

**The only file you write by hand is the top-level `evals/evals.json`** — your skill's eval definitions. Everything else under `evals/` is generated by the skill evaluation tool, so run the tool as described above and commit what it wrote. Each test type gets its own subdirectory, and every run is written as a new version: a `v<N>` directory for best-practices and functional tests, and a `v<N>` suffix in the filename for structure tests. `<N>` is one or more digits (`v1`, `v12`, `v184`, ...).

This is the full shape the tool produces:

```
skills/<name>/evals/
├── evals.json                                        # YOU write this: eval definitions for the skill
├── exemptions.json                                   # optional, see "When a test type can't be run"
├── structure/
│   └── structure-tests-results-v<N>.json             # one file per run
├── best-practices/
│   └── v<N>/
│       ├── benchmark.json                            # scores for the run
│       ├── iteration-<n>/
│       │   └── best-practices-tests-results.json     # per-iteration results
│       └── cli_debug/                                # gitignored, see below
│           ├── _cli_debug_metadata.json
│           ├── cli_<nn>_<operation>_<check>.json
│           └── cli_debug_<timestamp>.log
└── functional/
    └── v<N>/
        ├── benchmark.json                            # scores for the run
        ├── evals.json                                # the evals this run executed
        ├── _metadata.json                            # run metadata
        └── iteration-<n>/
            └── <scenario-name>/                      # one per scenario in evals.json
                ├── with_skill/
                │   ├── functional-tests-results.json
                │   ├── outputs/
                │   │   ├── journal_records.json      # the DevOps Agent journal for this run
                │   │   ├── classified_output.json    # gitignored, see below
                │   │   └── metadata.json             # gitignored, see below
                │   └── sdk_debug/                    # gitignored, see below
                │       ├── _sdk_debug_metadata.json
                │       ├── sdk_<nn>_<Operation>.json
                │       └── level2_result.json
                └── without_skill/                    # same shape, skill disabled
```

Parts of this vary between runs and between tool versions: iteration counts differ (commonly three), scenario directory names come from your `evals.json`, and the debug directories are only written when a run captures them. Commit whatever your run produced rather than trying to match this tree exactly.

Two practical notes:

- **Commit only the last version of each test type.** The tool keeps every run it has ever done, and that adds up fast — one skill's local eval directory can reach tens of thousands of files and over a gigabyte, while the latest version of each test type is a few dozen files and a couple of megabytes.
- **Some of what the tool writes is deliberately not committed.** `skills/.gitignore` excludes `cli_debug/` and `sdk_debug/` entirely — debug traces from the evaluation tool and the SDK behind it, useful locally while you iterate but not part of the skill or its results, and containing `.log` files DevOps Agent wouldn't accept in a skill upload anyway. It also excludes `outputs/classified_output.json` and `outputs/metadata.json`, which are intermediate per-iteration artifacts. `outputs/journal_records.json` **is** committed: it holds the DevOps Agent journal for that run, which is the evidence of what the evaluation actually produced. Seeing the excluded files locally but not in your commit is expected.

##### The pull request check

A pull request check ([`.github/workflows/validate-skill-evals.yml`](.github/workflows/validate-skill-evals.yml)) confirms that each skill directory a PR touches carries evidence of all three test types. It deliberately verifies only the stable outer skeleton, not the full tree above, because the deeper contents vary by run and by tool version:

| Required | |
| --- | --- |
| `evals/evals.json` | must exist |
| `evals/structure/` | at least one `structure-tests-results-v<N>.json` |
| `evals/best-practices/` | at least one **complete** `v<N>/`: `benchmark.json` **and** an `iteration-<n>/best-practices-tests-results.json` |
| `evals/functional/` | at least one **complete** `v<N>/`: `benchmark.json`, `evals.json`, **and** an `iteration-<n>/<scenario-name>/` directory holding both `with_skill/functional-tests-results.json` and `without_skill/functional-tests-results.json` |

Both halves of that last requirement have to come from the same `<scenario-name>/` directory inside the same `iteration-<n>/`, since a functional result is only meaningful as a with-skill / without-skill comparison. The iteration number and scenario name themselves are wildcards — any `iteration-<n>` and any scenario name will satisfy it.

"At least one complete" means an aborted run sitting next to a good one does no harm, but a lone aborted run won't satisfy the check — if a run died before writing its `benchmark.json`, re-run it rather than committing the partial output.

When no version qualifies, the check reports the highest-numbered one and what it lacks, on the assumption that's the run you meant to commit:

```
FAIL  my-skill (enforced)
        - `skills/my-skill/evals/functional/` has no complete `v<number>/` run (v179);
          the latest, `v179/`, is missing `benchmark.json`
```

That text comes from `.github/scripts/validate_skill_evals.py`, the script the workflow runs. You'll see it in the check's job log, as annotations on the check itself, and as a summary table on the workflow run page. You can also run it locally before pushing:

```bash
python3 .github/scripts/validate_skill_evals.py --skill <your-skill-name>
```

A failing check also puts a `needs-evals` label on the PR, which is removed automatically once the check passes. That label is written only by automation and only reflects the last result — it isn't something to add or remove by hand.

##### When a test type can't be run

Some skills genuinely can't produce results for one of the test types. The two common cases are limitations in accessing the skill evaluation tool, and skills the tool can't fully evaluate yet — its functional tests don't support every DevOps Agent agent type. For those, commit an `evals/exemptions.json` naming the test type and why:

```json
{
  "functional": {
    "reason": "Functional test results could not be produced due to limitations in accessing the skill evaluation tool. Structure and best-practices results in this directory were produced by a maintainer on the author's behalf, and manual with-skill / without-skill DevOps Agent output is attached to the pull request."
  }
}
```

The exempted test type is then not checked. It's reported as a warning instead, so the check goes green while still showing what's missing and why. Keys are `structure`, `best-practices`, and `functional`; `evals.json` is hand-written rather than tool output, so it can't be exempted.

Write a reason that explains the blocker and what *was* run — a future maintainer needs to know whether to revisit it. If the exemption is temporary, such as an agent type the tool will support later, say so, so it gets removed when the limitation goes away.

An exemption excuses the tool's results, not the testing itself. Still test the skill manually as described above, and include the evidence in the pull request — DevOps Agent output with and without the skill, across a few iterations — so a maintainer can judge whether the skill actually works. An exemption with no supporting evidence gives a reviewer nothing to go on.

The file fails closed: invalid JSON, an unknown test type, or a missing or empty `reason` grants no exemption and is reported as a problem in its own right, so a typo can't silently waive a requirement. Because the file is part of the PR, granting an exemption goes through normal review like any other change — don't add one without agreement from a maintainer.

An exemption is a claim about what can't be produced, and a maintainer who doesn't accept the claim can reject it by adding the `enforce-evals` label to the pull request. That withdraws every exemption the PR's skills claim — each exempted type is checked as though the file weren't there, and the check's log names the reason it rejected next to the results now required.

The label is all-or-nothing for the whole pull request: it withdraws every exempted test type on every skill the PR touches, not just the claim a maintainer means to refuse. On a PR where one exemption is unfounded and another is legitimate, applying the label requires the results for both, and the legitimate one has to be settled in review — either by producing those results too, or by splitting the skills across separate PRs.

Everything below that depth is left unchecked, so `outputs/`, `_metadata.json`, `cli_debug/`, `sdk_debug/`, iteration counts, and scenario names are all free to vary, as are any extra files.

The check is rolling out gradually, so whether a violation fails the check or is only reported depends on the skill:

| Skill | Behavior |
| --- | --- |
| Doesn't exist on `main` yet — your PR adds it | Must satisfy the four requirements, or the check fails |
| Exists on `main` and already has this layout | Must keep satisfying them, or the check fails |
| Exists on `main` on the older flat `evals/` layout, and your PR **starts** moving it to this one | Must satisfy them, or the check fails — a migration has to be complete, not partial |
| Exists on `main` on the older flat `evals/` layout, and your PR leaves it there | Reported as a warning; the check passes |

So new skills need eval results, and existing skills are only held to that once someone migrates them. Migrating one is welcome in any PR — but finish it, or use an exemption for the part you can't produce. Landing half a migration and leaving the rest would fail the next person to touch that skill, for something they didn't do, which is why the third row exists.

##### Pull requests opened before this check existed

Pull requests that were already open when this check was introduced are listed by number in `PRS_PREDATING_CHECK`, in the script. Their authors tested their skills against the rules that applied when they contributed, so the check reports warnings for them and passes, even for a skill the PR adds. If yours is one of them, you don't have to produce eval results to merge — though they're welcome, and the warnings in the check's summary show what's missing.

Two things are outside that, because they aren't about producing results you were never asked for. A skill that already carries eval results on `main` still can't lose them, and a PR that ships *part* of the new layout still has to finish it or exempt the rest — the same rule as the third row of the table above, for the same reason.

A maintainer can still hold one of these pull requests to the full requirement, by adding the `enforce-evals` label to it. That makes every skill the PR touches enforced, the same as for a new skill, and it withdraws any exemptions those skills claim, as described above — otherwise a PR exempting all three test types would stay green whatever the label said, since an exemption removes the very violations that enforcement decides the severity of. It applies to any pull request rather than only the listed ones. Adding it re-runs the check straight away. It stays on the PR once applied, so the requirement doesn't lapse on the next push — which is why it's a separate label from `needs-evals`, the one automation clears whenever the check passes.

The list is a one-off for the transition and shrinks as those pull requests close. It'll be deleted once they're all closed.

#### Keeping a Skill Fresh

Skills reference AWS APIs, thresholds, and documentation that drift over time. A scheduled workflow ([`.github/workflows/skill-staleness-reminder.yml`](.github/workflows/skill-staleness-reminder.yml)) runs on the 1st of every other month and, for any skill whose `skills/<name>/` directory has had no commit in the last 60 days, opens a `skill-freshness` issue. Each new issue is assigned to a random repository maintainer to triage, and the issue body lists the skill's `SKILL.md` frontmatter `author` so the maintainer can reassign to the skill owner to verify.

If an issue lands with you, verify the skill against the checklist in it. When it's still accurate, bump the patch version in `SKILL.md` and add a `CHANGELOG.md` line noting the review — any commit touching the skill directory resets the clock and stops the reminder next cycle.

### Custom Agents

#### Test Your Custom Agent

Test relevant scenarios with and without the custom agent, multiple times. Focus on quality and consistency of the output, compared to asking DevOps Agent the same question using chat. When checking consistency, the output doesn't have to be the same verbatim - focus on the substance

## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment


## Contributing via Pull Requests
Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional documentation on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).


## Finding contributions to work on
Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels (enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any 'help wanted' issues is a great place to start.


## Code of Conduct
This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct).
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications
If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public github issue.


## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.

By submitting this pull request, I confirm that my contribution is made under the terms of the Apache License 2.0.
