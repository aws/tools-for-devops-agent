---
name: launchdarkly-flag-qualitative-feedback-setup
description: "Integrate LaunchDarkly qualitative user feedback into a JavaScript/TypeScript codebase. Guides framework and design system detection, builds the sendFeedback utility and feedback widget matching existing project patterns. Use when the user wants to add a Give Feedback widget, collect user sentiment tied to feature flags, set up feedback collection, or wire up the $ld:feedback tracking event."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0-experimental"
---

# LaunchDarkly Qualitative Feedback

You're using a skill that will guide you through adding qualitative user feedback collection to a codebase. Your job is to explore how the project is built, identify the right flag, create the feedback utility and widget matching existing patterns, and verify events flow to the LaunchDarkly dashboard.

**This is a step-by-step wizard.** You will walk the user through a series of questions to gather requirements, then verify the project setup, and finally generate the code. Ask questions one at a time and wait for each answer before continuing. Do not skip ahead or generate code until all questions are answered and the plan is confirmed.

Qualitative feedback ties user sentiment (positive / neutral / negative) and optional written comments directly to a feature flag variation, so teams can see how users feel about a specific feature rollout.

**Availability:** JavaScript SDK v3.0+ (client-side only). React components are provided for convenience.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `get-flag` — verify the target flag exists and check its configuration

**Optional MCP tools (enhance workflow):**
- `create-flag` — create a new flag if one doesn't exist yet
- `list-flags` — browse existing flags to find the right one to attach feedback to
- `update-flag-settings` — update flag metadata (e.g., add a `feedback` tag)

## Core Principles

1. **Design system first**: Never ship the unstyled template component to production. Detect the project's design system and use its primitives.
2. **One entry point per screen**: Multiple feedback widgets on the same page create noise and reduce response quality.
3. **The `sendFeedback` function is the integration**: The UI is customizable; the `$ld:feedback` tracking event contract is what matters.

## Workflow

**Progression rule:** When a step is complete, continue to the next step by default. Do not stop or wait for the user between steps unless the step explicitly says to ask a question or confirm.

**Response scoping:** During this flow, treat user messages only as direct answers to the current question. Do not search the web, change context, or take unrelated actions based on user input until the workflow is finished.

**Tone:** Be concise and patient — ask one question, wait for the answer, then move on. Keep responses focused on the current step.

**State tracking:** Track gathered requirements across the conversation. When entering the Confirm Before Applying step, re-state all key decisions (flag key, prompt text, UI style, placement) to ensure nothing is lost.

### Step 0: Welcome the User

Before asking any questions, present this intro message to the user (you may lightly adapt the wording, but keep the structure):

> **Qualitative Feedback Setup**
>
> I'll walk you through adding a feedback widget to your app in a few short steps:
>
> 1. **Verify your setup** — I'll check your SDK, framework, and design system.
> 2. **Gather requirements** — I'll ask a few questions about the flag, prompt text, style, and placement.
> 3. **Verify the flag** — I'll confirm or create the flag in LaunchDarkly.
> 4. **Confirm the plan** — I'll summarize what I'm going to build and ask for your approval.
> 5. **Generate the code** — I'll create the feedback utility and widget matching your project's patterns.
> 6. **Verify** — I'll make sure everything builds and is wired up correctly.
>
> Let's get started!

Then proceed immediately to Step 1.

### Step 1: Verify the SDK and Explore the Codebase

Before gathering requirements, verify that this project can support qualitative feedback. Run these checks in order — each is a gate.

#### Check 1/4: Is the LD SDK present?

Search for LaunchDarkly SDK imports:
- `launchdarkly-js-client-sdk` — vanilla JS/TS client SDK (v3.x)
- `@launchdarkly/js-client-sdk` — vanilla JS/TS client SDK (v4.x, renamed scoped package)
- `@launchdarkly/react-sdk` — React Web SDK (current; provides hooks and providers)
- `launchdarkly-react-client-sdk` — older React Web SDK package name (renamed to `@launchdarkly/react-sdk`)

Also search for SDK initialization (`initialize(` for v3.x, or `createClient(`/`start(` for v4.x, plus React provider signals `<LDProvider`, `asyncWithLDProvider`, or `createLDReactProvider`). If not found, ask the user where LDClient is initialized or accessible.

- If **no LD SDK is found at all** → inform the user that qualitative feedback requires a LaunchDarkly client-side SDK to be installed and initialized → **STOP. Do not proceed.**
- If found → continue to Check 2.

#### Check 2/4: Is it a client-side SDK?

