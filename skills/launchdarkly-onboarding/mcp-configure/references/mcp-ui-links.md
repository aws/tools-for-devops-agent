# Open MCP settings (links instead of menu paths)

Use this reference when onboarding tells the user to enable MCP, connect OAuth, or open MCP configuration. **Give clickable links**—do not rely only on "Settings → … → Tools & MCP" prose.

## How to use (agents)

1. Use the row for the detected client (see parent onboarding **Step 2: Detect the Agent**).
2. **Always include the HTTPS documentation link** for that client—it opens in the browser and works from any environment.
3. When the user is in **VS Code or Cursor**, also include the **`command:` links** on their own lines so they can click in the editor chat (same scheme VS Code uses for trusted markdown). If a `command:` link is not clickable or does nothing, fall back to the doc link or Command Palette text below.
4. **Path caveat:** LaunchDarkly's Cursor template uses **project** `.cursor/mcp.json`. VS Code's **MCP: Open User/Workspace Configuration** commands open VS Code's `mcp.json` locations (often under `.vscode/` or the user profile)—not `.cursor/mcp.json`. If the user edited `.cursor/mcp.json`, point them at the **Cursor doc link** or "open `.cursor/mcp.json` in the editor" plus Cursor's MCP panel.

## Clients

| Client | Documentation (open in browser) | In-app shortcuts (VS Code–compatible hosts) |
|--------|----------------------------------|---------------------------------------------|
| **Cursor** | [Model Context Protocol (MCP) — Cursor Docs](https://cursor.com/docs/context/mcp) | [Open Settings (filtered search: `mcp`)](command:workbench.action.openSettings?%5B%22mcp%22%5D) |
| **VS Code** (GitHub Copilot Chat, built-in MCP, etc.) | [Add and manage MCP servers in VS Code](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) | [Open user `mcp.json`](command:workbench.mcp.openUserMcpJson) · [Open workspace folder `mcp.json`](command:workbench.mcp.openWorkspaceFolderMcpJson) · [Open Settings (filtered search: `mcp`)](command:workbench.action.openSettings?%5B%22mcp%22%5D) |
| **Claude Code** | [Connect Claude Code to tools through MCP](https://docs.claude.com/en/docs/claude-code/mcp) | Config is file-based (project `.mcp.json` or user config)—open those files in the editor; no shared `command:` URI across versions. |
| **Windsurf** | [MCP — Windsurf Docs](https://docs.windsurf.com/windsurf/mcp) | Use Windsurf's documented MCP / Cascade UI. |
| **GitHub Copilot (cloud agent, repo settings)** | [Extend Copilot coding agent with MCP — GitHub Docs](https://docs.github.com/en/copilot/customizing-copilot/extending-copilot-coding-agent-with-mcp) | Configuration is on **github.com** under the repository's **Settings** (see doc). Optional: [MCP and Copilot coding agent (concepts)](https://docs.github.com/en/copilot/concepts/coding-agent/mcp-and-coding-agent). |

## Command Palette text (fallback)

If links are not clickable:

- **VS Code / Cursor:** Run **MCP: Open User Configuration**, **MCP: Open Workspace Folder Configuration**, or **MCP: List Servers** from the Command Palette (`⇧⌘P` / `Ctrl+Shift+P`). Alternatively **Preferences: Open Settings (UI)** and search **`mcp`**.
- **Cursor:** See the [Cursor MCP doc](https://cursor.com/docs/context/mcp) for the current location of the MCP tools list and OAuth **Connect** (labels such as **Tools & MCP** or **MCP** vary by version).

## Command link encoding note

`command:workbench.action.openSettings?` links pass a JSON array argument (URL-encoded). Example: query `mcp` → `?%5B%22mcp%22%5D` is `["mcp"]`. Adjust the search string if the UI does not filter as expected (e.g. try `"Tools MCP"`).
