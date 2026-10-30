# LaunchDarkly Qualitative Feedback Skill

An Agent Skill that walks users through a step-by-step wizard to add LaunchDarkly's qualitative user feedback feature to a JavaScript/TypeScript codebase, adapting to the project's framework and design system.

## Overview

This skill guides users through an interactive wizard:

1. **Verify setup** — checks the SDK (client-side, v3.0+), framework, and design system
2. **Gather requirements** — asks about the target flag, prompt text, feedback type, and widget placement
3. **Verify the flag** — confirms or creates the flag in LaunchDarkly
4. **Confirm the plan** — summarizes planned changes and waits for approval
5. **Generate code** — creates the `sendFeedback` utility and feedback widget matching existing project patterns
6. **Verify** — confirms the build passes and everything is wired up correctly

Along the way the skill:
- Detects the UI framework (React, Vue, Angular, Svelte, vanilla JS) and design system (MUI, Chakra, shadcn, Tailwind, etc.)
- Identifies or creates the feature flag to attach feedback to
- Optionally links feedback to session replays via LaunchDarkly observability

## Widget Styles

The skill asks two questions to determine the widget style: feedback type and icon style.

**Feedback type:**

| Type | Description |
|------|-------------|
| Sentiment + text | Popover with sentiment buttons and a text area for comments |
| Sentiment only | Inline one-click sentiment buttons, no popover or text input |
| Text only | Popover with a text area, no sentiment buttons |

**Icon style** (when sentiment is involved):

| Style | Buttons |
|-------|---------|
| Thumbs up / down | Two buttons: positive / negative |
| Smiley faces | Three buttons: positive / neutral / negative |

This produces five widget variants:

| Type | Icons | Template |
|------|-------|----------|
| Sentiment + text | Thumbs | `PopoverFeedback` with `icons="thumbs"` |
| Sentiment + text | Smileys | `PopoverFeedback` with `icons="smileys"` |
| Sentiment only | Thumbs | `InlineFeedback` with `icons="thumbs"` |
| Sentiment only | Smileys | `InlineFeedback` with `icons="smileys"` |
| Text only | — | `PopoverFeedback` with `icons="none"` |

All widget components accept `flagKey` and `prompt` as props and track a `submitted` state that replaces the widget with a confirmation message after feedback is sent.

## Installation (Local)

For now, install by placing this skill directory where your agent client loads skills.

Examples:

- **Generic**: copy `skills/feature-flags/launchdarkly-flag-qualitative-feedback-setup/` into your client's skills path

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment. The remote server provides higher-level, agent-optimized tools that orchestrate multiple API calls and return pruned, actionable responses.

The target application must use the LaunchDarkly JavaScript SDK v3.0+ (client-side).

## Usage

Once installed, the skill activates automatically when a user asks about collecting user feedback:

```
Add a Give Feedback widget for my new search feature
```

```
Set up qualitative feedback collection on the checkout-redesign flag
```

```
I want to collect user sentiment on my feature rollout
```

```
Wire up the LaunchDarkly feedback popover using our shadcn components
```

## Structure

```
launchdarkly-flag-qualitative-feedback-setup/
├── SKILL.md                       # Wizard workflow and agent instructions
├── marketplace.json
├── README.md
└── references/
    ├── client-side-sdk-list.md    # SDK packages that support qualitative feedback
    ├── server-side-sdk-list.md    # SDK packages that do NOT support qualitative feedback
    ├── sendFeedback.ts            # Template: sends $ld:feedback event with session replay support
    ├── PopoverFeedback.tsx        # Template: popover with text area + configurable sentiment icons
    └── InlineFeedback.tsx         # Template: inline one-click sentiment buttons
```

## Related

- [LaunchDarkly Flag Create](../launchdarkly-flag-create/) — Create the flag to attach feedback to
- [LaunchDarkly Flag Targeting](../launchdarkly-flag-targeting/) — Control who sees the feedback widget via targeting rules
- [LaunchDarkly Flag Cleanup](../launchdarkly-flag-cleanup/) — Remove the feedback flag when collection is complete
- [Official Docs: User feedback](https://launchdarkly.com/docs/sdk/features/user-feedback)
- [Official Docs: Viewing feedback](https://launchdarkly.com/docs/home/releases/user-feedback)
- [LaunchDarkly MCP Server](https://github.com/launchdarkly/mcp-server)

## License

Apache-2.0
