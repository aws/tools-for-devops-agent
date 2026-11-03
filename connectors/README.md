# Connectors

A connector is the definition of an MCP server that a partner hosts, for customers to add to AWS DevOps Agent. Unlike `mcp/`, which holds servers you deploy in your own account, a connector holds no code: each lives in `connectors/<name>/` as a `connector.yaml`, a `logo.svg`, an optional `logo-dark.svg` for dark themes and a `README.md` setup guide.

| Path | Contents |
|---|---|
| `schema/v1/connector.schema.json` | JSON Schema (2020-12) for `connector.yaml` with `schema_version: 1` |
| `schema/v1/releases.schema.json` | JSON Schema for `releases.yaml` |
| `schema/v1/published-files.json` | The files a connector directory may contain. Every one is published |
| `releases.yaml` | Per connector, the version production serves. Changed by maintainers only |
| `TERMS.md` | The AWS DevOps Agent Partner Connector Terms and Conditions, which a partner accepts in its connector's pull request |

`maintainers` in `connector.yaml` lists the GitHub usernames, or teams as `org/team`, that maintain the connector, without a leading `@`.

A partner accepts the [AWS DevOps Agent Partner Connector Terms and Conditions](TERMS.md) in the pull request that adds or changes its connector; see "Partner Connectors" in [CONTRIBUTING.md](../CONTRIBUTING.md). Connector submissions are not open yet. The contribution guide, covering how to write and submit a connector, will be added to CONTRIBUTING.md.
