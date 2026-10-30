# Grafana Cloud

Connect AWS DevOps Agent to your Grafana Cloud stack through Grafana's hosted MCP server. You sign in with your Grafana Cloud account; there's no API key or service account token to create.

## Before you connect

1. **Check your role.** You need the **Assistant Cloud MCP User** role, or the `grafana-assistant-app.cloud-mcp:access` permission. Editor and higher have it by default. A Grafana organization administrator can grant it.
2. **Accept the Grafana Assistant terms.** An administrator must have accepted the Grafana Assistant terms and conditions for the stack once.
3. **Decide on write access.** During sign-in you choose read-only or read and write access. Write access lets the agent change dashboards, alert rules and incidents, and ask Grafana Assistant questions. Granting it needs the **Assistant Admin** role or the `grafana-assistant-app.cloud-mcp.scope:write` permission. If **Write** is unavailable on the consent page, ask your Grafana organization administrator.

## While connecting

When the sign-in window opens, sign in to Grafana Cloud, choose the stack to connect, and pick read-only or read and write access.

The agent acts as you: it can see and do only what your Grafana roles allow.

The sign-in stays valid for 30 days of use. After that, reconnect to sign in again.

## More information

- [Grafana Cloud MCP documentation](https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/)
- [Grafana support](https://grafana.com/support/)
