# MCP Servers Catalog

Browse MCP servers that extend AWS DevOps Agent with custom tools for diagnostics, monitoring, and operational tasks. Self-hosted servers are deployed to your AWS account and registered with your Agent Space; partner-hosted servers are run by their vendor and added to DevOps Agent through a connector.

## Self-hosted

<div id="mcp-catalog-root" data-source="../javascripts/mcp-data.json"></div>

## Partner-hosted

These MCP servers are hosted by their vendor, so there is nothing to deploy. Each one has a [connector](../connectors/index.md) page with its setup steps.

<div id="partner-connectors-root" data-source="../javascripts/connectors-data.json" data-site-root="../"></div>

## How MCP Servers Work

MCP ([Model Context Protocol](https://modelcontextprotocol.io)) servers provide tools to AWS DevOps Agent through a standardized protocol. Unlike skills — which teach the agent *what to do* — MCP servers give the agent *the ability to act* by exposing callable tools that interact with your infrastructure.

Each self-hosted MCP server is deployed as infrastructure in your AWS account (typically Lambda-based) and registered with DevOps Agent via a secure endpoint. The agent discovers available tools at runtime and invokes them as needed during investigations or operational workflows.

For more information, see the [AWS DevOps Agent MCP servers documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html).
