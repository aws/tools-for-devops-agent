# Bluebox

Steps to take in Bluebox before you connect. With this connection, AWS DevOps Agent can ask Bluebox about your live services (health, errors, latency, dependencies and earlier Bluebox investigations) while it investigates incidents, checks changes and reviews releases.

You connect in one of two ways: with an access token and a workspace ID (the default), or by signing in with Bluebox.

## Before you connect

- A Bluebox workspace with your observability backend connected.
- Services the observability backend monitors, through OpenTelemetry or instrumentation already in place. Check under **Environment** in Bluebox that they show up. The agent lists only services that sent traces in the last hour.

## Create an access token

1. In Bluebox, open your profile menu, select **Account**, then open **Access tokens** and select **Create token**.
2. Create one token per Agent Space, so you can revoke one space's access without affecting other clients.
3. Copy the value. Bluebox shows it once. Paste it into the connection form's **Bluebox access token** field. The connector sends it as `Authorization: Bearer <token>`.

The token carries your full Bluebox identity: the agent sees what you can see in Bluebox, and every question it asks counts against your workspace's daily AI usage. If the token is exposed, revoke it under **Account → Access tokens** right away.

## Find your workspace ID

With an access token, each connection reads one Bluebox workspace, the one whose ID you enter. Workspace IDs start with `ws_`.

1. Sign in to Bluebox and use the workspace menu to open the workspace the agent should read.
2. Copy the workspace ID from the browser's address bar.
3. Paste it into the connection form's **Bluebox workspace ID** field. The connector sends it as `X-Workspace-Id: <workspace-id>`.

Two other places show the ID. On the **Access tokens** page, select the workspace before you copy the generated config: the config carries the ID in its `X-Workspace-Id` header. In the Bluebox CLI, `bluebox workspace list --output json` prints the `id` of every workspace you belong to.

Bluebox refuses a workspace the token's owner is not a member of (HTTP 403). The token still reaches every workspace you belong to, so a tool call that names another of your workspaces reads that one.

## Sign in with Bluebox (OAuth)

Nothing needs to be set up in Bluebox for this option: AWS DevOps Agent registers itself with Bluebox when you connect.

1. When you connect, sign in to Bluebox in your browser.
2. Read the approval page and approve access. The sign-in grants `mcp:tools`, which lets the agent call Bluebox tools in your workspaces as you. It works only at the Bluebox MCP server. The approval page lists AWS DevOps Agent as an unverified, self-registered app. This is expected: AWS DevOps Agent registers itself when you connect, so Bluebox can't verify its name.

The connection acts as the person who signed in, with that person's current workspace access: the agent sees what they can see in Bluebox, and every question it asks counts against the workspace's daily AI usage. If their role changes or they leave a workspace, the agent's access changes with it.

A sign-in lasts at most 90 days, and ends sooner if the connection goes 14 days without use. Then sign in again. To review or revoke the connection, open your profile menu, select **Account**, then open **Connected agents**.

This option sends no workspace ID. Bluebox reads your default workspace, otherwise the one you used most recently, otherwise your only workspace. If you belong to more than one workspace, pin the one the agent should read: open it in Bluebox, go to workspace settings and turn on **Open this workspace by default**. A tool call can still read another of your workspaces by naming it in its `workspace_id` argument, for example when the Agent Space instructions name that workspace.

**Which option to pick.** An access token reads one fixed workspace and needs no browser sign-in, but you replace it every 30 days. Signing in leaves no token to store or rotate, but reads your default workspace and needs a new sign-in at least every 90 days.

## Optional: connect your repositories

Connect your GitHub repositories in Bluebox under **Settings → Setup**. The agent can then find the services a code change touches by repository.

## Tools

All seven tools only read your Bluebox data. Enable all of them. `ask` is annotated as not read-only because Bluebox saves each question and its answer as a conversation you can open later in Bluebox. It changes nothing in your systems. Leave `ask` without required approval, so investigations, which run without an operator, can use it.

## Token expiry and rotation

Access tokens expire after 30 days. Before a token expires, create a new one and connect again with it: remove Bluebox from each Agent Space, deregister it under **Capability Providers**, then add it again with the new token. Removing it also deletes the `bluebox-observability` skill, so install it again. Then revoke the old token. If tool calls start failing with HTTP 401, the token has expired or was revoked: create a new one and connect again the same way.

## More information

- [Bluebox MCP server](https://docs.bluebox.ai/mcp-server), including "Know what you approve when you sign in", "Review and revoke connected agents" and "Scope to a specific workspace"
- [Bluebox workspaces](https://docs.bluebox.ai/workspaces) and the [Bluebox CLI](https://docs.bluebox.ai/cli)
- [Bluebox security and privacy](https://docs.bluebox.ai/security-and-privacy)
- [Getting help](https://docs.bluebox.ai/getting-help)
