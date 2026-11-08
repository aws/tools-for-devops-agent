# Spellwarden

Spellwarden checks the skills and MCP servers that AI agents load, and reports findings, trust scores and alerts. With this connector the agent can answer questions about them, such as which skills in your organisation have open critical findings or whether an MCP server passed its last check.

## Before you start

You need a Spellwarden account and organisation at [dash.spellwarden.ai](https://dash.spellwarden.ai). The connector works on every plan and during the trial.

## Connect

### Sign in (recommended)

1. Choose **Spellwarden**, then **Sign in**.
2. Sign in to Spellwarden. Spellwarden asks which organisation the Agent Space may see, and whether the connection is **Read only** (the default) or **Read and write**.
3. Choose **Read only** and the organisation this Agent Space should see, then approve.

The connection acts as you, in that one organisation only, and the agent is told so when it connects and whenever it calls `list_organisations`. It lasts 365 days. To end it, open your account's **Connected apps** in the Spellwarden dashboard and revoke it.

### Or use an API key

In the Spellwarden dashboard, open **Settings**, **API keys** and create a key with **Read** access. Paste it as the Spellwarden API key. A key belongs to one organisation.

## Tools

Read-only tools. Allow these:

`list_organisations`, `get_organisation`, `list_skills`, `get_skill`, `list_findings`, `get_trust_score`, `list_policy_packs`, `list_registry_entries`, `get_runtime_inventory`, `get_eval_run`, `get_migration_report`, `list_mcp_servers`, `list_agent_space_connections`.

Mutative tools. They change data in your Spellwarden organisation, so leave them off; a Read only connection or a read key refuses them anyway:

- `scan_skill` starts a scan of a skill.
- `add_mcp_server` adds an MCP server to the organisation and checks it.
- `start_eval_run` starts an evaluation run, which counts against the organisation's monthly runs.
- `export_eval` and `export_policy_pack` create export files.

No tool deletes anything.

## Example prompts

- "Which skills in our Spellwarden organisation have open critical or high findings, and what does each finding mean?"
- "Did the MCP servers we use pass their last Spellwarden check? List any that failed and why."
- "What is our organisation's trust score, and what would raise it?"

## Check what this Agent Space loads

The connector gives the agent Spellwarden's tools. To have Spellwarden also check the skills, instruction files and MCP servers this Agent Space loads, every hour, deploy the stack at [github.com/spellwarden-ai/devops-agent-stack](https://github.com/spellwarden-ai/devops-agent-stack). The guide is at [spellwarden.ai/docs/aws-devops-agent](https://spellwarden.ai/docs/aws-devops-agent).

## Support

See [spellwarden.ai/docs/aws-devops-agent](https://spellwarden.ai/docs/aws-devops-agent#support). Report a security issue to security@spellwarden.ai.
