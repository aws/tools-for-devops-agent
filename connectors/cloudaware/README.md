# Connect Cloudaware

Cloudaware keeps a continuously updated CMDB of your cloud accounts and
connected tools. This connector lets DevOps Agent query that inventory during an
investigation. Cloudaware reads the data from the Google BigQuery project that
Cloudaware exports your CMDB data to.

## Before you connect

You need three values: an API key, your Export Project and your SObjects Dataset.

### 1. Create an API key

1. In Cloudaware, go to **Admin Console** → **API CREDENTIALS** → **API Keys**.
2. Click **+ CREATE API KEY**.
3. Copy the key and store it securely. Anyone who has it can query your CMDB data.

Create a separate key for DevOps Agent, so you can revoke it without affecting
other tools.

Queries made with an API key run as a service account. Cloudaware configures it
for Cloudaware-managed BigQuery projects. If Cloudaware exports to your own
BigQuery project, ask your Technical Account Manager (TAM) to set it up. For
least privilege, give that service account read-only access to the SObjects
Dataset and nothing else.

### 2. Find your Export Project and SObjects Dataset

| Value | What it is |
| --- | --- |
| **Export Project** | The ID of the Google Cloud project that holds your exported Cloudaware data. |
| **SObjects Dataset** | The name of the BigQuery dataset in that project that describes your CMDB: object types, fields and relationships. |

Don't know your values? Ask your TAM at [tam@cloudaware.com](mailto:tam@cloudaware.com).

### 3. Connect

Enter the values in the connection form's **Cloudaware API key**,
**Export Project** and **SObjects Dataset** fields.

## What the agent can do

All tools only read data. None change your Cloudaware configuration or your
cloud resources, and the agent can read only what the API key's service account
can already read.

| Tool | What it does |
| --- | --- |
| `search_types` | Finds CMDB object types by keyword |
| `search_fields` | Lists the fields of a type, with labels and descriptions |
| `get_relationship_graph` | Shows how a type relates to other types |
| `analyze_field` | Returns statistics about the values of one field |
| `execute_query` | Runs a SQL query over your CMDB dataset |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `401 Unauthorized` | Check that your API key still exists in **Admin Console** → **API CREDENTIALS** → **API Keys**. |
| `403 Forbidden` on queries | The service account lacks BigQuery access. Ask your TAM. |
| Connected, but no data is returned | Check the Export Project and SObjects Dataset values. |

Still stuck? Contact your TAM at [tam@cloudaware.com](mailto:tam@cloudaware.com), or see the
[Cloudaware MCP documentation](https://docs.cloudaware.com/mcp-server-ai/).
