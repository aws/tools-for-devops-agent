# LaunchDarkly Config Projects Skill

An Agent Skill for setting up LaunchDarkly project management in a codebase. Guides exploration of the stack, assessment of the right approach, and integration that fits the architecture.

## Overview

This skill teaches agents how to:
- Explore the codebase to understand the tech stack and patterns
- Assess what project setup approach makes sense
- Choose the right implementation path (by language, use case, or tooling)
- Create projects and save SDK keys via API or MCP
- Verify the setup via API fetch and SDK integration test

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/agentcontrol/projects/` into your client's skills path

## Prerequisites

**Choose one:**
- LaunchDarkly API access token with `projects:write` permission
- LaunchDarkly MCP server configured in your environment

## Usage

Once installed, the skill activates automatically when you ask about project setup:

```
Set up a LaunchDarkly project for our configs
```

```
Create a project for our customer support agent
```

```
Add LaunchDarkly project management to this codebase
```

## Structure

```
launchdarkly-projects/
├── SKILL.md
├── README.md
└── references/
    ├── quick-start.md
    ├── python-setup.md
    ├── nodejs-setup.md
    ├── go-setup.md
    ├── env-config.md
    ├── project-cloning.md
    ├── iac-automation.md
    ├── admin-tooling.md
    └── multi-language-setup.md
```

## Related

- [LaunchDarkly AgentControl](https://docs.launchdarkly.com/home/ai-configs): Create configs after setting up projects
- [LaunchDarkly Docs](https://docs.launchdarkly.com)
- [Agent Skills Specification](https://agentskills.io/specification)

## License

Apache-2.0
