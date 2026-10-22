# Changelog

## 1.0.0

- Initial version
- System prompt with Goal/Inputs/Approach/Constraints/Output structure
- Syncs a Confluence Cloud page tree or space into an attached custom memory store through the Atlassian MCP server
- Reads pages for up to 45 minutes per run and records the rest in a `sync-state` memory, so a large tree completes over several runs
- Re-runs update only pages whose version changed, keep each page's triage decision while its version holds, and remove memories only for pages confirmed deleted or moved out of the tree
- Ends with a setup error naming the fix when the URL, the memory store, or the Atlassian tools are missing
- Output is a sync report listing every page's outcome
