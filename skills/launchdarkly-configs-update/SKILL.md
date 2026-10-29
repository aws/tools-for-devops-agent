---
name: launchdarkly-configs-update
description: "Update, archive, and delete LaunchDarkly configs and their variations. Use when you need to modify config properties, change model parameters, update instructions or messages, archive unused configs, or permanently remove them."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Config Update & Lifecycle

You're using a skill that will guide you through updating, archiving, and deleting configs and their variations. Your job is to understand the current state of the config, make the changes, and verify the result.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `get-ai-config-health` -- assess config health before making changes (detects missing models, orphaned tools, empty configs)
- `get-ai-config` -- understand current state before making changes
- `update-ai-config` -- update config metadata (name, description, tags, archive)
- `update-ai-config-variation` -- update variation model, prompts, or parameters

**Optional MCP tools:**
- `delete-ai-config` -- permanently delete a config (irreversible)
- `delete-ai-config-variation` -- permanently delete a variation (irreversible)

## Core Principles

1. **Fetch Before Changing**: Always check the current state before modifying
2. **Verify After Changing**: Fetch the config again to confirm updates were applied
3. **Archive Before Deleting**: Archival is reversible; deletion is not

## Workflow

### Step 1: Assess Health and Understand Current State

Start with `get-ai-config-health` to get a structured health assessment. This detects:
- Variations with no model (show as "NO MODEL" in the UI)
- Variations with neither instructions nor messages
- Orphaned tool references (tools attached that don't exist in the project)
- Configs with no variations at all

The health verdict (`healthy`, `warning`, `unhealthy`) helps you prioritize what to fix.

Then use `get-ai-config` to review the full detail:
- Current mode (agent or completion)
- Existing variations and their models
- Current instructions or messages
- Attached tools and parameters

### Step 2: Make the Update

**Update config metadata** -- Use `update-ai-config`:
- Change name or description
- Add or replace tags
- Archive with `archived: true` (reversible)

**Update a variation** -- Use `update-ai-config-variation`:
- Switch model (provide new `modelConfigKey` and `modelName`)
- Change instructions or messages
- Tune parameters (temperature, max_tokens, etc.)
- Attach or detach tools via the parameters object

**Archive a config** -- Use `update-ai-config` with `archived: true`. Archiving is the **preferred** way to retire a config:
- It is reversible (unarchive with `archived: false`)
- The config is hidden from active lists but preserved
- After calling the archive, treat a successful response as confirmation and proceed to verification
- When a user says "remove", "retire", "decommission", or "no longer need", default to archiving unless they explicitly say "delete permanently"

**Delete** -- Use `delete-ai-config` or `delete-ai-config-variation` (irreversible, requires `confirm: true`). **Always suggest archiving first.** Only proceed with deletion if the user explicitly confirms they want permanent, irreversible removal.

### Step 3: Verify

Use `get-ai-config` to confirm the response shows your updated values.

**Report results:**
- Update applied successfully
- Config reflects changes
- Flag any issues or rollback if needed

## What NOT to Do

- Don't update production configs without testing in another variation first
- Don't change multiple things at once -- make incremental changes
- Don't skip verification
- Don't delete without explicit user confirmation -- always suggest archiving first
- Don't retry an update because the API response doesn't echo back the exact values you sent -- verify with `get-ai-config` instead

## More resources

To learn more about creating and managing variations, read [Create and manage config variations](https://launchdarkly.com/docs/home/agentcontrol/create-variation.md).

## Related Skills

- `launchdarkly-configs-variations` -- Create variations to test changes side-by-side
- `launchdarkly-tools` -- Update tool attachments
