# PagerDuty

Steps to take in PagerDuty before you connect. The agent can do only what the API key is allowed to do in PagerDuty.

## Choose your region

Pick the endpoint that matches where your PagerDuty account lives:

| You sign in at | Pick |
|---|---|
| `<subdomain>.pagerduty.com` | **US** |
| `<subdomain>.eu.pagerduty.com` | **EU** |

## Connect with an API key

<!-- TODO: user vs account (REST API) key, and read-only option -->

1. In PagerDuty, create an API key as described in [API access keys](https://support.pagerduty.com/main/docs/api-access-keys).
2. Name it after its purpose, such as `aws-devops-agent`.
3. Copy the key and paste it into the connection form.

## Allow write actions

Reading works with read-only access. Acknowledging or resolving incidents and adding notes changes PagerDuty, and needs a key whose owner can update incidents.

For more detail, see the [PagerDuty MCP server documentation](https://docs.pagerduty.com/developer/mcp-tooling-remote-server). For help, contact [PagerDuty Support](https://support.pagerduty.com).
