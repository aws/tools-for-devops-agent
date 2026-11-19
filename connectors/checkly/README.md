# Checkly

Steps to take in Checkly before you connect. Creating a service API key needs the **Owner** or **Admin** role in the Checkly account.

One connection reaches one Checkly account. To connect more than one account, create a key in each account and add the connector once per account.

## Create a service API key

The agent authenticates as the key, not as a person, so its calls are attributed to the key.

1. In Checkly, go to **Account settings** > **Service API keys** and select **Create service API key**.
2. Name it after its purpose, such as `aws-devops-agent`.
3. Under **Select a role**, choose **Read only**. The agent can then view all resources but cannot change anything or trigger checks.
4. Select **Create API key** and copy the key. Checkly shows it once.

## Find your account ID

Go to **Account settings** > **General** and copy the account ID. The **Service API keys** page also shows it in the example request, after `X-Checkly-Account:`.

## Connect

In the connection form, enter the key as **Service API key** and the ID as **Account ID**.

## Let the agent change things in Checkly

Reading works with a **Read only** key. The server also has tools that trigger check runs, start root cause analyses, and create or change checks, check groups and environment variables. To use them, create the key with a broader role instead: **Read & Run** to run checks, or **Read & Write** to also change things. Then enable those tools in DevOps Agent and decide which need approval.

## Let Checkly alerts open investigations

After you connect, the console shows a webhook URL, an `Authorization` header and a JSON body. Add them to Checkly:

1. Go to **Environment variables**, open the **Environment secrets** tab, and add a secret named `AWS_DEVOPS_AGENT_WEBHOOK_KEY`. Its value is the key from the header the console shows, without the word `Bearer`.
2. Go to **Alert channels**, select **Add more channels**, and choose **Webhook**. Give it a name such as `AWS DevOps Agent`, keep the method **POST**, and paste the webhook URL.
3. On the **Headers** tab, add a header named `Authorization` with the value `Bearer {{{AWS_DEVOPS_AGENT_WEBHOOK_KEY}}}`. Use three braces on each side. With two, Checkly escapes characters such as `=` in the key and the webhook rejects the request.
4. On the **Body** tab, replace the template with the body the console shows.
5. Under **Notification events**, keep **a check fails** selected and clear **a check recovers**. Recovery events do not open or close investigations.
6. Under **Subscriptions**, add the checks that should start an investigation, then save.
7. Select **Test alert channel**. On the **Response** tab, a working setup shows status `200` and the message `Webhook received`.

The alert sends the check's name, type, location and a link to the failing result. The agent then reads the result and its error through the connection.

For more detail, see the [Checkly MCP server documentation](https://www.checklyhq.com/docs/ai/mcp-server/).
