# Connect Cribl to AWS DevOps Agent

Cribl's embedded MCP server lets AWS DevOps Agent investigate your Cribl environment: Sources, Destinations, Pipelines, Worker Groups, system health, metrics, alerts, and Search data. The server is built into the Cribl Leader and runs every tool call with the identity and role-based access control (RBAC) of the account whose token you provide.

These steps happen in **Cribl**, before you connect in the DevOps Agent console.

## Pre-requisites

- A Cribl environment: [Cribl.Cloud](https://aws.amazon.com/marketplace/pp/prodview-gwiqiktubqhhk?sr=0-0&ref_=ucaf&applicationId=AWSMPContessa) or [on-prem](https://docs.cribl.io/stream/deploy-types/).
- For on-prem deployments, Cribl version 4.19.0 or newer.
- The Admin role in your Cribl Organization, to enable the MCP server on the MCP Server settings page. Connecting to the server and running tools does not require the admin role.
- Product access for the tools you want to use. Cribl filters the tool list by your permissions. See [Tool Access and Permissions](https://docs.cribl.io/copilot/cribl-mcp-server/#rbac).

## 1. Enable the MCP server

An administrator must turn the server on once per Organization:

1. Log in to your Cribl.Cloud Organization, or to your on-prem Leader.
2. Go to **Settings > Global > MCP Server**.
3. Toggle **Enable MCP server** on.

Connecting and running tools does not require the admin role — only enabling the server does.

## 2. Choose your connection (Cribl.Cloud or Cribl On-Prem)

### 2a. Cribl.Cloud

If using Cribl.Cloud your MCP endpoint is `https://<workspace>-<organization>.cribl.cloud/api/v1/mcp`. The DevOps Agent console asks for the full host label — the **tenant** — which is your Workspace name and Organization ID joined by a hyphen, exactly as it appears in your Cribl.Cloud URL (for example `main-a1b2c3d4`).

You can confirm both parts under **Settings > Global > Information**.

### 2b. Cribl On-Prem

If using Cribl On-Prem, take note of your Cribl On-Prem Leader hostname and API port and paste it in the AWS DevOps Agent console.

## 3. Get your Bearer token
Use the applicable instructions depending if you're using Cribl.Cloud (3a) or Cribl On-prem (3b):

### 3a. Cribl.Cloud

The connector authenticates with a Cribl.Cloud session **Bearer token**:

1. Go to **Settings > Global > MCP Server**.
2. Under **Connect to Cribl MCP server > Get your token**, select the **Copy token** icon.

You can also copy it from the **Bearer Token** row at **Settings > Global > Information** once the server is enabled. Non-admin roles (**User**, **Read Only**, **Editor**) can get a token this way too.

Paste this value as the **Cribl Bearer token** in the AWS DevOps Agent console.

### 3b. Cribl On-Prem

On an on-prem Leader, go to **Settings > Global > MCP Server** and toggle **Enable MCP server** on. Then obtain a Bearer token from the login API. Replace the hostname, port, and credentials with your own values.

```bash
curl -s -X POST 'https://${hostname}:${port}/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username": "<your-username>", "password": "<your-password>"}' | jq -r .token
```

On-prem Bearer tokens expire according to the Auth token TTL value at Settings > Global > General Settings > API Server Settings > Advanced (default 3600 seconds, or one hour). For details, see [Authenticate with the Cribl API](https://docs.cribl.io/cribl-as-code/api-auth).

To use https for on-prem requests, you must [configure Transport Layer Security (TLS)](https://docs.cribl.io/stream/securing-tls-ui-api). If TLS is not configured, use http instead. Use http only for testing in development environments.

Paste this value as the **Cribl Bearer token** in the AWS DevOps Agent console.

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

- This connector covers **Cribl.Cloud** and on-prem Leaders. For the standalone Docker MCP server, see the [Cribl MCP server documentation](https://docs.cribl.io/copilot/cribl-mcp-server/).
- Protect your token like a password. A connected client inherits your Cribl permissions.