Qualitative feedback is a **client-side only** feature. Verify the SDK found in Check 1 is a client-side SDK. Refer to [references/client-side-sdk-list.md](references/client-side-sdk-list.md) and [references/server-side-sdk-list.md](references/server-side-sdk-list.md) for the complete lists.

If the SDK is **server-side only** with no client SDK present → explain that qualitative feedback requires a client-side SDK and cannot be sent from server code → **STOP. Do not proceed.**

If unclear, ask the user whether their SDK is client-side or server-side before continuing.

#### Check 3/4: Is the SDK version compatible?

Check `package.json` for the exact version. The `$ld:feedback` event requires **v3.0+** of the JavaScript/React SDK.

- If version **< 3.0** → inform the user they need to upgrade before feedback can be added → **STOP. Do not proceed.**
- If version **>= 3.0** → continue to Check 4.

#### Check 4/4: Is feedback already configured?

Search for `$ld:feedback`, `sendFeedback`, `FeedbackPopover`, or `Give feedback` to check for existing feedback integration.

- If a **`sendFeedback` function exists** that calls `client.track('$ld:feedback', ...)` → **reuse it**. Record its import path — Step 5 will be skipped. Continue to Step 2.
- If a **feedback widget exists** but not the `sendFeedback` utility → note the widget pattern for consistency.
- If **nothing found** → continue normally.

#### Remaining exploration

After the checks above pass, gather the remaining context:

1. **Find the SDK initialization.** Search for:
   - `initialize(` from `launchdarkly-js-client-sdk` (v3.x)
   - `createClient(` / `start(` from `@launchdarkly/js-client-sdk` (v4.x)
   - `<LDProvider`, `asyncWithLDProvider`, or `createLDReactProvider` from the React SDK
   - How the `LDClient` instance is accessed (direct reference, React context, custom hook, etc.)

2. **Check for observability.** Search for `@launchdarkly/observability` and `@launchdarkly/session-replay`. If present, feedback can be linked to session replays.

3. **Detect the UI framework and design system.**

   | Signal | Framework |
   |--------|-----------|
   | `react`, `react-dom` in deps | React |
   | `vue` in deps | Vue (adapt vanilla JS pattern to Vue component) |
   | `@angular/core` in deps | Angular (adapt vanilla JS pattern to Angular component) |
   | `svelte` in deps | Svelte (adapt vanilla JS pattern to Svelte component) |
   | None of the above | Vanilla JS/TS |

   Then check for a **design system or component library**:
   - `@mui/material`, `@emotion/react` → MUI
   - `@chakra-ui/react` → Chakra UI
   - `antd` → Ant Design
   - `@radix-ui/*` or `@shadcn/*` → Radix/shadcn
   - `tailwindcss` in deps or `tailwind.config.*` → Tailwind CSS
   - `bootstrap` or `react-bootstrap` → Bootstrap
   - Custom design system → look for a `components/` directory with shared primitives (Button, Modal, Popover, etc.)

   **If a design system is detected, use its primitives** (Button, Popover, TextArea, IconButton) instead of the inline-styled template component. The template components in [references/](references/) are a **starting point** — always adapt them to match the project's existing patterns.

### Step 2: Understand the Goal

**STOP. Do not proceed to Step 3 until you have answers to ALL of the following.** Check the user's request — if it already answers a question, you don't need to re-ask it. For anything not covered, ask the user and wait for their response before continuing.

**Ask only one question at a time.** Wait for the user's answer before asking the next. Do not list multiple questions in one message. **When presenting options, use `AskUserQuestion`** to render interactive selectors in the agent console. For free-text questions (like prompt text), ask as a normal text message.

1. **Which feature/flag?** Feedback is always tied to a flag key. Search the codebase for existing flag keys, then use `AskUserQuestion` with the discovered flags as options (plus a "Create a new flag" option). If no flags are found, ask as a text question.
2. **What question do you want to ask the user?** This becomes the prompt text shown in the feedback widget (e.g., "How do you feel about this view?" or "Did this work as expected?"). Ask this as a normal text message since it requires free-text input.
3. **What type of feedback?** Use `AskUserQuestion` with header "Type" and these options:
   - label: "Sentiment + text (Recommended)", description: "Sentiment buttons with a text area for comments, in a popover"
   - label: "Sentiment only", description: "One-click sentiment buttons inline — no popover, no text input"
   - label: "Text only", description: "Just a text area for written feedback in a popover, no sentiment buttons"
   If the user selects "Sentiment + text" or "Sentiment only", follow up with `AskUserQuestion` header "Icons" and these options:
   - label: "Thumbs up / down", description: "Two buttons: positive / negative"
   - label: "Smiley faces", description: "Three buttons: positive / neutral / negative"
