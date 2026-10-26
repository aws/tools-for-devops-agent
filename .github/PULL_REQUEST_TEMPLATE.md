<!--
Thank you for your contribution! Please provide a clear description of your change below.
See CONTRIBUTING.md for guidance on contributing skills, custom agents, MCP servers, and tests.
Fill in every section that applies, and delete the entry-type sections that don't.
-->

> **Before you open this PR — read this.** Every required box below must be checked, with the work actually done, before a maintainer will review. A PR with unchecked required items is placed **on hold** and is not reviewed until it is complete. Checking a box you haven't actually done will be caught at review and sends the PR back. Eval evidence is gated separately by the `validate-skill-evals` check. The per-entry-type sections apply by contribution type — complete every section that matches what this PR adds or changes.

## Description

<!-- What does this PR add or change, and why? One or two sentences on the operational problem it solves and what it lets the agent do that it couldn't before. -->

## Type of change

- [ ] New skill
- [ ] New custom agent
- [ ] New MCP server
- [ ] Update to an existing skill, agent, or MCP server
- [ ] Documentation or infrastructure change

## Required before review

<!-- These are gates. A PR is not ready for review until each applicable box is checked. -->

- [ ] **Repository layout is correct** — skills in `/skills`, MCP servers in `/mcp`, custom agents in `/custom-agents`; skills and MCP servers are never mixed in one directory.
- [ ] **A domain SME has reviewed and signed off.** A named subject-matter expert for this domain — someone other than the author — has reviewed the tool for technical correctness and approved it in this PR. Required, not optional.
- [ ] **Evaluation evidence is included** (see Testing).
- [ ] **No internal-only or proprietary content** — no internal hostnames, account IDs, customer names, ticket numbers, internal URLs, or secrets in the tool, its examples, or its tests.
- [ ] **README is complete** — prerequisites, setup/deployment, and at least one sample prompt or usage example.
- [ ] **CHANGELOG updated** and the version bumped.
- [ ] **Named owner** for ongoing maintenance.

## Testing

<!-- How did you validate this change? For skills, include our skill evaluation tool results and manual DevOps Agent testing. The tool isn't published yet — see the Test Your Skill section in CONTRIBUTING.md for how external contributors can get their skill evaluated. -->

- [ ] `structure` checks pass.
- [ ] `best-practices` run across multiple iterations, with consistent results.
- [ ] `functional` run **with and without** the change, so the difference in the agent's behavior is visible.
- [ ] `evals/evals.json` includes **positive** cases (should trigger) and at least one **negative** case (should not trigger on unrelated input).

<!--
REVIEWERS: if this PR adds or changes a skill's `evals/exemptions.json`, that file
waives the eval-results requirement for the named test types, so the check cannot
judge it for you. Check that the `reason` names a real blocker, that the PR carries
manual with-skill / without-skill DevOps Agent output in place of the missing
results, and that nothing is exempted that could simply have been run. If a reason
does not hold, add the `enforce-evals` label: that withdraws every exemption on the
PR and requires the results after all, and the check's log then names each reason it
rejected. See the "When a test type can't be run" section in CONTRIBUTING.md.

Also: pull requests that were already open when the eval-results check was
introduced are listed in the script by number, so the check passes with warnings
instead of failing. If this is one of them and the skill should ship results after all,
add the same `enforce-evals` label — the check re-runs with every touched skill
enforced, and the label stays put on later pushes. See "Pull requests opened
before this check existed" in CONTRIBUTING.md.
-->

## Skills — complete if this PR adds or changes a skill

<!-- The validate-skills check verifies the SKILL.md frontmatter, the files a skill publishes and its version history automatically; see "Skill Publishing Rules" in CONTRIBUTING.md. -->

- [ ] `SKILL.md` frontmatter is valid: `name` matches the directory, `description` present and within length limits, body at most 500 lines.
- [ ] The `description` is written from the agent's point of view — scenarios, services, error types, symptoms.
- [ ] Scoped to a specific agent type in `metadata.aws-devops-agent-skills.agent-types` (`INCIDENT_RCA`, `INCIDENT_TRIAGE`, `INCIDENT_MITIGATION`, …), not left `GENERIC` without reason.
- [ ] Procedures are structured as decision trees on real conditions, not flat prose.
- [ ] Reference material lives in `references/` or `assets/` and loads on demand.
- [ ] Non-executable content only — **no scripts or code** in the skill directory. Deterministic compute belongs in an MCP server.

## MCP servers — complete if this PR adds or changes an MCP server

- [ ] Transport is **Streamable HTTP**; auth is documented (SigV4 / OAuth / API key).
- [ ] **Every tool is classified read-only vs mutative in the README**, with mutative tools called out explicitly.
- [ ] Tools are fixed and named — the server does not execute arbitrary caller-supplied commands, SQL, or queries. Any query surface is allowlisted and bounded (time range, result size, timeout).
- [ ] **Least-privilege IAM** — the execution role grants only the actions the tools need; the scoping is stated in the README and the policy/template is included.
- [ ] No standing secrets in code or config — credentials come from Secrets Manager or equivalent.
- [ ] Target resources are validated against an allowlist before any call.
- [ ] Tools return bounded summaries, not unbounded raw data.
- [ ] **Application security review** is complete, in progress, or linked, with a threat model. An MCP server that can act in a customer account does not merge without it.
- [ ] `template.yaml` (SAM) or `cdk.*` (CDK), `src/`, and `tests/` are present and tests pass.

## Custom agents — complete if this PR adds or changes a custom agent

- [ ] `SYSTEM_PROMPT.md` is present and is what gets pasted into the agent configuration.
- [ ] The composed tools and skills are listed in the README, and each is already in the catalog or included in this PR.
- [ ] Any mutative tool the agent can call is identified, with its approval behavior described.
- [ ] Run mode (on-demand vs scheduled) and the artifact it produces are documented.

## Security and safety

- [ ] Read-only by default; any action that changes customer state is explicit, documented, and approval-gated.
- [ ] Customer data stays in the customer's account.
- [ ] No destructive operations without an explicit, documented confirmation step.

## License confirmation

- [ ] By submitting this pull request, I confirm that my contribution is made under the terms of the Apache License 2.0.
