# Set up Elastic for AWS DevOps Agent

Connect AWS DevOps Agent to your Elastic data through the **Elastic Agent Builder MCP server**. Before connecting, select or deploy Elastic, copy your MCP URL, and create an API key. To start investigations automatically from Elastic alerts, also complete step 4.

## 1. Deploy or select your Elastic environment

Use an Elastic Cloud Serverless project or a currently supported Elastic Stack deployment with Agent Builder. Agent Builder is generally available in Elastic Stack 9.3 and later; your subscription or Serverless feature tier must include it.

### Elastic Cloud Hosted on AWS

1. Sign in to [Elastic Cloud](https://cloud.elastic.co/) and select **Create deployment**.
2. Choose the solution view for your workload, such as **Observability**.
3. Select **AWS**, a region near your data, and a current supported Stack version.
4. Choose a hardware profile and capacity, name the deployment, and select **Create deployment**.
5. Open Kibana when the deployment is ready.

### Elastic Cloud Serverless

1. Sign in to [Elastic Cloud](https://cloud.elastic.co/) and select **Create project**.
2. Choose **Observability**, select **AWS** and a region near your data, name the project, and select **Create project**.
3. Open Kibana when the project is ready.

### Prepare your data

Open **Agents / Agent Builder** in Kibana, using global search if needed. Ingest the logs, metrics, and traces you want investigated, and confirm you can query them. Existing environments can reuse their current data.

The MCP endpoint is part of Agent Builder in Kibana. **You do not need to deploy a separate MCP container or EC2 instance.**

## 2. Find your Elastic MCP URL

In Agent Builder, open the agents and **Tools** library and select **Manage MCP > Copy MCP Server URL**. Some versions show **Copy your MCP server URL** directly.

| Kibana space | MCP endpoint |
| --- | --- |
| Default space | `https://<kibana-host>/api/agent_builder/mcp` |
| Custom space | `https://<kibana-host>/s/<space-id>/api/agent_builder/mcp` |

Use the **Kibana endpoint**, not the Elasticsearch endpoint or Elastic Cloud sign-in URL. Preserve any configured base path. For a custom space, use its URL identifier, which may differ from its display name.

The endpoint belongs to your deployment or project; there is no shared regional Elastic MCP URL.

## 3. Create an API key and configure authentication

### API key — recommended for this setup

Create the key inside the deployment or project you are connecting.

1. Sign in as a user with `manage_own_api_key` or `manage_api_key`, Agent Builder access, and read access to the target data. The key cannot exceed its owner's permissions.
2. Find **API keys** using Kibana global search and select **Create API key**.
3. Name it `aws-devops-agent` and set an expiration, for example **30 days**.
4. Enable **Control security privileges** and paste this role descriptor:

```json
{
  "aws-devops-agent-read-only": {
    "cluster": [],
    "indices": [
      {
        "names": ["logs-*", "metrics-*", "traces-*"],
        "privileges": ["read", "view_index_metadata"]
      }
    ],
    "applications": [
      {
        "application": "kibana-.kibana",
        "privileges": ["feature_agentBuilder.read"],
        "resources": ["space:default"]
      }
    ]
  }
}
```

5. Replace the index patterns with the data the agent should investigate. For a custom space, replace `space:default` with `space:<space-id>`.
6. Create the key and securely copy its **encoded** value. It is shown only once.

This descriptor supports the basic index-query tools listed in step 4. Tools that use Elasticsearch inference endpoints additionally need `monitor_inference`; tools using Kibana connectors need `feature_actions.read`. Add privileges only for the tools you enable.

Elastic expects this HTTP header:

```http
Authorization: ApiKey <encoded-api-key>
```

When you connect, paste only the **encoded** key: the connection form adds the `ApiKey ` prefix. Use the complete encoded credential, not the separate key ID or raw `api_key` field.

Enable these tools when you connect, where available:

| Tool | Purpose |
| --- | --- |
| `platform.core.list_indices` | Discover accessible indices, aliases, and data streams. |
| `platform.core.get_index_mapping` | Inspect available fields and their types. |
| `platform.core.execute_esql` | Query and aggregate data using ES\|QL. |

If the connection fails, check:

| Symptom | Check |
| --- | --- |
| `401 Unauthorized` | Encoded key and expiration. |
| `403 Forbidden` | `feature_agentBuilder.read`, index privileges, owner permissions, and matching space scope. |
| `404 Not Found` | Project or deployment alias, region, and Agent Builder availability. |
| Tools connect but return no data | Index patterns, data ingestion, timestamps, and query filters. |

Before the key expires, create a replacement, update the connection with it, and confirm access before you invalidate the previous key.

## 4. Webhook Connector Setup — AWS DevOps Agent

### 1. Create the connector
Navigate to: **Stack Management → Connectors → Create connector → Webhook**
- **Method**: POST
- **URL**: <WEBHOOK_URL>
- **Authentication**: None

### 2. Add headers

| Name | Value |
|------|-------|
| Authorization | Bearer <API_KEY> |
| Content-Type | application/json |

Note: Name must contain only the header name (no colon). Value contains the full value, including the Bearer prefix if required. Use the Secret header type for Authorization if available, to keep it encrypted.

### 3. Save the connector

### 4. Test the connector
Open the connector → Create an action (test panel)

Paste the following into Body:

```json
{
  "test": true,
  "message": "Test notification from Kibana"
}
```

Click Run / Test. Expected: a successful response from the webhook endpoint confirms the connector is configured correctly.

### 5. Rotate credentials
Since <API_KEY> may have been shared outside of secure storage, regenerate it from the AWS DevOps Agent side and update the connector's Authorization header value before using it in production.
