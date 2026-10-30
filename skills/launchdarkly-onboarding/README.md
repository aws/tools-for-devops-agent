# Onboarding Skill

An Agent Skill that onboards a project to LaunchDarkly end to end: install the SDK, create a first flag, and let the user watch it flip in their running app.

## Overview

The skill runs a fixed sequence and keeps the conversation quiet between decision points, so the user can delegate the work and come back to a finished state:

1. **Safe workspace** — create the `launchdarkly-onboarding` branch and leave every change uncommitted for the user to review.
2. **Explore** — classify the workspace from dependency manifests and entrypoints. A multi-package workspace is always ambiguous, so the skill asks which package to integrate instead of guessing. An empty workspace gets an offer to scaffold a small demo app.
3. **Install the SDK** — hand off to [`sdk-install`](sdk-install/SKILL.md) (detect, plan, apply), or use the fast path when the app was just scaffolded. The SDK key comes from MCP when it is already configured, otherwise from a direct dashboard link.
4. **First flag** — create the flag, add a flag-gated banner to the app, start the dev server, and hand the reveal to the user so they see the banner change when the flag turns on.
5. **MCP (optional)** — offered only after the flag works, via [`mcp-configure`](mcp-configure/SKILL.md).

Notable behaviors:

- **No log or summary file.** State is detected from the repository, so "continue onboarding" resumes at the first incomplete step.
- **Drift is redirected, not refused.** When the user asks to skip ahead, the skill acknowledges the request, names the concrete consequence in one sentence, and offers the choice.
- **Observability on request.** When the prompt asks for observability or session replay, the SDK install also adds the LaunchDarkly observability plugin to the client's `plugins` option, reusing its key. Packages and wiring per stack live in [`references/sdk/observability-plugin.md`](references/sdk/observability-plugin.md).
- **No internal leakage.** Step labels, skill file names, workflow jargon, and MCP or SDK internals never reach the user.

## Installation

```bash
npx skills add launchdarkly/ai-tooling --skill onboarding -y --agent <agent>
```

Or copy `skills/onboarding/` into your client's skills path.

## Prerequisites

- An MCP-capable coding agent (Cursor, Claude Code, Windsurf, GitHub Copilot, and others).
- `npx` on PATH for optional companion skill installs.
- A LaunchDarkly account. SDK keys, client-side IDs, and mobile keys are only needed when the SDK key step runs.

## Usage

Ask the agent to onboard the project:

> Set up LaunchDarkly in my project.

## Nested skills

| Skill | Purpose |
|-------|---------|
| [`sdk-install`](sdk-install/SKILL.md) | Detect the stack, plan the integration, apply the code changes |
| [`mcp-configure`](mcp-configure/SKILL.md) | Configure the hosted LaunchDarkly MCP server |

## Evaluations

`evals/onboarding/` scores the kickoff and the early decision points: kickoff voice, monorepo ambiguity, MCP staying out of the way until the flag works, and drift handling.

```bash
cd evals && npm run eval:onboarding
```
