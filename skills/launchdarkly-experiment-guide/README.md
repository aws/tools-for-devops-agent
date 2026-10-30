# LaunchDarkly Experiment Guide Skill

An Agent Skill that takes a developer from *"I should probably A/B test this"* to
a concrete, ready-to-create LaunchDarkly experiment — even if they've never
designed an experiment and don't have a metric, a flag, or a hypothesis yet.

## Overview

This skill teaches agents how to:
- Scan the codebase and git history to infer what the product is and what the
  team has recently built (experiment candidates).
- Scan the connected LaunchDarkly account for existing flags and metrics, so it
  reuses instead of duplicating.
- Propose a hypothesis and a primary metric grounded in that context — with
  worked examples — instead of asking the user cold.
- Wire up the flag-evaluation and metric-tracking code the user needs.
- Draft the full experiment and create it only after explicit confirmation.

It is the novice-facing, guided front door to experimentation. For the
mechanical lifecycle (assemble/start/stop with a winner) it delegates to
[`launchdarkly-experiment-setup`](../launchdarkly-experiment-setup/SKILL.md), and
it reuses the metric and flag skills for those pieces.

## How it fits with the other skills

| Job | Skill |
|-----|-------|
| Guided, end-to-end experiment creation for a non-expert | **this skill** |
| Mechanical experiment assembly + iteration lifecycle | `launchdarkly-experiment-setup` |
| Choose / create a metric, instrument the event | `launchdarkly-metric-choose` · `-create` · `-instrument` |
| Create / wrap a flag to match the codebase | `launchdarkly-flag-create` |

## Installation

From your project's root directory:

```bash
npx skills add launchdarkly/ai-tooling --skill launchdarkly-experiment-guide -y
```

## Prerequisites

- A local codebase (the skill reads files and `git log`).
- To create the experiment automatically, either the LaunchDarkly MCP server
  configured, or a LaunchDarkly API token for the REST fallback. Without either,
  the skill still produces the full draft and the exact commands to run.

## Usage

The skill activates when you ask about experimenting or A/B testing, especially
when you don't yet know what to test:

```
I want to A/B test something in my app but I'm not sure what
```

```
Help me set up an experiment for the new checkout flow
```

```
What should I experiment on, and how do I measure it?
```
