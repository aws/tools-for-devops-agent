# Celonis

Connect AWS DevOps Agent to Celonis Process Intelligence through your tenant's MCP Gateway. Query process data, retrieve insights, and use the actions your Celonis team exposes.

## Configure OAuth in Celonis

1. Create a third-party OAuth client inside the Celonis platform with the necessary MCP scopes and permissions, following [MCP integration permissions](https://docs.celonis.com/en/mcp-integration-permissions.html) (Celonis sign-in required).
2. Register the callback URLs shown by the DevOps Agent console for your AWS region.
3. Copy the client ID and secret.

Available tools and data depend on the scopes and permissions configured in Celonis.

## Find your tenant and realm

Use the tenant and realm from your Celonis sign-in URL. For example, `https://my-team.eu-1.celonis.cloud` has tenant `my-team` and realm `eu-1`. Enter the tenant name without the URL prefix or domain suffix.

See [Realm cloud providers and regions](https://docs.celonis.com/en/realm-cloud-providers-and-regions.html) for the realm list (Celonis sign-in required).

## Connect

Return to the DevOps Agent console, choose the region, and enter the client ID and secret.
