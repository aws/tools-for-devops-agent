# Set up Elastic for AWS DevOps Agent

Connect AWS DevOps Agent to your Elastic data through the **Elastic Agent Builder MCP server**. Before connecting, select or deploy Elastic, find your project alias and region, and create an API key. To start investigations automatically from Elastic alerts, also complete sections 4 and 5.

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

## 2. Find your Elastic MCP URL or identifiers

When you connect, you select a region and enter either a **project alias** (Serverless) or **connection alias** (Cloud Hosted).

### Serverless projects
Your project alias is the first part of your Kibana URL. For example, in `https://my-project-a1b2c3.kb.us-east-1.aws.elastic.cloud`, the project alias is `my-project-a1b2c3` and the region is `us-east-1`.

You can also find the URL in Agent Builder: open **Agents / Agent Builder** → **Tools** library → **Manage MCP > Copy MCP Server URL**.

### Cloud Hosted deployments
Your connection alias is the first part of your Kibana URL. For example, in `https://my-deployment-abc123.kb.us-east-1.aws.elastic.cloud`, the connection alias is `my-deployment-abc123` and the region is `us-east-1`.

Use the **Kibana** URL, not the Elasticsearch endpoint or the Elastic Cloud sign-in URL.

The connection uses your deployment's or project's default Kibana space.

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

This descriptor supports the basic index-query tools listed below. Tools that use Elasticsearch inference endpoints additionally need `monitor_inference`; tools using Kibana connectors need `feature_actions.read`. Add privileges only for the tools you enable.

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

## 4. Trigger investigations from Elastic alerts

### Create the Webhook connector

1. Navigate to: **Stack Management → Connectors → Create connector → Webhook**
   - **Method**: POST
   - **URL**: <WEBHOOK_URL>
   - **Authentication**: None

2. Add headers:

| Name | Value |
|------|-------|
| Authorization | Bearer <API_KEY> |
| Content-Type | application/json |

Note: Name must contain only the header name (no colon). Value contains the full value, including the Bearer prefix if required. Use the Secret header type for Authorization if available, to keep it encrypted.

3. Save the connector

4. Test the connector
   Open the connector → Create an action (test panel). Paste the following into Body:

```json
{
  "test": true,
  "message": "Test notification from Kibana"
}
```

Click Run / Test. Expected: a successful response from the webhook endpoint confirms the connector is configured correctly.

### Attach the connector to your alert rule

1. Open the detection rule or alert rule that should trigger investigations
   Go to **Security → Rules** (or the Observability/alerting app the rule lives in) → open your rule → **Edit rule** → **Actions** tab.

2. Add the Webhook connector as an action
   Click **Add action** → select your Webhook connector.

3. Configure the action
   - In the dropdown for "Run when", pick the rule's active-alert action group (e.g. "Alert" / "Query matched")
   - Choose **On status changes** (not "On check interval" and not "Summarize alerts")
   - Do not attach it to the recovery action

4. Paste the investigation body
   In the action's **Body** field, paste the JSON payload AWS DevOps Agent shows after connecting. Use Kibana's variable picker ({} button) to insert rule variables like:
   - `{{context.rule.name}}`
   - `{{context.rule.id}}`
   - Service, host, and environment fields exposed by your rule type

5. Save the rule and send a test notification
   Check that an investigation opens in your AWS DevOps Agent space.

`alert.uuid` remains stable while an alert is active. The rule URL may be empty if Kibana's public base URL is not configured.

---

## 5. Automating Investigations via Elastic Workflows

With the Webhook connector configured, set up an Elastic Workflow to forward case-created events directly to AWS DevOps Agent.

### Create and configure the Elastic Workflow

Navigate to: **Management → Workflows → Create workflow**

Use the following details:

| Setting | Value |
|---------|-------|
| Workflow name | AWS DevOps Agent - Case Notification |
| Description | Forward newly created Elastic Security cases to AWS DevOps Agent |
| Status | Enabled |

### Define the Case Trigger

Elastic Workflows supports the `cases.caseCreated` event-driven trigger. This trigger runs whenever a case is created and provides the case ID and owner in the workflow event context.

Use the following YAML:

