# PagerDuty

Steps to take in PagerDuty before you connect.

## Choose your region

Pick the endpoint that matches where your PagerDuty account lives:

| You sign in at | Pick |
|---|---|
| `<subdomain>.pagerduty.com` | **US** |
| `<subdomain>.eu.pagerduty.com` | **EU** |

Both regions sign in at `identity.pagerduty.com`, so the region you pick only changes the MCP endpoint.

## Register an OAuth app

You need the Manager, Global Admin or Account Owner base role.

1. In PagerDuty, go to **Integrations** > **Developer Tools** > **App Registration** and create an app.
2. Under **Functionality**, add **OAuth** and choose **Scoped OAuth**.
3. Select the scopes the agent needs.
4. Add the redirect (callback) URL that the DevOps Agent console shows for your AWS region.
5. Copy the **client ID** and **client secret**.

See [Register an App](https://docs.pagerduty.com/developer/register-an-app) for details.

## Connect by signing in

In the DevOps Agent console, choose the region, enter the client ID and secret, then sign in to PagerDuty and grant access. The agent acts as you, with your PagerDuty role and permissions.

## Allow write actions

Reading works with any role. Acknowledging or resolving incidents and adding notes changes PagerDuty, and needs a role that can update incidents.

For more detail, see the [PagerDuty MCP server documentation](https://docs.pagerduty.com/ai-automation/advance/pagerduty-mcp-server). For help, contact [PagerDuty Support](https://support.pagerduty.com).
