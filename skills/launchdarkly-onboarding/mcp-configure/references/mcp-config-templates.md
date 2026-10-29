# MCP Config Templates

Per-agent JSON snippets for configuring the LaunchDarkly hosted MCP server. All configurations use OAuth — no API keys required.

Source: https://launchdarkly.com/docs/home/getting-started/mcp-hosted

## Unified Server (Recommended)

Use the unified server URL for new configurations:

| Server | URL | Purpose |
|--------|-----|---------|
| LaunchDarkly (unified) | `https://mcp.launchdarkly.com/mcp/launchdarkly` | Feature flags and AgentControl |

**Legacy URLs (deprecated):**
- `mcp/fm` — **deprecated**. Migrate to the unified server.
- `mcp/aiconfigs` — **deprecated**. Migrate to the unified server.

See [mcp-configure Edge Cases](../SKILL.md#edge-cases) for migration guidance.

## Cursor

Config file: `.cursor/mcp.json` in the project root.

### Unified server (recommended)

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly",
      "headers": {}
    }
  }
}
```

### Legacy feature management only (deprecated)

> **Deprecated:** `mcp/fm` is deprecated. Use the unified server URL above.

```json
{
  "mcpServers": {
    "LaunchDarkly feature management": {
      "url": "https://mcp.launchdarkly.com/mcp/fm",
      "headers": {}
    }
  }
}
```

**After adding the config:** enable the server and complete OAuth in Cursor's MCP UI. Use [MCP UI links — Cursor](mcp-ui-links.md#clients) (HTTPS doc + optional `command:` links); do not rely only on nested Settings menu paths.

## Claude Code

Config file: `.mcp.json` in the project root, or `~/.claude.json` for global config.

### Unified server (recommended)

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "type": "http",
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly"
    }
  }
}
```

### Legacy feature management only (deprecated)

> **Deprecated:** `mcp/fm` is deprecated. Use the unified server URL above.

```json
{
  "mcpServers": {
    "LaunchDarkly feature management": {
      "type": "http",
      "url": "https://mcp.launchdarkly.com/mcp/fm"
    }
  }
}
```

Authorization happens automatically via OAuth prompt on first MCP tool call.

## GitHub Copilot

Configured via the GitHub web UI, not a local config file.

1. Navigate to the target repository on GitHub
2. Go to **Settings > Code and automation > Copilot > Coding agent**
3. In the **MCP configuration** section, add:

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly",
      "headers": {}
    }
  }
}
```

4. Click **Save**

## Windsurf

Windsurf uses a similar MCP configuration format. Add to the agent's MCP config:

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly"
    }
  }
}
```

Consult Windsurf's documentation for the exact config file location.

## Migrating from Deprecated mcp/fm

The `mcp/fm` URL is deprecated. Replace it with the unified server.

**Remove this:**

```json
{
  "mcpServers": {
    "LaunchDarkly feature management": {
      "url": "https://mcp.launchdarkly.com/mcp/fm",
      "headers": {}
    }
  }
}
```

**Replace with:**

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly",
      "headers": {}
    }
  }
}
```

## Migrating from Deprecated mcp/aiconfigs

The `mcp/aiconfigs` URL is deprecated. Replace it with the unified server.

**Remove this:**

```json
{
  "mcpServers": {
    "LaunchDarkly AI Configs": {
      "url": "https://mcp.launchdarkly.com/mcp/aiconfigs",
      "headers": {}
    }
  }
}
```

**Replace with:**

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly",
      "headers": {}
    }
  }
}
```

The unified server handles both feature flags and AgentControl. If you also had `mcp/fm`, migrate it to the unified server — `mcp/fm` is **deprecated** and will be removed.


**Note:** Do not auto-migrate. Always ask the user via a blocking question before making changes (see [mcp-configure Edge Cases](../SKILL.md#edge-cases)).

## Migrating from the Old Local Server

If the user has the old npx-based server configured with an inline API key, replace it with the hosted unified server:

**Remove this:**

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "command": "npx",
      "args": [
        "-y", "--package", "@launchdarkly/mcp-server",
        "--", "mcp", "start",
        "--api-key", "api-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      ]
    }
  }
}
```

**Replace with the unified hosted server:**

```json
{
  "mcpServers": {
    "LaunchDarkly": {
      "url": "https://mcp.launchdarkly.com/mcp/launchdarkly",
      "headers": {}
    }
  }
}
```

Also remove any `LD_ACCESS_TOKEN` or `LAUNCHDARKLY_API_KEY` environment variables that were used for the local server. The hosted server handles authentication via OAuth.