```yaml
triggers:
  - type: cases.caseCreated
    on:
      condition: 'event.owner: "securitySolution"'
```

This condition limits the workflow to cases owned by Elastic Security. Unlike an alert trigger, a case-created trigger does not need to be attached to a detection rule's Actions section—it responds automatically to the case lifecycle event.

### Retrieve full case details

The case-created trigger provides the case ID, not the complete case object. Add a `cases.getCase` step to retrieve the full case:

```yaml
- name: fetch_case
  type: cases.getCase
  with:
    case_id: "{{ event.caseId }}"
    include_comments: true
```

This retrieves the case, including its comments and attachments where available. The resulting case object can be referenced through the workflow step output, for example:
- `{{ steps.fetch_case.output.case.title }}`
- `{{ steps.fetch_case.output.case.description }}`
- `{{ steps.fetch_case.output.case.severity }}`
- `{{ steps.fetch_case.output.case.status }}`

### Forward case data to AWS DevOps Agent

Add an HTTP action to the workflow. Use the configured Webhook connector ID instead of placing the URL and Authorization header directly in the workflow:

```yaml
- name: send_to_aws_devops_agent
  type: http
  connector-id: <CONNECTOR_ID>
  with:
    method: POST
    body:
      eventType: "incident"
      incidentId: "{{ event.caseId }}"
      action: "created"
      priority: "HIGH"
      title: "{{ steps.fetch_case.output.case.title }}"
      description: "{{ steps.fetch_case.output.case.description }}"
      timestamp: "{{ steps.fetch_case.output.case.created_at }}"
      data:
        caseStatus: "{{ steps.fetch_case.output.case.status }}"
        caseSeverity: "{{ steps.fetch_case.output.case.severity }}"
```

For this initial example, priority is set to HIGH. In production, map Elastic case severity values to AWS DevOps Agent priority values:

| Elastic case severity | AWS DevOps Agent priority |
|---|---|
| critical | CRITICAL |
| high | HIGH |
| medium | MEDIUM |
| low | LOW |

AWS DevOps Agent accepts CRITICAL, HIGH, MEDIUM, LOW, and MINIMAL as priority values. Implement the mapping using workflow conditional steps before sending the request if cases have different severities.

### Complete workflow definition

The following example combines the case-created trigger, case retrieval, and HTTP notification:

```yaml
name: AWS DevOps Agent - Case Notification
description: Forward newly created Elastic Security cases to AWS DevOps Agent
enabled: true

triggers:
  - type: cases.caseCreated
    on:
      condition: 'event.owner: "securitySolution"'

steps:
  - name: fetch_case
    type: cases.getCase
    with:
      case_id: "{{ event.caseId }}"
      include_comments: true

  - name: send_to_aws_devops_agent
    type: http
    connector-id: <CONNECTOR_ID>
    with:
      method: POST
      body:
        eventType: "incident"
        incidentId: "{{ event.caseId }}"
        action: "created"
        priority: "HIGH"
        title: "{{ steps.fetch_case.output.case.title }}"
        description: "{{ steps.fetch_case.output.case.description }}"
        timestamp: "{{ steps.fetch_case.output.case.created_at }}"
        data:
          caseStatus: "{{ steps.fetch_case.output.case.status }}"
          caseSeverity: "{{ steps.fetch_case.output.case.severity }}"
```

Save and enable the workflow. The connector supplies the configured endpoint and secret Authorization header at execution time. The workflow YAML contains only the connector ID and request payload.

Verify the actual output paths and timestamp field in the workflow editor against your Elastic version before using this example in production.

### Connect detection rules to Elastic Cases

The next step is to make sure that Elastic creates a case when a detection rule identifies an issue.

Navigate to: **Security → Rules**

1. Open your AWS CloudTrail detection rule or create a new detection rule.
2. Configure the rule query and schedule.
3. Configure the rule's Actions and add the Cases action or configure an appropriate workflow to create a case.
4. Save and enable the rule.

When Elastic creates the case, the `cases.caseCreated` event automatically starts the workflow and forwards it to AWS DevOps Agent.

**Important:** You do not need to attach the case-created workflow separately to a case policy. The workflow subscribes to the case lifecycle event. The detection rule is responsible for creating the case.
