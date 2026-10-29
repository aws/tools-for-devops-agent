---
name: launchdarkly-onboarding
description: "Scripted onboarding for LaunchDarkly: quiet execution, fixed sequence, SDK install, first flag with a live reveal, MCP offered afterwards. Enforces step completion before advancing and redirects drift. Use when adding LaunchDarkly, setting up or integrating feature flags in a project, SDK integration, or 'onboard me'."
license: Apache-2.0
compatibility: Requires an MCP-capable coding agent and `npx` on PATH for optional skill installs. SDK keys, client-side IDs, and mobile keys are only needed when the SDK key step runs.
metadata:
  author: launchdarkly
  version: "0.4.0"
---

# LaunchDarkly Onboarding

## Voice and Tone

Write plainly. Say only what you did or are about to do. No flourishes, slogans, or metaphors.

- Status lines, not narration. "Scanning your project now." "Scan complete. Installing SDK."
- No em dashes. Use periods or commas.
- Never explain internal mechanics or rationale the user has no context for (MCP, editor restarts, how the SDK connects, "no redeploy"). It means nothing to a first-time user.
- Before writing any line, ask whether the user needs it. If not, cut it.
- Do not offer a choice the user cannot meaningfully make. If the right move is obvious, just do it.
- Reassure plainly about safety. "No code will be changed without your approval."

## Source Attribution

The signup URL includes a `source` query parameter for attribution. Resolve it once at kickoff by scanning the user's original message. Store the resolved URL for the session. This marker is for the agent only. Never show it to the user.

| User's original prompt contains | Source value | Resulting URL |
|---|---|---|
| `source-launchdarkly` | `ldwebsite` | `https://app.launchdarkly.com/signup?source=ldwebsite` |
| No marker | `agent` | `https://app.launchdarkly.com/signup?source=agent` |

- Scan the user's initial message for `source-launchdarkly`. If found, use `ldwebsite`. Otherwise use `agent`.
- Parse once, before Step 0. Do not re-parse later.
- On resume, use `agent`.

Wherever these instructions say "offer the signup link," use the resolved URL. Never hardcode `?source=agent`.

## Rules

- The step labels below are your internal roadmap. Never show step names or numbers to the user.
- Enforce sequence. Do not advance until the current stage is done.
- Work silently between decision points. Do the work without narrating each step. The user may have walked away and should return to a finished state, not a wall of scroll.
- Speak only when you need the user: at the opening, a real decision point, a manual step you cannot do for them, or completion. Keep it short and lead with the outcome.
- Make changes on a branch and leave them uncommitted. The user reviews and commits, not you.
- Install companion skills at the point of need, never upfront.
- Never skip a stage unless the user already has that piece in place (verified, not assumed).
- If a stage fails, stop and resolve it before continuing.

### Speaking to the user

Keep user-facing messages rare and short. You are letting the user delegate and walk away.

- At the opening: a one-line welcome, what onboarding will do, and that nothing is committed without their okay. Then the first choice. Then go quiet and work.
- At a decision point or completion: one short summary. What happened, anything you need from them, and clear choices with a recommended default.
- Do not narrate routine work or write prose between execution steps. When the terminal stops scrolling, the user reads one concise message and never has to scroll back.

### Forbidden in user-facing output

- Step names, internal labels, or skill file names
- Workflow language ("hand off," "proceed to next step")
- Internal rationale (MCP, editor restarts, SDK internals)
- Raw markdown from these instructions
- The app's rendered output or the flag-gated content. Point the user to the running app instead of pasting what it shows.

---

## Experience Detection

Greet and present the first choice immediately. Do not make the user wait on a scan. Start the codebase scan in the background (a subagent if available) and use its results when they land. Never ask the user about the scan.

| Signal | Inference |
|---|---|
| LD SDK in dependencies | Knows LaunchDarkly |
| `variation()`, `useFlags()`, or equivalent calls present | Has used flags before |
| MCP already configured | Familiar with the tooling |
| Well-structured codebase (CI, tests, linting) | Experienced developer |
| Empty workspace, no LD presence | Treat as first-time |

If experienced signals show, move faster: skip the orientation line, do each action and report it in one line, and jump to whichever step is incomplete. Either way the outcomes are the same: SDK installed, first flag evaluating, and MCP only if they ask for it.

---

## Resume After Restart

If the user says "continue onboarding," they are returning to the flow. Do not ask what was happening. Detect live state in order: check for a LaunchDarkly SDK package and init code, then for `variation()` calls, then for the `launchdarkly-onboarding` branch. Resume at the first incomplete step and say where things stand in one sentence ("SDK is installed. Creating your first flag now."). Then continue without preamble.

---

