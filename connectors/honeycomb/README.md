# Honeycomb

Steps to take in Honeycomb before you connect. Creating API keys and team integrations needs the Honeycomb **Team Owner** role.

## Choose your region

Pick the endpoint that matches where your Honeycomb team lives:

| You sign in at | Pick |
|---|---|
| `ui.honeycomb.io` | **US** |
| `ui.eu1.honeycomb.io` | **EU** |

## Connect by signing in (default)

No setup is needed in Honeycomb. You sign in when you connect, and the agent acts as you, with your Honeycomb role. On the consent screen, choose **Read**. Read-only users get an error if they choose **Read-write**.

To review or revoke the connection later, go to **Account** > **Integrations** in Honeycomb.

## Connect with an API key

Use a key when the agent must act as itself, not as a person. The key has read-only access, and its calls are attributed to the key.

1. In Honeycomb, go to **Account** > **Team Settings** > **API Keys** and create a **Management** key. Other key types are rejected.
2. Name it after its purpose, such as `aws-devops-agent`.
3. Grant **Model Context Protocol: Read** and **Environments: Read**. Leave every other permission off.
4. Copy the **Key ID** and **Key Secret**.
5. In the connection form, enter them as one value, joined by a colon: `KEY_ID:KEY_SECRET`.

One key connects to one Honeycomb team. To connect more than one team, create a key in each team and add the connector once per team.

## Let the agent create boards, SLOs and triggers

Reading works with read-only access. Creating things in Honeycomb, such as a board, SLO or trigger, needs write access. To allow it:

- **Signing in:** choose **Read-write** on the consent screen. Read-only users can't create anything.
- **API key:** also grant **Write** under **Model Context Protocol**.

The agent creates something only when you ask for it, and only after you approve its plan.

## Let Honeycomb Triggers open investigations

After you connect, the console shows a webhook URL, an `Authorization` header and a JSON body. Add them to Honeycomb:

1. Go to **Account** > **Team Settings** > **Integrations**. Under **Trigger and SLO Recipients**, select **Add Integration**.
2. Set **Provider** to **Webhook**, give it a name such as `aws-devops-agent`, and paste the webhook URL. Leave **Shared Secret** empty.
3. On the **Headers** tab, add a header named `Authorization` whose value is the header value the console shows.
4. On the **Payload** tab, turn on **Triggers** and replace the template with the body the console shows. Select **Add**.
5. Open each Trigger that should start an investigation, add the integration under **Recipients**, and save.

Fill in each Trigger's **Description**. It is sent with the alert, and the agent reads it as context: state what the Trigger watches and where to look first.

For more detail, see [Connect Honeycomb and AWS DevOps Agent](https://docs.honeycomb.io/integrations/aws-devops-agent).
