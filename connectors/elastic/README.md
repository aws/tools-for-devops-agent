Set up Elastic for AWS DevOps Agent

Connect AWS DevOps Agent to your Elastic data through the **Elastic Agent Builder MCP server**. Before connecting, select or deploy Elastic, copy your MCP URL, and create an API key. To start investigations automatically from Elastic alerts, also complete step 6.

## 1. Deploy or select your Elastic environment

Use an Elastic Cloud Serverless project or a currently supported Elastic Stack deployment with Agent Builder. Agent Builder is generally available in Elastic Stack 9.3 and later; your subscription or Serverless feature tier must include it.

### Elastic Cloud Hosted on AWS

1. Sign in to [Elastic Cloud](https://cloud.elastic.co/) and select **Create deployment**.
2. Choose the solution view for your workload, such as **Observability**.
3. Select **AWS**, a region near your data, and a current supported Stack version.
4. Choose a hardware profile and capacity, name the deployment, and select **Create deployment**.
5. Open Kibana when the deployment is ready.

### Elastic Cloud Serverless

### Prepare your data

Open **Agents / Agent Builder** in Kibana, using global search if needed. Ingest the logs, metrics, and traces you want investigated, and confirm you can query them. Existing environments can reuse their current data.

The MCP endpoint is part of Agent Builder in Kibana. **You do not need to deploy a separate MCP container or EC2 instance.**

If Kibana is privately reachable, configure an [AWS DevOps Agent private connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-to-privately-hosted-tools.html) with a route to its HTTPS endpoint.

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

Use the complete encoded credential, not the separate key ID or raw `api_key` field. In the AWS custom MCP configuration below, enter **`ApiKey` followed by one space and the encoded key**. An Elastic API key does not use the `Bearer` prefix.

## 4. Connect AWS DevOps Agent

1. In the AWS DevOps Agent console, open **Capability Providers**.
2. Under **MCP Server**, select **Register** and enter a name and the MCP endpoint from step 2. Leave dynamic client registration off for this API key setup.
3. Choose **API Key** authentication and enter:

| Field | Value |
| --- | --- |
| API key name | `elastic-mcp` |
| Header name | `Authorization` |
| API key value | `ApiKey <encoded-api-key>` |

4. Submit the registration and confirm connection validation succeeds.
5. Open your **Agent Space > Capabilities > MCP Servers > Add**. Select the registered server and allowlist only the read-only tools needed for investigations.

Start with these tools, where available:

| Tool | Purpose |
| --- | --- |
| `platform.core.list_indices` | Discover accessible indices, aliases, and data streams. |
| `platform.core.get_index_mapping` | Inspect available fields and their types. |
| `platform.core.execute_esql` | Query and aggregate data using ES\|QL. |

AWS DevOps Agent requires **Streamable HTTP** transport. Use the remote Kibana MCP endpoint directly.

## 5. Verify the connection

For an optional API-key check, set the endpoint and encoded key locally, then list Agent Builder tools:

```bash
export ELASTIC_MCP_URL="https://<kibana-host>/api/agent_builder/mcp"
export ELASTIC_API_KEY="<encoded-api-key>"

curl --fail-with-body --silent --show-error \
  "${ELASTIC_MCP_URL%/mcp}/tools" \
  --header "Authorization: ApiKey ${ELASTIC_API_KEY}"
```

For a custom space, set `ELASTIC_MCP_URL` to its full space-specific URL. Keep real credentials out of the README and source control.

A successful JSON response confirms access to the tools API. To verify MCP transport and data access, also complete AWS connection validation and ask DevOps Agent:

> Use Elastic to identify accessible log indices, inspect their fields, and summarize error logs from the last 15 minutes.

Check that the investigation uses the Elastic tools and returns records from an expected index and time range.

| Symptom | Check |
| --- | --- |
| `401 Unauthorized` | Encoded key, expiration, and the `Authorization: ApiKey …` header. |
| `403 Forbidden` | `feature_agentBuilder.read`, index privileges, owner permissions, and matching space scope. |
| `404 Not Found` | Kibana host, base path, space ID, and Agent Builder availability. |
| Connection timeout | DNS, HTTPS reachability, Elastic network filters, and any AWS private connection. |
| Tools connect but return no data | Index patterns, data ingestion, timestamps, and query filters. |

Before the key expires, create a replacement and update the registered provider through **Capability Providers > Actions > Update**. Verify access before invalidating the previous key.

## 6. Trigger investigations from Elastic alerts — optional

The MCP connection lets DevOps Agent query Elastic. A webhook lets an Elastic alert start an investigation.

1. In your Agent Space's **Capabilities** tab, add a generic webhook with **API key** authentication. Copy its URL and generated token.
2. In Kibana, go to **Stack Management > Connectors** and create a **Webhook** connector. You can also create one while configuring a rule.
3. Set the method to **POST**, use the AWS webhook URL, and select **None** for the connector's built-in authentication. Add these headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer <aws-webhook-token>` |

Store the authorization value as a **Secret** header where supported. If `xpack.actions.allowedHosts` restricts outbound destinations, include the webhook hostname.

4. Add the connector to the rule's actions. For a per-alert action in Kibana Classic Alerting, use this starting body:

```json
{
  "eventType": "incident",
  "incidentId": "{{alert.uuid}}",
  "action": "created",
  "priority": "HIGH",
  "title": "{{rule.name}}",
  "description": "Elastic alert {{alert.id}} from rule {{rule.name}}. Rule URL: {{rule.url}}",
  "timestamp": "{{date}}"
}
```

5. Verify the variables using the rule's variable picker. Add service, host, environment, and relevant alert details to `description`; AWS does not include the free-form `data` object in the investigation context. Adjust the priority for the rule.
6. Select the rule's active-alert action group and **On status changes**. Do not attach this `action: created` body to the recovery action.
7. Send a test notification and verify that an investigation opens in the intended Agent Space.

Use a per-alert action, not an alert summary, for this template. `alert.uuid` remains stable while an alert is active. The rule URL may be empty if Kibana's public base URL is not configured.

**Keep the two credentials separate:** the Elastic API key uses `ApiKey` for AWS-to-Elastic queries; the AWS webhook token uses `Bearer` for Elastic-to-AWS notifications.