4. **Where should the feedback widget go?** Before asking, search the codebase for pages, routes, or main components. Then use `AskUserQuestion` with header "Placement" and 2–4 concrete placement options that make sense for this repo (e.g., "Next to the results heading on the Simulator page", "In the page header", "Below the main content area"). Prefer page-level placement — don't bury feedback in small sub-components unless it's workflow-specific confirmation.

### Step 3: Verify the Flag in LaunchDarkly

Use `get-flag` to confirm the target flag exists and is configured for client-side use.

- If the flag **doesn't exist**, use `create-flag` (or direct the user to the [flag create skill](../launchdarkly-flag-create/SKILL.md)).
- If the flag **exists but doesn't have client-side SDK availability enabled**, inform the user they need to enable it in the flag's Advanced Controls section.
- If the flag was created or verified, **provide the user with a direct link** to the flag in the LaunchDarkly dashboard.
- Optionally use `update-flag-settings` to add a `feedback` tag.

### Step 4: Confirm Before Applying

**STOP. Do not write any code until the user explicitly confirms the plan.** This applies every time — including when the user provides all details upfront, when re-running for a second flag in the same conversation, or when reusing existing utilities. A detailed user request is not implicit approval.

Summarize the planned changes using **future tense** (e.g., "Files to create", "Files to modify") — no code has been written yet:
- Flag key and whether it exists or needs creation
- The `sendFeedback` utility: where it will live, whether it will be reused from a prior step, and whether it includes session replay
- The feedback widget: component name, UI style, placement location
- Which files will be created or modified

Then use `AskUserQuestion` with header "Confirm" and these options:
- label: "Looks good", description: "Proceed with the plan as described"
- label: "Change something", description: "I want to adjust part of the plan before you start"

If the user selects "Change something" (or provides custom input), address their feedback and re-present the updated plan with the same confirmation prompt. Do not proceed to Step 5 until the user selects "Looks good".

### Step 5: Add the sendFeedback Function

**If Check 4 found an existing `sendFeedback` function, skip this step entirely.** Use the recorded import path from that check and proceed directly to Step 6.

This is the core integration. Create a utility function that sends the `$ld:feedback` tracking event.

Start from the template in [references/sendFeedback.ts](references/sendFeedback.ts). For JavaScript projects, adapt by removing type annotations.

The essential contract:

```typescript
client.track('$ld:feedback', {
    feedback_answer: string,  // required — the user's written feedback
    flag_key: string,         // required — the flag this feedback is about
    sentiment: "positive" | "neutral" | "negative",  // defaults to "neutral"
    feedback_prompt: string,  // optional — the question shown to the user
    o11y_session_id: string,  // optional — links to session replay
    custom_properties: Record<string, any>,  // optional — extra metadata to attach to the feedback event
});
client.flush();
```

**Key decisions:**
- Match the `LDClient` type import to the project's SDK version: `launchdarkly-js-client-sdk` for v3.x, `@launchdarkly/js-client-sdk` for v4.x. The templates import from `launchdarkly-js-client-sdk` — update it if the project is on v4. (The `client.track` / `client.flush` calls are the same across both.)
- If `@launchdarkly/session-replay` is in the project, include the session ID via `LDRecord.getSession()?.sessionSecureID`. If not, remove the session replay import and `o11y_session_id` logic from the template.
- Place the utility where the project keeps its LD-related code (alongside existing flag helpers, in a `lib/` or `utils/` directory, etc.)
- Export the `LDFeedbackSentiment` type if using TypeScript
- Keep the length limits from the template: `feedback_answer` and `feedback_prompt` are truncated to `MAX_FEEDBACK_LENGTH` (4096 characters), and `custom_properties` is dropped if it serializes to more than `MAX_CUSTOM_PROPERTIES_LENGTH` (4096 characters). Set `maxLength={MAX_FEEDBACK_LENGTH}` on the widget's text input so users see the limit while typing.

**Verification:** After creating the file, search the codebase to confirm it exists and contains the expected content — a `sendFeedback` export that calls `client.track('$ld:feedback', ...)` followed by `client.flush()`. If not found, fix before proceeding.

### Step 6: Build the Feedback Widget

Build the UI using the project's existing design system and component patterns.

