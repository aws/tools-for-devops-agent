# Set up Terraform

This connector connects AWS DevOps Agent to HashiCorp's hosted remote Terraform MCP server. It provides current Terraform Registry information and, with an HCP Terraform API token, access to the HCP Terraform organizations and resources that token can access.

> **Beta and scope:** The remote Terraform MCP server is a beta feature. HashiCorp advises against using beta functionality in production. It connects only to HCP Terraform organizations in the United States; it does not support HCP Europe or Terraform Enterprise. There is no region to select.

## Before you connect

- An HCP Terraform account and an organization in the United States.
- A user or team API token for that organization. Use a dedicated team token with the minimum permissions needed for the intended workflows where possible.
- The token must be stored and handled according to your organization's credential security policies.

## Create an API token

1. In HCP Terraform, create a team API token for the team that should provide AWS DevOps Agent access. Assign that team only the organization, project, and workspace permissions it needs. A user API token is also supported, but it acts as that user and may reach every organization the user belongs to.
2. Copy the token when HCP Terraform displays it. Store it securely; do not put it in a repository, prompt, or chat message.
3. If you use an organization API token, note that it cannot start runs, so run-related tools will fail with that token.

## Connect

1. In AWS DevOps Agent, add the **Terraform** partner connector.
2. Enter the HCP Terraform API token in the credential field. Enter the token value only; the connector sends it as `Authorization: Bearer <token>`.
3. Complete the connection, then verify the identity and access scope by asking which Terraform user or service account is authenticated and which organizations it can access.

The endpoint is `https://mcp.terraform.io/mcp`. The remote server requires an API token on every request, including requests to public Registry tools. It reads the token from the `Authorization` bearer header. Do not configure `TFE_ADDRESS`: this remote endpoint always connects to HCP Terraform.

## Access and safety

The API token is the access boundary. The remote server does not offer a read-only switch or per-tool configuration, so begin with a token whose HCP Terraform permissions are read-only and narrowly scoped. The agent can return private Registry details, workspace configuration and variables, plan output, logs, or state data that the token can access; treat those results as sensitive.

Some tools can make changes in HCP Terraform, including creating or updating workspaces, projects, teams, variables, policy attachments, and tags, or starting runs. Use a token with write permissions only when those workflows are intended, and keep HCP Terraform's normal approvals in place. The remote server does not expose `action_run`, project/team deletion, safe workspace deletion, force unlock, auto-approved runs, or destroy runs. A regular `create_run` can still start a plan-and-apply run; any apply remains subject to HCP Terraform's configured approval requirements. Review the run and its plan before approving changes.

For details on token permissions and remote-server safeguards, see [Remote Terraform MCP server security](https://developer.hashicorp.com/terraform/mcp-server/security#remote-terraform-mcp-server-security) and the [available tools](https://developer.hashicorp.com/terraform/mcp-server/reference#available-tools).

## Example prompts

- "Find the latest AWS provider version and show the documentation for `aws_s3_bucket`."
- "Find private modules in my HCP Terraform organization for managing Kubernetes clusters."
- "Summarize the latest run for the staging workspace, including its plan changes and current status."
- "Show the Terraform state version metadata for the payments workspace; do not change anything."
- "Create a plan-only run for the staging workspace and summarize the proposed changes. Do not approve or apply it."

## Troubleshooting

- **"Authorization bearer token is required"** — Reconnect with the API token in the connector's credential field. Do not include the `Bearer ` prefix yourself.
- **"Terraform token is unauthorized"** — The token may be expired or revoked, or it may belong to an HCP Europe organization. Create a valid token for a U.S. HCP Terraform organization and reconnect.
- **A run or organization tool returns an authorization error** — Check the token type and its HCP Terraform team or user permissions. Organization tokens cannot start runs.
- **Rate limited** — The remote server limits a session to five requests per second, with short bursts allowed. Retry after a brief pause.

## Learn more

- [Connect to the remote Terraform MCP server](https://developer.hashicorp.com/terraform/mcp-server/deploy/remote-mcp)
- [Terraform MCP server reference](https://developer.hashicorp.com/terraform/mcp-server/reference)
- [HashiCorp Terraform Agent Skills](https://github.com/hashicorp/agent-skills)
- [HashiCorp Support](https://www.ibm.com/mysupport)
