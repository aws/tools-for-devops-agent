# Set up Bronto

Before you connect, find your Bronto region and choose either signing in or an API key. If you want Bronto monitors to open investigations, also do step 4 after you connect.

## 1. Find your region

Your Bronto sign-in address shows your region. Select the matching label when you connect.

| You sign in at | Label |
| --- | --- |
| `app.eu.bronto.io` | EU |
| `app.us.bronto.io` | US |

## 2. Enable MCP access in Bronto

A Bronto admin must enable MCP access once for the organization:

1. In Bronto, go to **Settings** > **Authentication**.
2. Enable the **MCP** login method, select **Configure**, choose the login methods allowed for MCP, and select **Save**.

## 3. Choose how to authenticate

### Sign in (default)

Select **OAuth** in the DevOps Agent connection form, sign in to Bronto with a login method enabled for MCP, and approve the requested access. DevOps Agent completes the OAuth flow; you don't need to create or paste a client secret.

The agent acts as the user who signs in, with that user's Bronto permissions. Use a user who can search the datasets the agent should investigate and view monitors. A dedicated user with the **Agent ReadOnly Role** gives the agent read-only access to logs, monitors, dashboards, integrations and SLOs. Do not use a shared administrator account.

### API key

Use a key when the agent must act as itself, not as a person.

1. In Bronto, go to **Settings** > **API Keys** and select **Create a new API Key**.
2. Name it after its purpose, such as `aws-devops-agent`.
3. Select the **API Agent ReadOnly Role**. It gives read-only access to logs, monitors, dashboards, integrations and SLOs, and no access to API keys, users or billing. Do not use a Search key, which can't read monitors, or Ingestion key.
4. Select **Create Key** and copy the key. It is shown only once.

When you connect, paste the key by itself into **Bronto API key**. DevOps Agent sends it in the `X-BRONTO-API-KEY` header.

## 4. Let Bronto monitors open investigations

After you connect, the console shows a webhook URL and a signing secret for your Agent Space. Add them to Bronto:

1. In Bronto, go to **Settings** > **Integrations** and select **AWS DevOps Agent**.
2. Paste the **Webhook URL** and the **Signing secret**, and save. Bronto builds and signs the request body for you, so you don't need to paste the body the console shows.
3. Open each monitor that should start an investigation, add the integration under **Notifications**, and save.

Bronto notifies the agent only when a monitor alerts. Each alert opens one investigation; warnings, no-data states and resolutions are not sent. Fill in each monitor's **Description**: it is sent with the alert, and the agent reads it as context.

Sending a test notification from a monitor opens a real investigation.

More in the Bronto docs: [AWS DevOps Agent](https://docs.bronto.io/ai-features/aws-devops-agent), [Hosted MCP Server](https://docs.bronto.io/ai-features/hosted-mcp) and [API Keys](https://docs.bronto.io/Account-Management/API-Keys).
