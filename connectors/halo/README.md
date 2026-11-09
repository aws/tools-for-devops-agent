# Halo

Follow the steps below to set up a connection with Halo, allowing investigations to be triggered from tickets, and allowing the agent to use a custom set of tools.

## Create an Agent Space in Halo

1. In Halo, go to **Configuration** > **Integrations** > **AWS DevOps Agent** and enable the module by clicking the plus icon.
2. Add a new **Agent Space** and give it a name, such as the name of your Agent Space in AWS.
3. In the MCP section, choose the **Agent to log in as**. The DevOps Agent's tool calls will run with this agent's identity and permissions.

## Fill in the connection form

Using the details displayed in Halo, fill in the AWS connection form:

| Field | Value | Example |
|---|---|---|
| **Halo domain** | The domain you use to access Halo | `example.haloitsm.com` |
| **Halo port** | `443`, unless your self-hosted Halo uses another port | `443` |
| **MCP Toolset ID** | The Agent Space's **MCP Toolset ID** | `0f8fad5b-d9cb-469f-a165-70867728950e` |
| **Client ID** | The Agent Space's **Client ID** | |
| **Client Secret** | The Agent Space's **Client Secret** | |

If your Halo is self-hosted and isn't reachable from the internet on port 443, create a [private connection](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-to-privately-hosted-tools.html) to it, with its port in the port ranges, and select it when you connect.

Once the fields have been completed, save the Agent Space in Halo before submitting the connection form.

## Choose the tools

By default, the toolset includes functions to search knowledge base articles, search assets and add an internal note to a ticket. To change the available functions, select **Edit MCP Toolset** on the Agent Space.

## Let Halo tickets open investigations

1. On the Halo Agent Space, under **Webhook Setup**, paste the webhook URL and secret that AWS shows after you connect. You can also define the payload that Halo should send to the agent here.
2. Go to **Configuration** > **Tickets** > **Actions** and add an action with the system use **Run AWS DevOps Agent**, then select your Agent Space.
3. Add the action to the Workflows where it should be used.

When the action is used on a ticket, Halo sends the ticket details to your Agent Space to open an investigation. Each request is logged on the Agent Space's **Request Logs** tab.