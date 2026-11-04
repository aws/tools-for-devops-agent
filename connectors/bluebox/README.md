# Bluebox

Steps to take in Bluebox before you connect. With this connection, AWS DevOps Agent can ask Bluebox about your live services (health, errors, latency, dependencies and earlier Bluebox investigations) while it investigates incidents, checks changes and reviews releases.

## Before you connect

- A Bluebox workspace with your observability backend connected.
- Services that send OpenTelemetry traces (and optionally logs and metrics) to that workspace. Check under **Environment** in Bluebox that they show up. Services derived from traces are listed only while they send traffic.

## Create an access token

1. In Bluebox, open your profile menu, select **Account**, then open **Access tokens** and select **Create token**.
2. Create one token per Agent Space, so you can revoke one space's access without affecting other clients.
3. Copy the value. Bluebox shows it once. Paste it into the connection form's **Bluebox access token** field. The connector sends it as `Authorization: Bearer <token>`.

The token carries your full Bluebox identity: the agent sees what you can see in Bluebox, and every question it asks counts against your workspace's daily AI usage. If the token is exposed, revoke it under **Account → Access tokens** right away.

## Find your workspace ID

Each connection reads one Bluebox workspace, the one whose ID you enter. Workspace IDs start with `ws_`.

1. Sign in to Bluebox and use the workspace menu to open the workspace the agent should read.
2. Copy the workspace ID from the browser's address bar.
3. Paste it into the connection form's **Bluebox workspace ID** field. The connector sends it as `X-Workspace-Id: <workspace-id>`.

Two other places show the ID. On the **Access tokens** page, select the workspace before you copy the generated config: the config carries the ID in its `X-Workspace-Id` header. In the Bluebox CLI, `bluebox workspace list --output json` prints the `id` of every workspace you belong to.

Bluebox refuses a workspace the token's owner is not a member of (HTTP 403). The token still reaches every workspace you belong to, so a tool call that names another of your workspaces reads that one.

## Optional: connect your repositories

Connect your GitHub repositories in Bluebox under **Settings → Setup**. The agent can then find the services a code change touches by repository.

## Tools

All seven tools only read your Bluebox data. Enable all of them. `ask` is annotated as not read-only because Bluebox saves each question and its answer as a conversation you can open later in Bluebox. It changes nothing in your systems. Leave `ask` without required approval, so investigations, which run without an operator, can use it.

## Token expiry and rotation

Access tokens expire after 30 days. Before a token expires, create a new one, update the connection's credential in AWS DevOps Agent, then revoke the old token. Bluebox keeps several tokens active at once, so the connection keeps working while you switch. If tool calls start failing with HTTP 401, the token has expired or was revoked: create a new one and update the connection.

## More information

- [Bluebox MCP server](https://docs.bluebox.ai/mcp-server), including "Scope to a specific workspace"
- [Bluebox workspaces](https://docs.bluebox.ai/workspaces) and the [Bluebox CLI](https://docs.bluebox.ai/cli)
- [Bluebox security and privacy](https://docs.bluebox.ai/security-and-privacy)
- [Getting help](https://docs.bluebox.ai/getting-help)