## Kickoff

When the user asks to set up LaunchDarkly:

1. Open directly. No "I'll help you" or "Let me start" filler. Two short sentences: a welcome, what onboarding does, and that nothing is committed without their approval. Example (adapt, do not copy verbatim):
   > "Let's get you set up with LaunchDarkly. Once integrated, we'll create a test flag in your app so you can see how it works. No code will be changed without your approval."
2. Then start working. No roadmap table. One status line is fine ("Scanning your project now."), then go quiet.
3. Do not ask whether the user has an account. Infer it later: completing the SDK key step means they have one; if they cannot get a key, share the signup link at that point.

---

## Step 0: Safe Workspace

If this is a git repository, create and switch to a new branch named `launchdarkly-onboarding` before changing any files, so everything is isolated and reversible. If that branch already exists, append a short suffix. If this is not a git repo, skip silently.

Do not write an onboarding log or any summary file. Track state in memory for this session.

---

## Step 1: Explore

The scan runs in the background (see Experience Detection). Do not announce it beyond the one status line. Use its results when they land.

Classify the workspace before proceeding:

| State | Criteria | Action |
|---|---|---|
| **Clear app** | One language, a real entrypoint, one dependency manifest at the obvious location | Continue |
| **Unclear** | Minimal or conflicting signals, or a multi-package workspace (yarn/pnpm/npm workspaces, lerna, nx, turborepo, gradle, cargo, go) where more than one package could host LaunchDarkly | Ask (unclear form below) |
| **No app found** | No manifests, no entrypoints, empty workspace | Ask (no-app form below) |

A workspace with two or more candidate packages is always Unclear. Never guess which one to integrate.

**Ask form, unclear workspace** (one option per candidate package, with its path as the label):
```json
{
  "questions": [
    {
      "id": "app_location",
      "prompt": "I found multiple packages. Which one do you want to set up first?",
      "options": [
        { "id": "candidate_1", "label": "<detected path, e.g. packages/api>" },
        { "id": "candidate_2", "label": "<detected path, e.g. packages/web>" },
        { "id": "demo", "label": "None of these. Scaffold a demo." },
        { "id": "other", "label": "Somewhere else. I'll tell you where." }
      ]
    }
  ]
}
```

**Ask form, no app found:**
```json
{
  "questions": [
    {
      "id": "app_choice",
      "prompt": "I didn't find a runnable app. How do you want to proceed?",
      "options": [
        { "id": "demo_node", "label": "Scaffold a minimal Node.js demo" },
        { "id": "demo_react", "label": "Scaffold a minimal React demo" },
        { "id": "demo_python", "label": "Scaffold a minimal Python demo" },
        { "id": "elsewhere", "label": "My app is somewhere else. I'll point you to it." }
      ]
    }
  ]
}
```

On a demo choice, scaffold a minimal app in a new subfolder (e.g. `launchdarkly-demo/`).

Identify language, framework, and environment type from dependency files (`package.json`, `go.mod`, `requirements.txt`/`pyproject.toml`, `pom.xml`/`build.gradle`, `Gemfile`, `*.csproj`, `Cargo.toml`). Search for existing LaunchDarkly usage (`launchdarkly`, `ldclient`, `LDClient`, `@launchdarkly`). Determine server-side, client-side, or mobile, which drives SDK selection. If LD is already integrated, note the SDK version so install can be skipped.

Detect the coding agent for `--agent` flags: Cursor (`.cursor/`, `.cursorrules`), Claude Code (`~/.claude/`, `CLAUDE.md`), Windsurf (`.windsurfrules`), GitHub Copilot (`.github/copilot/`), Codex (`~/.codex/`, `AGENTS.md`). If ambiguous, ask.

---

## Step 2: MCP (optional, after the flag)

Do not set up MCP on the way to the first flag, and do not ask about it during setup. Reach the first flag without it (Step 4 uses a dashboard link). Offer it only after the flag works, as one short choice:

> "Want to manage flags from your editor next time? I can set that up. **[Set it up] [Skip]**"

If they choose **Set it up**: follow [mcp-configure](mcp-configure/SKILL.md). When that nested skill is not available in the session, install it:

```bash
npx skills add launchdarkly/ai-tooling --skill mcp-configure -y --agent <detected-agent>
```

If that fails, check `~/.agents/skills/` and `~/.cursor/skills/` for a cached copy, or configure the server inline using [MCP Config Templates](mcp-configure/references/mcp-config-templates.md). After it succeeds, call `get-project` once (`projectKey: "default"`) and store `projectKey` and `envKey` (`test`).

---

## Step 3: Install the SDK

