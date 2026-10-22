# Confluence Memory Sync — Custom Agent

> **Note:** This is sample code, not intended for production use without additional review and testing. Validate it in a non-production Agent Space first.

## Purpose

This custom agent turns a Confluence Cloud page tree or space into memories that AWS DevOps Agent can recall during investigations. It distills each relevant page into one memory, keeps an `overview` memory that summarizes the tree and indexes every synced page, and on later runs updates only the pages that changed.

## Key Capabilities

- Lists every page under a Confluence page, or every page in a space
- Distills each operationally relevant page into a memory whose facts are traceable to the page, in folders that mirror the Confluence tree
- Skips dated or non-operational pages (status reports, meeting notes, retrospectives) with a recorded reason
- Syncs a large tree over several runs, recording the pages it hasn't reached yet in a `sync-state` memory and syncing them first on the next run
- On re-runs, re-distills only pages whose Confluence version changed, and removes a memory only when its page is confirmed deleted or moved out of the tree
- Reads Confluence only; never edits it

## Prerequisites

- An AWS DevOps Agent space
- The Atlassian MCP server (`https://mcp.atlassian.com/v2/mcp`) connected to the Agent Space as an MCP server, authorized with OAuth or an Atlassian API token. The agent sees only the pages that identity can read.
- These Atlassian MCP tools allowlisted for the Agent Space: `getAccessibleAtlassianResources`, `searchConfluence`, and `getConfluenceContent` (named `searchConfluenceUsingCql` and `getConfluencePage` on older Atlassian MCP servers), plus `resolveConfluenceContentMacros` when the server offers it. The agent needs no write tools.
- A custom memory store for the synced pages — one store per Confluence tree. On the **Knowledge** page, choose the **Memories** tab, then **Create memory store**, and give it a description that says what the pages cover and when to read them.

## Creating the Agent

1. In the DevOps Agent web app, go to the **Agents** page and choose **Create agent**, then **Form**.
2. In **Name**, enter `confluence-memory-sync`.
3. Copy the content of `SYSTEM_PROMPT.md` from this directory into **System prompt**.
4. In **Memory stores**, select the store you created, then choose **Create agent**.
5. On the agent's page, choose **Edit**, then **Chat**, and ask: "Add the Atlassian getAccessibleAtlassianResources, searchConfluence, getConfluenceContent, and resolveConfluenceContentMacros tools to confluence-memory-sync." Confirm they appear under **Tools**. If any setup step is missing, the agent ends its run with an error that names the fix.

## Executing the Agent

Run the agent on demand with a prompt naming the Confluence URL and the store, for example:

```text
Sync https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Runbooks into the eng-runbooks memory store.
```

When only one writable store is attached, the prompt can omit the store name.

A run reads pages for up to 45 minutes, so a large tree takes several runs; the report says how many pages are still pending. Add a scheduled trigger with the same prompt to finish a large tree and keep the store current as pages change.

## Output

Each run, on demand or from a scheduled trigger, produces:

- **Memories** in the attached store, on the **Knowledge** page's **Memories** tab: one per synced page, in folders that mirror the Confluence tree; an `overview` that summarizes the tree and lists the synced pages; and a `sync-state` record of every other page and why it has no memory yet.
- **A sync report** as the run's final response, listing each page's outcome and how many pages are still pending.

## Memory Writes

The agent never changes Confluence: its Atlassian tools only list and read pages. It does change the attached memory store, with these tools, without an approval step, since custom agent runs are unattended:

| Tool | What it changes |
|:-----|:----------------|
| `fs_write`, `upload_memories` | Creates and updates page memories, `overview`, and `sync-state` in the attached store |
| `fs_delete` | Deletes the memory of a page that was deleted, moved out of the tree, or archived, or that changed and is now skipped |

Every write stays in the one store the run names, and only if it is attached to the agent and is not a managed store. The agent deletes a memory only after confirming its page's state, and only after all of the run's uploads succeed. Every memory update keeps the earlier versions, viewable on the **Memories** tab.

## Limits

- A custom agent run lasts at most one hour, so each run stops starting new pages after 45 minutes and leaves the rest pending for the next run.
- A memory store holds at most 200 memories: the `overview`, the `sync-state` record, and up to 198 page memories. Pages beyond that are reported as over capacity; to sync them, split the tree into smaller roots, each with its own store and run prompt.
- Each memory stays under the 100 KB memory size limit.

## Related

- [Creating a custom agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-creating-a-custom-agent.html)
- [DevOps Agent Memories](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-memories.html)
- [Connecting MCP Servers](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-capabilities-for-aws-devops-agent-connecting-mcp-servers.html)
