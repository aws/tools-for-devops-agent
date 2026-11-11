# dx-resilience-auditor

> **⚠️ Sample code:** Not intended for production use without additional
> review and testing. Validate in a non-production environment first.

Custom agent that audits **Layer-3 failover resilience** across redundant
Direct Connect VIFs — on demand via chat, or on a schedule (e.g. weekly). It
verifies that the prefixes exchanged over redundant VIFs actually cover each
other in both directions, and reports every prefix that would be blackholed if
a single VIF failed. Strictly read-only.

## Setup

Two steps are the same for everyone; the rest offers three equivalent
installation options.

**Always first:**

1. **Deploy the MCP server** — [`dx-resilience-mcp`](../../mcp/dx-resilience-mcp/)
   (SAM template) in the account owning the VIFs.
2. **Register it at the account level** — console → *Capability Providers* →
   *Register MCP Server*. Endpoint = the Function URL; auth = AWS SigV4 with
   the access role, Region of the stack, Service Name `lambda`. (Registration
   here does **not** yet attach it to any Agent Space.)
3. **Attach it to your Agent Space** — this is a separate, required step:
   select your Agent Space → *Capabilities* tab → *MCP Servers* → *Add* →
   choose `dx-resilience-mcp` → *Select specific tools* → enable
   `get_dx_topology`, `analyze_vif_resilience`, `compare_prefix_sets`,
   each classified **read-only**. You should then see "3 connected".

> **Critical — MCP tool identifiers are prefixed with the server name.** In the
> Agent Space toolbox the tools appear as `dx-resilience-mcp_get_dx_topology`
> (etc.), i.e. `<registered-server-name>_<tool>`. Two places must use these
> prefixed IDs: the skill's `enable_tools` (activates them when the skill loads)
> and the custom agent's tool list. Register the MCP server as exactly
> **`dx-resilience-mcp`** so the shipped IDs match; if you register it under a
> different name, replace the `dx-resilience-mcp_` prefix accordingly in both
> places. Bare names (no prefix) are silently accepted but never bind at
> runtime — the agent then aborts every run with "analysis tools not available".

**Then create the skill, agent, memory store, and trigger — pick ONE option:**

### Option A — GitHub import (recommended)

Requires a GitHub account connected to your Agent Space. Keeps the skill and
agent **in sync** with this repository: when we ship fixes, click *Sync*.

1. **Import the skill** — [`dx-vif-resilience`](../../skills/dx-vif-resilience/)
   via *Knowledge → Skills → Add skill → Import from repository* (directory URL).
2. **Import this agent** — *Agents → Create agent → Import*, pointing at this
   directory's `SYSTEM_PROMPT.md`. Assign the skill during import.
3. **Assign tools via Chat** (tools can't be set in the form):
   `Add the get_dx_topology, analyze_vif_resilience and compare_prefix_sets
   tools to my dx-resilience-auditor agent.`
4. **Attach a memory store** (recommended) — create a custom store (e.g.
   `dx-resilience-intent`) and attach it, so confirmed redundant sets and
   acknowledged asymmetries persist across runs:
   `Attach the dx-resilience-intent memory store to dx-resilience-auditor.`
5. **Add a schedule trigger** (optional) — agent detail page → *Triggers* →
   Schedule, e.g. `rate(7 days)` or `cron(0 9 ? * MON *)`. Optionally add a
   per-trigger prompt such as "Full audit, both directions, all redundant sets."

### Option B — Copy & paste (no prerequisites)

Same as Option A, but instead of importing: upload the skill directory as a
zip (*Add skill → Upload skill*), and create the agent via *Create agent →
Form*, pasting the contents of `SYSTEM_PROMPT.md` into the system prompt
field. Fully editable locally, but you won't receive upstream updates — watch
this repo and re-paste to update.

### Option C — CloudFormation (for IaC-managed Agent Spaces)

Provision the agent, memory store, and trigger declaratively with
[`assets-template.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/custom-agents/dx-resilience-auditor/assets-template.yaml) (`AWS::DevOpsAgent::Asset` +
`AWS::DevOpsAgent::Trigger`): it creates the custom agent, the
`dx-resilience-intent` memory store, and the weekly trigger in one stack.

```bash
aws cloudformation deploy \
  --template-file assets-template.yaml \
  --stack-name dx-resilience-auditor-assets \
  --parameter-overrides \
      AgentSpaceId=<your-agent-space-id> \
      SkillAssetId=<assetId of the imported dx-vif-resilience skill> \
      McpToolIds=<tool ids of the three registered MCP tools>
```

Notes:
- Import the skill first (Option A step 1 — even the CFN path imports the
  skill from GitHub rather than duplicating its content). Get `SkillAssetId`
  and the tool IDs from `aws devops-agent list-assets` / your Agent Space
  toolbox.
- The agent prompt is embedded in the template as `AGENT.md`;
  `SYSTEM_PROMPT.md` in this directory is the source of truth — keep them in
  sync.

## Usage

- Scheduled: runs unattended, produces an assessment artifact +
  recommendations; low-confidence set groupings are labeled for one-time
  confirmation.
- Chat: `Run dx-resilience-auditor and focus on dxvif-aaa and dxvif-bbb.`
- First run tip: confirm the proposed redundant sets in chat once — the agent
  writes them to the memory store and every later scheduled run uses them.

## Safety

All assigned tools are non-mutative; the MCP server's IAM role is structurally
read-only (`directconnect:Describe*/List*/Get*` only). The agent's prompt and
skill additionally forbid mutating actions, including BGP failover tests.
