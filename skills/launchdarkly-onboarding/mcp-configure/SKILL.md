---
name: mcp-configure
description: "Configure the LaunchDarkly hosted MCP server during onboarding. Use when the parent LaunchDarkly onboarding skill reaches the MCP offer, after the first flag works. Supports Cursor, Claude Code, Windsurf, GitHub Copilot, and other MCP-compatible agents. OAuth authentication; no API keys for the hosted server."
license: Apache-2.0
compatibility: Requires an MCP-compatible coding agent and a LaunchDarkly account
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# LaunchDarkly MCP Server Configuration (onboarding)

Configures the LaunchDarkly hosted MCP server so flag management skills and onboarding can use MCP tools. Uses OAuth for authentication — no API keys needed for the hosted server.

This skill is nested under [LaunchDarkly onboarding](../SKILL.md); the parent skill hands off here once the first flag works.

## Prerequisites

- A LaunchDarkly account (when directing users to sign up, use the resolved signup URL from the parent skill's [Source Attribution](../SKILL.md#source-attribution); default: `https://app.launchdarkly.com/signup?source=agent`)
- An MCP-compatible coding agent

## Hosted MCP Servers

LaunchDarkly provides a unified hosted MCP server for all functionality:

| Server      | URL                                             | Purpose                       |
| ----------- | ----------------------------------------------- | ----------------------------- |
| LaunchDarkly (unified) | `https://mcp.launchdarkly.com/mcp/launchdarkly` | Feature flags and AgentControl |

The legacy `mcp/fm` and `mcp/aiconfigs` URLs are **deprecated** — migrate any existing usage to the unified server (see [Edge Cases](#edge-cases)).

For onboarding, the unified server is all that's needed.

## Workflow

### Step 1: Detect the Agent

If the parent onboarding skill already identified the agent, use that context. Otherwise infer from agent-specific directories, config files, and the tools available to you at runtime. Do not ask the user — pick the strongest match.

### Step 2: Try Quick Install

The fastest path is the quick install link. Present it to the user:

**LaunchDarkly MCP:** [https://mcp.launchdarkly.com/mcp/launchdarkly/install](https://mcp.launchdarkly.com/mcp/launchdarkly/install)

**Important: tell the user what to expect after clicking the link.** The install link may open in the browser, but the authorization or "add server" prompt typically appears **back in the coding environment** (the editor or host app where the agent runs), not in the browser. Immediately after presenting the link, include guidance like:

- After clicking the link, watch your coding environment (the editor where this conversation is running) for an approval dialog, an "add MCP server" prompt, or a tools/integrations panel notification.
- The browser may start the OAuth flow, but you'll likely need to confirm or approve the server in the editor itself.
- **If no prompt appears:** check the editor's MCP, integrations, or tools settings area to see if the server was added but needs to be enabled. If it's not there at all, fall back to manual setup (Step 3 below).

If the quick install link doesn't work (agent doesn't support it, or user prefers manual setup), proceed to Step 3.

### Step 3: Manual Configuration

Locate the MCP config file for the detected agent and add the hosted server entry. See [MCP Config Templates](references/mcp-config-templates.md) for the exact JSON per agent.

| Agent          | Config file location                                       |
| -------------- | ---------------------------------------------------------- |
| Cursor         | `.cursor/mcp.json` (project) or global Cursor settings     |
| Claude Code    | `.mcp.json` (project) or `~/.claude.json` (global)         |
| GitHub Copilot | Repo **Settings** on GitHub.com → Copilot → Cloud agent → MCP (see [MCP UI links](references/mcp-ui-links.md)) |
| Windsurf       | Agent-specific MCP config                                  |

**Add the unified LaunchDarkly server for onboarding.** This single server handles feature flags and AgentControl.

### Step 4: Agent-Specific Authorization

After writing the config, some agents need extra steps. **Do not** send users through long manual menu paths only—use [MCP UI links](references/mcp-ui-links.md) (HTTPS docs + `command:` shortcuts for VS Code / Cursor).

**Cursor:**

1. Open MCP in Cursor using the [Cursor MCP doc link and in-app shortcuts](references/mcp-ui-links.md#clients) (e.g. Settings search via `command:` link when clickable).
2. Toggle on **LaunchDarkly** (or the name from your config).
3. Click **Connect** to authorize with the LaunchDarkly account.

**VS Code (when applicable):**

- Use [VS Code MCP doc + `mcp.json` / Settings links](references/mcp-ui-links.md#clients); trust or start the server if prompted.

**Claude Code:**

- Authorization happens automatically on first MCP tool call via OAuth prompt. File-based setup: [Claude Code MCP doc](https://docs.claude.com/en/docs/claude-code/mcp).

**GitHub Copilot:**

- Click **Save** after adding the MCP configuration in repo settings. Use the [GitHub Copilot MCP doc](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot-coding-agent-with-mcp) for the exact **Settings** path on github.com.

### Step 5: Verify MCP Tools (No Mandatory Restart)

Restart is no longer required for Cursor or Claude Code after enabling an MCP server. Probe for tools immediately after the user confirms they've enabled and authorized the server.

1. **Tell the user to enable and authorize the server.** In Cursor: toggle on the LaunchDarkly server in MCP settings and click **Connect**. In Claude Code: the OAuth prompt appears on first tool call. Do **not** tell them to restart yet.

2. **Probe immediately.** After the user confirms the server is enabled, call a lightweight MCP tool (e.g. `list-feature-flags` with the user's project key). Do not ask the user whether MCP is working — just try it.
   - **Success** (normal response, even an empty flag list): MCP is live. Continue.
   - **Auth error** (401, 403, "unauthorized", "forbidden", or OAuth-related message): the server was found but authorization failed. Go to step 3a.
   - **Tool not found or timeout** (tool not recognized, connection refused, no response): the editor hasn't picked up the server yet. Go to step 3b.

3a. **Auth failure path.** The MCP server is reachable but OAuth is incomplete or expired — restarting the editor won't help.
   - Tell the user: "The MCP server responded but authorization failed. In Cursor: open MCP settings, find the LaunchDarkly server, and click **Connect** to re-authorize. In Claude Code: the next MCP tool call should re-trigger the OAuth prompt."
   - Use [MCP UI links](references/mcp-ui-links.md) to give the user a direct shortcut to their agent's MCP settings.
   - Re-probe after the user confirms they re-authorized.
   - If the re-probe succeeds: continue with onboarding.
   - If it fails again: offer the retry one-liner (see step 4 below). Do **not** suggest a restart for a persistent auth problem.

3b. **Server-not-found path.** The editor likely hasn't loaded the new MCP config yet.
   - Tell the user: "The MCP tools aren't visible yet. Some editors need a restart to pick up new MCP servers. Restart your editor and say **'continue LaunchDarkly onboarding'** when you're back — I'll resume from here."
   - Be specific about how to restart: "Restart Cursor" / "reload Claude Code" / "refresh the Copilot agent" depending on what you detected in Step 1.

4. **On resume after restart:** The parent onboarding skill detects live state, so no log file is needed. When the next turn starts:
   - Re-probe for MCP tools silently.
   - If tools are now available: "MCP is connected." Continue with onboarding.
   - If tools still missing: do **not** block the rest of onboarding — remaining steps must still be completable without MCP. Offer a one-liner to retry later: "You can set up MCP anytime by clicking [quick install link] and restarting."

5. If the failure looks like a config issue (wrong file path, server not enabled), mention the likely cause so the user can fix it on their own time — but do not block progress.

## Edge Cases

- **User already has MCP configured:** Verify by checking for existing LD MCP entries in the config. If the unified server (`mcp/launchdarkly`) is present and working, skip configuration. If the deprecated `mcp/fm` or `mcp/aiconfigs` is present, see below.
- **User has the deprecated `mcp/aiconfigs` or `mcp/fm` server:** These URLs are deprecated. Do **not** auto-migrate. Use a blocking question:

```json
{
  "questions": [
    {
      "id": "legacy_migration",
      "prompt": "I found a deprecated LaunchDarkly MCP URL in your config (mcp/fm or mcp/aiconfigs). It should be replaced with the unified LaunchDarkly server (mcp/launchdarkly), which handles both feature flags and AgentControl. Do you want me to migrate?",
      "options": [
        { "id": "yes", "label": "Yes, remove the old server and add the unified one" },
        { "id": "no", "label": "No, leave it as is for now" }
      ]
    }
  ]
}
```

  - If **yes**: remove the deprecated entry, ensure the unified `mcp/launchdarkly` server is present (do not duplicate if it's already there), and continue.
  - If **no**: leave the config untouched and continue with onboarding — the deprecated server may still work for now.

- **User has the old npx-based local server:** Migrate them to the hosted server. Remove the old `npx @launchdarkly/mcp-server` entry and any `LD_ACCESS_TOKEN` env vars. Replace with the hosted server config.
- **Agent not in known list:** Provide the generic pattern: the user needs to add an MCP server entry pointing to `https://mcp.launchdarkly.com/mcp/launchdarkly` using whatever format their agent expects.
- **User opts out of MCP during onboarding:** Document that choice and continue; do not block SDK work.

## What NOT to Do

- Don't configure a local npx-based server. Always use the hosted server.
- Don't ask for or store API keys. The hosted server uses OAuth.
- Don't auto-migrate from the deprecated `mcp/aiconfigs` — always ask via the blocking question.
- Don't suggest restart as the first step — probe for tools immediately after the user enables the server.
- Don't suggest restart for auth errors (401/403) — the server was found, so a restart won't help. Guide the user to re-authorize instead.

## References

- [MCP UI links](references/mcp-ui-links.md) — HTTPS + `command:` links to open MCP settings (Cursor, VS Code, Claude Code, Windsurf, GitHub)
- [MCP Config Templates](references/mcp-config-templates.md) — hosted OAuth JSON per agent; migration from deprecated configs
- [Official MCP docs](https://launchdarkly.com/docs/home/getting-started/mcp-hosted) — full hosted setup guide
