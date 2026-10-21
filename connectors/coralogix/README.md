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

1. In Coralogix, go to **Settings** > **Users and Teams** > **API Keys**.
2. Under **Personal keys**, select **+ Key** and name the key, for example `aws-devops-agent`.
3. In **Role Presets**, select only **DataQuerying**. It gives read-only query access to logs, metrics, spans and datasets.
4. Select **Create** and copy the key. If your team turned on API key security settings, Coralogix shows the key only once and asks you to download it.

When you connect, paste the key by itself into **Personal API key**. DevOps Agent adds the `Bearer ` prefix.

Use a personal key, not a Send-Your-Data (ingestion) key. The key works within the permissions and data scopes of the user who creates it, so create it as a user who can query the applications and subsystems you want investigated.

If you choose permissions under **Advanced** instead of the preset, include all of these:

| Permission | Allows |
| --- | --- |
| `LOGS.DATA-API#HIGH:READDATA` | Query frequent-search logs |
| `LOGS.DATA-API#LOW:READDATA` | Query Monitoring and Compliance logs |
| `METRICS.DATA-API#HIGH:READDATA` | Query metrics |
| `SPANS.DATA-API#HIGH:READDATA` | Query frequent-search spans |
| `SPANS.DATA-API#LOW:READDATA` | Query Monitoring and Compliance spans |

Do not add write or admin permissions. To let the agent read alert definitions, add `ALERTS:READCONFIG`, `ALERTS:LOGSREADCONFIG`, `ALERTS:METRICSREADCONFIG` and `ALERTS:SPANSREADCONFIG` under **Advanced**. Do not add the **Alerts** preset, which also lets the key change and snooze alerts.

## 3. Optional: open investigations from Coralogix alerts

After you connect, the console shows a webhook URL, an `Authorization` header and a request body. Add them in Coralogix under **Integrations** > **Notification Center**. You need a role that can edit connectors and presets, such as Data Admin, Observability Lead or Platform Admin.

1. **Create a connector.** On the **Connectors** tab, select **New connector**, then **Generic HTTPS**.
   - Name it, for example `AWS DevOps Agent`.
   - Set **URL** to the webhook URL and **Request type** to **POST**.
   - Expand **Advanced**. Under **Headers**, add `Content-Type` with the value `application/json`, and `Authorization` with the value the console shows.
   - Select **Create connector**.
2. **Create a preset.** On the **Presets** tab, open **Alert**, select **Generic HTTPS**, then select **New preset**.
   - Set the **Headers** template to `{}`.
   - Replace the **Body** template with the body the console shows, unchanged.
   - Select **Send test notification** and pick your connector. Coralogix sends a sample alert, so you can check the setup before a real alert fires.
   - Select **Create preset**.
3. **Attach alerts.** In each alert that should open an investigation, go to the **Response** step.
   - Set **Notify on** to **Alerts**, not **Cases**. The preset is for alerts, and Cases mode sends case events instead.
   - On the **Destinations** tab, select **+ Add destination** and choose your connector and preset. To cover many alerts at once, add them as a destination in a Notification Center router and route the alerts to it by label.
   - Leave **Notify when resolved** off. The body marks every notification as a newly fired alert, so a recovery could open an extra investigation.

Each alert firing opens its own investigation, so attach only the alerts that need one. The alert's priority sets the investigation's priority: P1 is CRITICAL, P2 is HIGH, P3 is MEDIUM, P4 is LOW and P5 is MINIMAL. The agent starts from the alert's name and description, so give each alert a description that names the affected service and what the alert detects.

More in the Coralogix docs: [API keys](https://coralogix.com/docs/user-guides/account-management/api-keys/api-keys/), [Coralogix domain](https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/), [MCP server permissions](https://coralogix.com/docs/user-guides/mcp-server/permissions/), [Notification Center connectors](https://coralogix.com/docs/user-guides/notification-center/connectors/).
