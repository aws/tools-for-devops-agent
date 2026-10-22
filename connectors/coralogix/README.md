# Set up Coralogix

Before you connect, find your Coralogix region and choose either OAuth sign-in or a personal API key. If you want Coralogix alerts to open investigations, also do step 3 after you connect.

## 1. Find your region

Your Coralogix sign-in address shows your region. Select the matching label when you connect. A key works only in its own region.

| You sign in at | Label | Hosted in |
| --- | --- | --- |
| `<team>.coralogix.com` | EU1 | AWS eu-west-1 (Ireland) |
| `<team>.app.eu2.coralogix.com` | EU2 | AWS eu-north-1 (Stockholm) |
| `<team>.app.coralogix.us` | US1 | AWS us-east-2 (Ohio) |
| `<team>.app.us2.coralogix.com` | US2 | AWS us-west-2 (Oregon) |
| `<team>.app.us3.coralogix.com` | US3 | Google Cloud us-central1 (Iowa) |
| `<team>.app.ap1.coralogix.in` | AP1 | AWS ap-south-1 (Mumbai) |
| `<team>.app.ap2.coralogix.com` | AP2 | AWS ap-southeast-1 (Singapore) |
| `<team>.app.ap3.coralogix.com` | AP3 | AWS ap-southeast-3 (Jakarta) |

## 2. Choose how to authenticate

### OAuth sign-in

Select **OAuth** in the DevOps Agent connection form, then sign in to Coralogix for the region you selected and approve the requested access. DevOps Agent completes the OAuth flow; you do not need to create or paste an OAuth client secret.

The Coralogix user who signs in needs access to the applications and subsystems the agent should investigate. Use a least-privilege, read-only role such as **DataQuerying**. Do not use a shared administrator account.

### Personal API key

1. In Coralogix, go to **Settings** > **API Keys**.
2. Select **+ Add Key**, choose **Personal Key**, and name it, for example `aws-devops-agent`.
3. In **Role Presets**, select the presets required by the tools you want to use. **DataQuerying** gives read-only query access to logs, metrics, spans, and datasets.
4. Select **Create** and copy the key.

When you connect, paste the key by itself into **Personal API key**. DevOps Agent adds the `Bearer ` prefix.

Use a personal key, not a Send-Your-Data (ingestion) key. The key works within the permissions and data scopes of the user who creates it, so create it as a user who can query the applications and subsystems you want investigated.

Ensure the personal API key has the permissions required by the tools you want to use. For example, to use the Alerts tools, select **Alerts** in **Role Presets**.

## 3. Trigger investigations from alerts

To automatically start an AWS DevOps Agent investigation when a Coralogix alert fires, use the webhook URL, API key, and request body that AWS DevOps Agent provides for your Agent Space.

Configure one Coralogix delivery path:

- **Notification Center (recommended):** Go to **Integrations** > **Notification Center** > **Connectors** and create a **Generic HTTPS** connector that sends a `POST` request to the Agent Space webhook URL. Add `Content-Type: application/json` and `Authorization: Bearer <Webhook-API-Key>` headers. Then go to **Integrations** > **Notification Center** > **Presets**, select **Alert**, and create a preset with the AWS DevOps Agent request body.
- **Legacy outbound webhook:** Go to **Integrations** > **Outbound Webhooks** and create a **Generic** outbound webhook with the same URL, headers, and request body if Notification Center is not available for your account.

For the alert, open its **Response** step, set **Notify on** to **Alerts**, then select the connector and preset, or the outbound webhook. Use the request body unchanged so it follows the AWS DevOps Agent webhook format.

More in the Coralogix docs: [AWS DevOps Agent](https://coralogix.com/docs/user-guides/mcp-server/aws-devops-agent/), [OAuth](https://coralogix.com/docs/user-guides/mcp-server/oauth/), [API keys](https://coralogix.com/docs/user-guides/account-management/api-keys/api-keys/), [Coralogix domain](https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/), and [MCP server permissions](https://coralogix.com/docs/user-guides/mcp-server/permissions/).
