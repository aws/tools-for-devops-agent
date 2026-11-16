# Arize AX

Steps to take in Arize AX before you connect.

## Choose your region

Pick the endpoint that matches where your Arize AX account lives:

| You sign in at | Pick |
|---|---|
| `app.arize.com` | **Global (US)** |
| `app.eu-west-1a.arize.com` | **EU (eu-west-1a)** |
| `app.ca-central-1a.arize.com` | **Canada (ca-central-1a)** |

A key works only in the region where it was created. A key from the wrong region fails with a permission error.

## Create a service key

Use a service key so the agent acts as itself, its calls are attributed to the key, and it keeps working if the person who created it leaves. Creating one needs the Admin or Member role.

1. In Arize AX, go to **Settings** > **Account Settings** > **Service Keys** and select **+ New Service Key**.
2. Name it after its purpose, such as `aws-devops-agent`.
3. Under **Organizations & Spaces**, add each organization that holds the projects you want the agent to investigate. Leave the **Organization Role** at **Read-Only**.
4. Add each space and set its role to **Read-Only Member**.
5. Select **Create Service Key** and copy the key. Arize AX shows it once. It starts with `ak-`.
6. Paste the key into the connection form. Enter the key only; the console adds `Bearer`.

A user key from **Settings** > **Account Settings** > **API Keys** also works, but it has every permission you have, including delete.

## Choose which tools to enable

The server exposes read tools and tools that create, update or delete Arize AX data. Annotations mark each one, and the server does not enforce them: with a key that has write access, a destructive call runs as soon as it is sent.

For investigations, enable only the read tools (`get_*`, `list_*`, `search_*` and `server_info`), including `get_prompt_label`. Leave all non-read tools disabled. If you separately enable any non-read tool, require explicit operator approval for each call; this includes `create_*`, `insert_*`, `update_*`, `delete_*`, `annotate_*`, `assign_*`, task-run actions and prompt-label changes. A tool can change data even when its `destructiveHint` is false.

## Install and activate the investigation skill

After associating the connector with your Agent Space, install the recommended `arize-incident-investigation` skill. Confirm it is **Active** and available to Incident Triage, Incident RCA and On-demand (CHAT). A connected MCP server does not by itself confirm skill installation or activation.

For the AWS skill import and activation steps, see [Managing Skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#managing-skills).

## Limits

Calls count against your Arize AX REST rate limits, shared by all keys of the same user: 100 requests per minute per endpoint by default, and 10 per minute for span listing. Each call times out after 30 seconds.

For more detail, see the [Arize AX MCP server docs](https://arize.com/docs/api-clients/mcp/overview).

## Support

For technical help, use your existing Arize support channel or email [support@arize.com](mailto:support@arize.com). See the [API support contacts](https://arize.com/docs/ax/rest-reference/overview#support).
