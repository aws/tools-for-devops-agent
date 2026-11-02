# Halo

Follow the steps below to set up a connection with Halo, allowing investigations to be triggered from tickets, and allowing the agent to use a custom set of tools.

## Create an Agent Space in Halo

1. In Halo, go to **Configuration** > **Integrations** > **AWS DevOps Agent** and enable the module by clicking the plus icon.
2. Add a new **Agent Space** and give it a name, such as the name of your Agent Space in AWS.
3. Under **Webhook Setup**, paste the webhook URL and secret your Agent Space shows in AWS.
4. In the MCP section, choose the **Agent to log in as**. The DevOps Agent's Halo function calls run with this agent's identity and permissions.
5. Copy the **Client Secret** for later.
6. Save the Agent Space.

Saving creates a linked application for the agent to authorise with, along with an MCP Toolset.

## Fill in the connection form

After saving, enter these values in the connection form:

| Field | Value | Example |
|---|---|---|
| **Halo domain** | The domain you use to access Halo | `example.haloitsm.com` |
| **MCP Toolset ID** | The Agent Space's **MCP Toolset ID** | `0f8fad5b-d9cb-469f-a165-70867728950e` |
| **Client ID** | The Agent Space's **Client ID** | |
| **Client Secret** | The secret you copied in step 5 | |

## Choose the tools

By default, the toolset includes functions to search knowledge base articles, search assets and add a note to a ticket. To change the available functions, select **Edit MCP Toolset** on the Agent Space.

## Let Halo tickets open investigations

1. On the Agent Space, under **Webhook Setup**, you can define the payload that Halo should send to the agent.
2. Go to **Configuration** > **Tickets** > **Actions** and add an action with the system use **Run AWS DevOps Agent**, then select your Agent Space.
3. Add the action to the Workflows where it should be used.

When the action is used on a ticket, Halo sends the ticket details to your Agent Space to open an investigation. Each request is logged on the Agent Space's **Request Logs** tab.
