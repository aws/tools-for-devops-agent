# Connect Cribl to AWS DevOps Agent

Cribl's embedded MCP server lets AWS DevOps Agent investigate your Cribl environment: Sources, Destinations, Pipelines, Worker Groups, system health, metrics, alerts, and Search data. The server is built into the Cribl Leader and runs every tool call with the identity and role-based access control (RBAC) of the account whose token you provide.

These steps happen in **Cribl.Cloud**, before you connect in the DevOps Agent console.

## 1. Enable the MCP server

An administrator must turn the server on once per Organization:

1. Log in to your Cribl.Cloud Organization.
2. Go to **Settings > Global > MCP Server**.
3. Toggle **Enable MCP server** on.

Connecting and running tools does not require the admin role — only enabling the server does.

## 2. Find your tenant (workspace-organization)

Your MCP endpoint is `https://<workspace>-<organization>.cribl.cloud/api/v1/mcp`. The DevOps Agent console asks for the full host label — the **tenant** — which is your Workspace name and Organization ID joined by a hyphen, exactly as it appears in your Cribl.Cloud URL (for example `main-a1b2c3d4`).

You can confirm both parts under **Settings > Global > Information**.

## 3. Get your Bearer token

The connector authenticates with a Cribl.Cloud session **Bearer token**:

1. Go to **Settings > Global > MCP Server**.
2. Under **Connect to Cribl MCP server > Get your token**, select the **Copy token** icon.

You can also copy it from the **Bearer Token** row at **Settings > Global > Information** once the server is enabled. Non-admin roles (**User**, **Read Only**, **Editor**) can get a token this way too.

Paste this value as the **Cribl Bearer token** in the DevOps Agent console.

## Which permissions the token needs

The token never grants more than the account that copied it, and Cribl checks permissions again on every tool call. Give the agent the access it should have:

- **Stream product access** — read Sources, Destinations, and Pipelines.
- **Search product access** — run KQL searches and read Search Notebooks.
- **System metrics / System messages / Monitors** — read deployment health, alerts, and monitor rules.
- Write access to a Worker Group is required only for the Pipeline-config write tool. Omit it for a read-only, investigation-only connection.

Cribl filters the tool list to what your token's permissions allow, so a read-only token simply shows fewer tools.

## Token expiration

Cribl.Cloud Bearer tokens expire after about 24 hours. When tool calls start returning HTTP 401, copy a fresh token and update the connection. If the server has been disabled, tool calls return HTTP 403 — an administrator re-enables it at **Settings > Global > MCP Server**.

## Notes

- This connector targets **Cribl.Cloud**. For on-prem Leaders or the standalone Docker MCP server, see the [Cribl MCP server documentation](https://docs.cribl.io/copilot/cribl-mcp-server/).
- Protect your token like a password. A connected client inherits your Cribl permissions.