Start from the appropriate template in [references/](references/). For JavaScript projects, adapt by removing type annotations.
- **Sentiment + text** → [PopoverFeedback.tsx](references/PopoverFeedback.tsx) with `icons="thumbs"` or `icons="smileys"`
- **Text only** → [PopoverFeedback.tsx](references/PopoverFeedback.tsx) with `icons="none"`
- **Sentiment only** → [InlineFeedback.tsx](references/InlineFeedback.tsx) with `icons="thumbs"` or `icons="smileys"`

These templates use inline styles and SVG icons so they work without any CSS framework or icon library. When the project has a design system, replace template elements with its primitives:

| Template element | Replace with |
|------------------|-------------|
| Inline `style={{...}}` | Project's CSS approach (Tailwind classes, CSS modules, styled-components, etc.) |
| `<button>` | Design system's `<Button>` component |
| Positioned `<div>` popover | Design system's `<Popover>` or `<Dropdown>` component |
| `<textarea>` | Design system's `<TextArea>` or `<Input>` component |
| Inline SVG icons | Project's icon library (Lucide, Heroicons, MUI icons, etc.) |

Always use `fill="currentColor"` (not hardcoded hex colors) in SVG icons so they inherit the parent's text color.

**Do NOT use find-and-replace for `PROMPT_TO_REPLACE`.** Instead, make `prompt` a string prop on the component. This makes the widget reusable across flags without code duplication. Pass the user's prompt text from Step 2 as a prop when rendering.

**Standard UX pattern** (follow this regardless of design system):
- A **trigger button** with a speech-bubble icon and "Give feedback" label (for popover styles)
- A **popover** that opens on click, containing:
  - A text area with the prompt text as its placeholder
  - Sentiment controls matching the style chosen in Step 2:
    - **Thumbs up / thumbs down** — two icon buttons toggling positive/negative
    - **Smiley-face scale** — three icon buttons for positive (smile), neutral (meh), negative (frown)
    - **Text-only** — no sentiment buttons; omit the `sentiment` field from `sendFeedback`
  - A submit button
- **After submission:** Track a `submitted` state. Replace the widget with a "Thanks for your feedback!" confirmation message. Do not just close the popover silently — the user needs to know their feedback was received.
- **Quick thumbs / inline smileys** (no popover): inline prompt text with sentiment buttons; sends feedback immediately on click with no text input. After click, replace with a thank-you message.

**Placement:** Use the location chosen in Step 2. Do not add multiple feedback entry points on the same screen.

#### Wire the component into the target

After building the widget, add it to the target location from Step 2:

1. **Find the target file.** Search the codebase for the page or component matching the placement chosen in Step 2. State the file path you found and ask the user to confirm it's correct before modifying it. If they say no, ask for clarification and try again.
2. **Import and render.** Import the feedback component into the confirmed target file. Render it and pass the required props: `flagKey` string and `prompt` string. For React SDK projects, the component should use the `useLDClient()` hook internally rather than accepting `ldClient` as a prop.
3. **Verification:** Search the target component to confirm it imports and renders the feedback component with the required props (`flagKey`, `prompt`). If the import or render is missing, fix before proceeding.

#### Framework-specific approach

**React** — Start from the template, then adapt to the project's design system using the table above.

**Vanilla JS/TS** — Wire up DOM elements to the `sendFeedback` function:
```typescript
submitButton.addEventListener('click', () => {
    sendFeedback(client, flagKey, feedbackInput.value, selectedSentiment, promptText);
});
```

**Vue / Angular / Svelte** — Translate the React component pattern into the framework's idiom. The `sendFeedback` function is framework-agnostic; only the UI wrapper changes.

### Step 7: Verify

**Pre-condition check:** Before verifying, confirm that all prior steps produced their expected outputs:
- (a) The `sendFeedback` utility file exists (or an existing one was reused from Check 4).
- (b) The feedback widget component file exists.
- (c) The widget is imported and rendered in the target location with the required props.

If any are missing, go back and complete the relevant step before proceeding.

Walk the user through validation step by step:

1. **Run the build.** Execute the project's build or lint command. If it fails, fix the errors before continuing.
2. **Start the app locally.** Ask the user to run their dev server (or run it yourself if you can). Confirm it starts without errors.
3. **Navigate to the feedback location.** Tell the user to open the page where the widget was placed. Ask them to confirm the "Give feedback" button (or inline thumbs) is visible and styled correctly.
4. **Submit test feedback.** Walk the user through: click the trigger → enter test text → select a sentiment → click Send. Ask them to open the browser's Network tab and confirm a POST to the LaunchDarkly events endpoint fired containing `$ld:feedback`.
5. **Check the dashboard.** Provide a direct link to the flag's **Feedback** tab in the LaunchDarkly dashboard. Tell the user to wait ~1 minute and then refresh — their test feedback should appear.
6. **Session replay (if applicable).** If `@launchdarkly/session-replay` is configured, ask the user to check for a **Replay** button next to the feedback entry in the dashboard.