Install the SDK and wire up initialization automatically. Do not ask how, and do not explain what the SDK is. Tell the user one line: "Scan complete. Installing SDK." Then proceed.

Hand off to [sdk-install](sdk-install/SKILL.md) with the stack context from Step 1. It runs detect, plan, and apply: selects the package, installs it, and wires initialization to match the codebase. When that nested skill is not available in the session, install it:

```bash
npx skills add launchdarkly/ai-tooling --skill sdk-install -y --agent <detected-agent>
```

When the app was scaffolded by the agent in Step 1, skip the nested skill and use the fast path directly (the stack is known; skip `npm run build`):

| Scaffold | Package | Install | Env var | Entrypoint | Init |
|---|---|---|---|---|---|
| React (Vite) | `launchdarkly-react-client-sdk` | `npm install launchdarkly-react-client-sdk` | `VITE_LAUNCHDARKLY_CLIENT_SIDE_ID` | `src/main.jsx`/`.tsx` | `asyncWithLDProvider` around the root render |
| Node.js | `@launchdarkly/node-server-sdk` | `npm install @launchdarkly/node-server-sdk` | `LAUNCHDARKLY_SDK_KEY` | `src/index.js`/`server.js` | `init(sdkKey)` then `waitForInitialization()` |
| Python | `launchdarkly-server-sdk` | `pip install launchdarkly-server-sdk` | `LAUNCHDARKLY_SDK_KEY` | `app.py`/`main.py` | `ldclient.set_config(Config(sdk_key))` then `ldclient.get()` |

Rules: the SDK key lives in an environment variable, never hardcoded. One client instance, shared. Wait for initialization before evaluating flags.

### Observability plugin

This applies whenever the user mentions observability, session replay, error monitoring, logs, or tracing, at any point: in the first message, mid-flow, or as a follow-up after onboarding is done ("Can you also add the observability plugin?"). Follow [Observability plugin](references/sdk/observability-plugin.md) for the package and wiring per stack. The essentials:

- Add the plugin to the `plugins` option of the LaunchDarkly client's existing init, reusing its key. No second client, no second credential, no key prompt.
- If the client is already initialized, add the plugin to that init without redoing the SDK install or asking for a key. Mid-onboarding, then continue to the first flag as usual. As a follow-up after onboarding finished, confirm in one line and stop: no restarted onboarding, no new first flag.
- Session replay with no privacy level named: use the strictest setting (`privacySetting: 'strict'` in the browser).
- If the installed SDK is too old to accept `plugins` and the fix is a major-version upgrade or a different package, ask before changing it, naming the version problem in one line.
- If the stack has no observability plugin, say so in one line and continue with feature flags. Do not substitute OpenTelemetry or another package.

### SDK key

The SDK needs a key. Default to fetching it for the user when MCP is connected; otherwise give them the direct link and let them paste it. Ask only if you cannot determine the path:

```json
{
  "questions": [
    {
      "id": "sdk_key_setup",
      "prompt": "Do you have a LaunchDarkly account?",
      "options": [
        { "id": "yes", "label": "Yes" },
        { "id": "no_account", "label": "Not yet" }
      ]
    }
  ]
}
```

- Account, MCP connected: fetch the key via `get-environments`, write it to `.env`, and ensure `.env` is gitignored. Never print key values.
- Account, no MCP: give the direct link and have them paste it. `https://app.launchdarkly.com/projects/{projectKey}/settings/environments/{envKey}/keys`
- No account: share the resolved signup link. Write placeholder env vars so the code compiles, and continue.

Key type must match the integration: server-side SDK takes an **SDK key**, browser/client-side takes a **client-side ID**, mobile takes a **mobile key**. Env variable names and bundler rules live in [Apply code changes](sdk-install/apply/SKILL.md).

Do not proceed until initialization is verified.

---

## Step 4: First Flag

Create the flag, wire it into the app, and let the user watch it turn on.

- **Create the flag.** If MCP is connected, call `create-flag` (on a duplicate-key conflict, call `get-flag` and adopt the existing flag; do not `list-flags` first). If MCP is not connected, give them a dashboard link that opens the create form with the key prefilled and have them create it: `https://app.launchdarkly.com/projects/{projectKey}/flags/new?key={flagKey}`
- **Add a flag-gated banner.** Insert a small, clean banner at the top of the app's main page, gated on the flag. Off state: a neutral banner reading "LaunchDarkly test banner (flag is off)" with a link to view the flag in LaunchDarkly. On state: the banner switches to a clearly different look (for example a green background) reading "LaunchDarkly test banner (flag is on)". Style it so it looks intentional, not like debug output. Add to the existing app, do not rewrite it. For an app with no rendered page, add one equivalent visible output (an endpoint or a startup line) that changes with the flag.
- **Start the dev server on a free port** (check `lsof -ti :3000,4000,5173` first). **Keep it running until the user has seen the flag turn on. Do not stop the server before then.**
- **Hand off the reveal to the user.** Give them the local URL and one choice for turning it on:

