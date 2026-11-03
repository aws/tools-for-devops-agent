# Grafana Cloud

Connect AWS DevOps Agent to your Grafana Cloud stack through Grafana's hosted MCP server. You sign in with your Grafana Cloud account; there's no API key or service account token to create.

## Before you connect

1. **Check your role.** You need the **Assistant Cloud MCP User** role, or the `grafana-assistant-app.cloud-mcp:access` permission. Editor and higher have it by default. A Grafana organization administrator can grant it.
2. **Accept the Grafana Assistant terms.** An administrator must have accepted the Grafana Assistant terms and conditions for the stack once.
3. **Decide which access to grant.** The consent page shows three access levels, each as its own checkbox:

   | Level | What the connection can do | Who can grant it |
   |---|---|---|
   | **Read** | View dashboards, alerts, incidents, metrics, logs, traces and profiles, and query Prometheus, Loki, Tempo and Pyroscope | **Assistant Cloud MCP User** |
   | **Query** | Run raw queries against SQL data sources such as ClickHouse, Snowflake, Athena and InfluxDB. These queries run as written, so they can change data when the data source's credentials allow it | **Assistant Cloud MCP User**, which every Editor holds by default |
   | **Write** | Create, modify and delete anything you can in Grafana, including asking Grafana Assistant and starting Assistant investigations. Includes Query and Read | **Assistant Admin**, or the `grafana-assistant-app.cloud-mcp.scope:write` permission |

   **For a read-only connection, clear both Query and Write**, and leave Read selected. Clearing only Write still lets the agent run SQL that can change data.

## While connecting

When the sign-in window opens, sign in to Grafana Cloud, choose the stack to connect, and select the access levels you decided on. If a checkbox is unavailable, you don't hold the role that grants it; ask your Grafana organization administrator.

The agent acts as you: it can see and do only what your Grafana roles and the access you granted allow.

The sign-in stays valid for 30 days of use. After that, reconnect to sign in again.

## After connecting

If you granted Query or Write, **require approval for those tools** in DevOps Agent: the SQL query tools, every tool that creates, changes or deletes something, and the Grafana Assistant tools that ask a question or start an investigation. Asking Grafana Assistant also counts toward your stack's Grafana Assistant usage.

## More information

- [Grafana Cloud MCP documentation](https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/)
- [Manage Grafana Assistant access with RBAC](https://grafana.com/docs/grafana-cloud/platform/grafana-assistant/privacy-and-security/rbac/)
- [Grafana support](https://grafana.com/support/)