After the user confirms everything works, mention:
- They can subscribe Slack channels to receive feedback notifications: go to the flag's **Feedback** tab → **Subscribe** → select Slack channels (requires the LaunchDarkly Slack app).
- Provide the direct link to the flag's Feedback tab so they can bookmark it for monitoring.

## Edge Cases

| Situation | Action |
|-----------|--------|
| No LD SDK found | **STOP** — handled by Check 1 |
| Server-side SDK only, no client SDK | **STOP** — handled by Check 2 |
| SDK version < 3.0 | **STOP** — handled by Check 3 |
| Existing `sendFeedback` function found | Reuse it, skip Step 5 — handled by Check 4 |
| React SDK (`@launchdarkly/react-sdk` / `launchdarkly-react-client-sdk`) | Access client via `useLDClient()` hook instead of a direct reference |
| Flag doesn't have client-side availability | User must enable it in the flag's Advanced Controls |
| Observability not installed | Skip the `o11y_session_id` field; session replay won't be available |
| No design system detected | Use the template component with minimal inline styles as a starting point |
| Multiple flags need feedback | Create separate `sendFeedback` calls per flag; each widget targets one flag key |

## What NOT to Do

- Don't ship the unstyled template component to production — always adapt to the project's design system.
- Don't add multiple feedback widgets on the same screen.
- Don't forget to call `client.flush()` after `client.track()`.
- Don't hardcode flag keys — use the project's existing constant/config pattern for flag keys.
- Don't send feedback from server-side code — this is a client-side feature only.

## Templates

Code templates live in [references/](references/) alongside the SDK lists:

| File | Description |
|------|-------------|
| [sendFeedback.ts](references/sendFeedback.ts) | Utility that sends the `$ld:feedback` tracking event, with session replay support |
| [PopoverFeedback.tsx](references/PopoverFeedback.tsx) | Popover with text area + configurable sentiment icons (`icons="thumbs"` / `"smileys"` / `"none"`) |
| [InlineFeedback.tsx](references/InlineFeedback.tsx) | Inline one-click sentiment buttons (`icons="thumbs"` / `"smileys"`) |

All templates are TypeScript — for JavaScript projects, adapt by removing type annotations. Templates include inline SVG icons and work without external icon libraries. Adapt them to the project's design system and pass the user's prompt text as a prop.

## References

- [Official Docs: User feedback SDK](https://launchdarkly.com/docs/sdk/features/user-feedback)
- [Official Docs: Viewing feedback](https://launchdarkly.com/docs/home/releases/user-feedback)
- [Tutorial: Collecting user feedback](https://launchdarkly.com/docs/tutorials/collect-qualitative-user-feedback-homepage)

## Example Flows

These show how the decision tree plays out for common scenarios.

**Happy path — React + TypeScript, new flag, thumbs popover:**
Step 0 → welcome. Step 1 → finds `@launchdarkly/react-sdk`, React + Tailwind, no existing feedback. Step 2 → user picks a new flag `checkout-redesign`, prompt "How do you feel about the new checkout?", thumbs style, placed below the order summary. Step 3 → creates flag via `create-flag`. Step 4 → user approves. Step 5 → creates `sendFeedback.ts` in `lib/ld/`. Step 6 → creates `FeedbackPopover.tsx` adapted to Tailwind, wires it into `CheckoutPage.tsx` with `useLDClient()`. Step 7 → build passes, event fires.

**Existing sendFeedback — reuse and skip:**
Step 1 → Check 4 finds `src/utils/sendFeedback.ts` already calling `client.track('$ld:feedback', ...)`. Records the import path. Step 2 → gathers requirements normally. Steps 3–4 → as usual. Step 5 → **skipped** (reuses existing function). Step 6 → builds widget, imports `sendFeedback` from the existing path. Step 7 → build passes, event fires.

**Server-side SDK — early STOP:**
Step 1 → Check 1 finds `@launchdarkly/node-server-sdk`. Check 2 → it's in `server-side-sdk-list.md`, no client SDK present. → Informs user that qualitative feedback requires a client-side SDK. **STOP.**

**No design system — minimal styles:**
Step 1 → finds `launchdarkly-js-client-sdk` v3.2, no React, no Tailwind, no component library. Step 6 → uses the template with inline styles as the baseline, adapts to the project's vanilla JS patterns and existing CSS conventions.