```json
{
  "questions": [
    {
      "id": "flip_method",
      "prompt": "Your app is running at <url> and the flagged element is off. Turn the flag on to watch it change. How do you want to flip it?",
      "options": [
        { "id": "ld_ui", "label": "I'll flip it in LaunchDarkly" },
        { "id": "agent", "label": "Flip it for me" }
      ]
    }
  ]
}
```

- If **I'll flip it in LaunchDarkly**: give them the direct link to the flag and wait. `https://app.launchdarkly.com/projects/{projectKey}/flags/{flagKey}/targeting?env={envKey}`
- If **Flip it for me**: turn it on via `toggle-flag` (MCP) or the REST API, whichever is configured. If neither is, fall back to the dashboard link.
- Only offer **Flip it for me** when MCP or an API token is actually configured. Otherwise show just the LaunchDarkly option.

Do not print the page or the banner text in chat. Point the user to their browser: the banner at `<url>` flips live with the server still running. That is the flag working.

### Wrap-up

Keep it to a few lines:
- The flag is live. See it in LaunchDarkly: `https://app.launchdarkly.com/projects/{projectKey}/flags/{flagKey}/targeting?env={envKey}`
- Nothing is committed. Your changes are on the `launchdarkly-onboarding` branch, so you can review, keep, or drop them however you like.
- One choice for what's next. Drop the observability option if the plugin was added during setup.

```json
{
  "questions": [
    {
      "id": "explore_next",
      "prompt": "Want to explore more of LaunchDarkly?",
      "options": [
        { "id": "experimentation", "label": "Experimentation: test changes and measure impact" },
        { "id": "observability", "label": "Observability: monitor flags and errors in production" },
        { "id": "ai_configs", "label": "AI Configs: manage AI models and prompts" },
        { "id": "done", "label": "Not now" }
      ]
    }
  ]
}
```

---

## Redirecting Drift

If the user asks to skip a step or jump ahead mid-flow, your first reply always does three things, in order, before writing code or skipping:
1. Acknowledge what they asked for, in their words.
2. Name the concrete consequence of skipping in one sentence. The specific thing that breaks (e.g. "the flag calls won't run until the SDK is installed"). State the real failure, not a vague allusion.
3. Offer the choice: finish the quick step first, or proceed their way.

> "I hear you, you want the flag code now. Without the SDK installed those calls won't run. Setup takes about two minutes. Want me to finish that first, or hand you the code to wire up after?"

Never silently dump code with no tradeoff, and never rigidly refuse. If they insist, respect it, note what was skipped, restate the risk in one sentence, and keep moving.

---

## Skill Repositories

| Repo | Skills | Purpose |
|------|--------|---------|
| `launchdarkly/ai-tooling` | `launchdarkly-onboarding`, `sdk-install`, `mcp-configure` | Setup |
| `launchdarkly/ai-tooling` | `launchdarkly-flag-create` and related | Flag management |

---

## Edge Cases

- **SDK already installed:** Skip Step 3. Say so in one line that names what you found and where, then go to Step 4. Do not re-explain the SDK or run install commands. If the user asked for observability, still add the plugin to the existing client first ([Observability plugin](references/sdk/observability-plugin.md)).
- **MCP already configured:** Use it. Skip the Step 2 offer. Call `get-project` to store keys and continue.
- **Deprecated mcp/aiconfigs or mcp/fm found:** Both are deprecated. Ask before migrating to the unified `mcp/launchdarkly` server. Do not auto-migrate.
- **No supported agent detected:** Ask directly. Provide manual config if needed.
- **npx not available:** Provide manual skill installation (clone repo, copy skill directories).
- **User only wants partial setup:** Respect it. State what is missing and what that limits.
- **Non-LaunchDarkly dependencies would have to change** (peer-dep bumps, lockfile churn) to install or compile the SDK: get explicit approval first, per [Apply code changes](sdk-install/apply/SKILL.md).

## References

- [mcp-configure](mcp-configure/SKILL.md) and [MCP Config Templates](mcp-configure/references/mcp-config-templates.md) — Step 2
- [sdk-install](sdk-install/SKILL.md) — Step 3 (detect, plan, apply)
- [SDK recipes](references/sdk/recipes.md) and [SDK snippets](references/sdk/snippets/) — per-SDK install and init detail
- [Observability plugin](references/sdk/observability-plugin.md) — Step 3, when the user asks for observability or session replay
