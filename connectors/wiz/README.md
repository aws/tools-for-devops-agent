# Wiz

Steps to take in Wiz before you connect.

The Wiz MCP server must be enabled for your tenant on the [Settings > Tenant > AI Features](https://app.wiz.io/settings/ai-features) page.

## Connect with a service account (default)

Use a service account when the agent must act as itself, not as a person. Its calls are limited to the permissions and Projects you give it, and deleting the integration cuts off its access.

1. Go to [Create new Wiz MCP Integration](https://app.wiz.io/settings/deployments/integrations/new/wiz-mcp). Creating one needs a Wiz role that can create integrations.
2. Name it after its purpose, such as `aws-devops-agent`.
3. Optional: scope it to the Projects the agent should see.
4. Select **Add Integration**, then copy the **Client ID** and **Client Secret**.
5. On the [Tenant Info > Data Centers and Regions](https://app.wiz.io/tenant-info/data-center-and-regions) page, copy your **Tenant Data Center**, such as `us17`.
6. In the connection form, enter the Client ID, Client Secret and Tenant Data Center.

New tools may need more permissions later. Review the integration's permissions when Wiz announces new tools.

## Connect by signing in

No setup is needed in Wiz. You sign in when you connect, and the agent acts as you, with your Wiz role and Projects. The session lasts for the **Session Lifetime** set on [Settings > Security](https://app.wiz.io/settings/security), 30 days by default. After that, reconnect.

## Tools

The connector uses the Wiz `devops` toolset. Every tool in it reads data; none changes anything in Wiz or in your cloud. Enable the full toolset: the `wiz-security-context` skill fetches its workflow with `devops_resource_auditing_skill` and then calls the other tools.

For more detail, see [Connect to the remote Wiz MCP server](https://docs.wiz.io/docs/connect-remote-wiz-mcp-server).
