# LaunchDarkly Flag Drift Skill

An Agent Skill for detecting and reconciling drift between a feature flag's in-code SDK fallback default and its LaunchDarkly default rule, keeping outage behavior consistent with production.

## Overview

This skill teaches agents how to:
- Resolve a flag's current default rule (fallthrough) value from LaunchDarkly in every critical environment the build serves
- Detect cross-environment divergence (e.g. EU vs. Federal serving different defaults), where a single in-code default cannot match every environment
- Locate the fallback default argument in every SDK evaluation and declaration in code
- Compare the two and detect drift
- Reconcile only the in-code default when it has drifted, without removing the flag or changing its evaluation
- Open a well-scoped pull request that documents the change

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-drift/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

Refer to your LaunchDarkly account settings for instructions on connecting to the remotely hosted MCP server.

## Usage

Once installed, the skill activates automatically when you ask about flag default drift:

```
The default rule for `new-checkout-flow` changed in production. Check if the code default drifted
```

```
Does the hardcoded default for `dark-mode` still match LaunchDarkly?
```

```
Open a PR to sync the in-code default for `enable-new-billing` with its fallthrough
```

## Structure

```
launchdarkly-flag-drift/
├── SKILL.md
├── marketplace.json
├── README.md
└── references/
    ├── sdk-default-patterns.md
    └── pr-template.md
```

## Related

- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/SKILL.md): Remove a flag from code entirely
- [LaunchDarkly Flag Targeting](../launchdarkly-flag-targeting/SKILL.md): Change the default rule in LaunchDarkly instead of the code
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)
- [LaunchDarkly Docs](https://docs.launchdarkly.com)
- [Agent Skills Specification](https://agentskills.io/specification)

## License

Apache-2.0
