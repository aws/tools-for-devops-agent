# Atlassian

Use Atlassian MCP to find Jira work, Confluence runbooks, previous incidents and
connected source code, and to create follow-up work when requested. The server is
hosted and supported by Atlassian. Access follows the connected identity's product
permissions and your organization's policies.

## Before you connect

1. Confirm that your Atlassian Cloud account or service account can access the sites,
   projects and spaces needed for investigations. Grant only the permissions needed;
   search and investigation do not require permission to create or edit content.
2. Ask your organization administrator to review the **Atlassian MCP server** settings in
   Atlassian Administration. For OAuth access, allow the AWS DevOps Agent redirect domain
   `api.prod.cp.aidevops.<region>.api.aws`, using the AWS Region of your Agent Space,
   such as `us-east-1`. For API-key access, authentication via API token must be enabled.
3. If your organization uses app IP allowlists, tool calls from AWS DevOps Agent can be
   blocked. A successful sign-in alone does not establish access to every app or site.

## OAuth sign-in (recommended)

Use an Atlassian account with access to the intended sites and apps. During Atlassian
sign-in, review the requested permissions, choose the intended site when prompted,
and consent only if those permissions match your use case. Client registration is
dynamic; you do not need to create an OAuth application or supply a client secret.

If your organization restricts MCP clients by domain, have your administrator approve
the client's redirect domain before sign-in. Consult
[Atlassian MCP settings](https://support.atlassian.com/security-and-access-policies/docs/control-atlassian-mcp-server-settings/).

## Service account API key

Ask your Atlassian administrator to create a service account and generate an API key
with the scopes and app access needed for the selected workflows. Store the key
securely and follow your organization's rotation policy. This authentication method
uses `Authorization: Bearer <api_key>`.

Use a **service account API key**, rather than a personal API token. Personal tokens
use Basic authentication with an email and token; that combined-credential flow is
outside this connector's supported authentication options.

API-key access can expose fewer tools than OAuth, depending on the scopes available
for each app. The key is not bound to a single cloud ID: select the intended site
and pass its authorized `cloudId` to tools that require it.

See [Configure authentication via API token](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/configuring-authentication-via-api-token/).

## Sites, tools and skills

The hosted endpoint is `https://mcp.atlassian.com/v2/mcp`. There is no region or
instance URL to construct. Access to a site depends on the connected identity;
use the authorized resource list to identify its cloud ID.

The optional skills cover knowledge search, bug triage, source-code search, status
reports, sprint dashboards, meeting action items and specification breakdowns.
Knowledge search, code search and dashboards read data. Other workflows can create
Jira issues, add comments or publish Confluence content when explicitly requested.
Review tool permissions and required approvals for the workflows you use.

For a `401`, check the sign-in session or API key. For a `403`, review scopes, site/app
permissions and IP policies. A missing tool can reflect authentication or product
restrictions; it does not imply that the underlying data is absent.

For help, see [Atlassian MCP documentation](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/)
or [contact Atlassian Support](https://support.atlassian.com/contact/).
