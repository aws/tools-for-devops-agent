# ClickHouse Observability

Connect AWS DevOps Agent to ClickHouse Observability, the managed ClickStack service in ClickHouse Cloud, so the agent can query your logs, traces and metrics during investigations and chat. The agent reaches your data through the ClickStack MCP server, the open-source MCP server that ClickHouse Observability runs for you.

## Before you connect

- You need a ClickHouse Cloud account, and a service with [observability enabled](https://clickhouse.com/docs/clickstack/observability/getting-started) that holds your telemetry.
- Turn on MCP for that service: in the ClickHouse Cloud console, open the service, select **Connect**, then **Connect with MCP**, and turn it on.
- Set a default service in your ClickHouse Cloud account settings. The connection always uses that service. Without one, the connection is rejected.
- The agent acts as you. It sees the data sources your role in ClickHouse Observability can see, and nothing else.

No API keys or OAuth clients need to be created in ClickHouse Cloud.

## Connect

1. In the DevOps Agent console, go to **Add a capability** and choose **ClickHouse Observability**.
2. Sign in with your ClickHouse Cloud account when prompted.
3. On the consent screen, allow access to ClickHouse Observability.
4. When the console offers the `clickstack-investigation` skill, install it.

To investigate a different service, change the default service in your ClickHouse Cloud account settings.

To stop the agent's access, remove the ClickHouse Observability capability from your Agent Space.

## What the agent can do

The connector exposes the ClickStack MCP server's tools. Reading is the default:

| Tools                                                                                                                             | Access                                    |
| --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Service health, search, event patterns, event deltas, emerging signals, time series, tables, trace waterfalls, slowest operations | Read                                      |
| Listing and describing sources, metrics, dashboards, saved searches, alerts and webhooks                                          | Read                                      |
| Raw SQL                                                                                                                           | Read. Queries run read-only in ClickHouse |
| Saving or deleting dashboards, alerts, saved searches, sources and webhooks                                                       | Write                                     |

The `clickstack-investigation` skill tells the agent to use write tools only when you ask, and only after it shows you the exact change and you confirm. To rule writes out entirely, leave the write tools disabled or require approval for them in DevOps Agent.

## Support

- Documentation: [ClickStack MCP server](https://clickhouse.com/docs/clickstack/observability/mcp)
- Support: [ClickHouse support](https://clickhouse.com/support/program)
