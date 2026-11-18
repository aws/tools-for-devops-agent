# PagerDuty

Steps to take in PagerDuty before you connect.

## Choose your region

Pick the endpoint that matches where your PagerDuty account lives:

| You sign in at | Pick |
|---|---|
| `<subdomain>.pagerduty.com` | **US** |
| `<subdomain>.eu.pagerduty.com` | **EU** |

## Connect by signing in

You sign in to PagerDuty when you connect, and grant the agent access to your account. The agent acts as you, with your PagerDuty role and permissions.

## Allow write actions

Reading works with any role. Acknowledging or resolving incidents and adding notes changes PagerDuty, and needs a role that can update incidents.

For more detail, see the [PagerDuty MCP server documentation](https://docs.pagerduty.com/developer/mcp-tooling-remote-server). For help, contact [PagerDuty Support](https://support.pagerduty.com).
