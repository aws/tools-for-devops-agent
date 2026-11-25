---
name: launchdarkly-configs-update
description: "Update, retire, and delete LaunchDarkly configs and their variations. Use when you need to modify config properties, change model parameters, update instructions or messages, take unused configs out of service, or permanently remove them."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: "nieblara"
  version: "1.0.0"
  summary: "Change, retire or delete a LaunchDarkly AgentControl config or variation, such as its model, parameters or prompts."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_MITIGATION, CHAT"
---

# Config Update & Lifecycle

You're using a skill that will guide you through updating, retiring, and deleting configs and their variations. Your job is to understand the current state of the config, make the changes, and verify the result.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `get-agent-configs` with `configKey` -- understand current state before making changes; add `section: "health"` to assess config health (detects missing models, orphaned tools, empty configs)
- `update-agent-config` with `resource: "config"` -- update config metadata (name, description, tags, default variation, maintainer)
- `update-agent-config` with `resource: "variation"` -- update variation model, prompts, or parameters
- `update-agent-config` with `resource: "targeting"` -- turn a config's targeting off in an environment to take it out of service

**Optional MCP tools:**
- `delete-agent-config` with `resource: "config"` -- permanently delete a config (irreversible)
- `delete-agent-config` with `resource: "variation"` -- permanently delete a variation (irreversible)

## Core Principles

1. **Fetch Before Changing**: Always check the current state before modifying
2. **Verify After Changing**: Fetch the config again to confirm updates were applied
3. **Turn Off Before Deleting**: Configs cannot be archived. Turning targeting off is reversible; deletion is not

## Workflow

### Step 1: Assess Health and Understand Current State

Start with `get-agent-configs` (configKey, `section: "health"`) to get a structured health assessment. This detects:
- Variations with no model (show as "NO MODEL" in the UI)
- Variations with neither instructions nor messages
- Orphaned tool references (tools attached that don't exist in the project)
- Configs with no variations at all

The health verdict (`healthy`, `warning`, `unhealthy`) helps you prioritize what to fix.

Then use `get-agent-configs` with the `configKey` to review the full detail:
- Current mode (agent or completion)
- Existing variations and their models
- Current instructions or messages
- Attached tools and parameters

To restore an earlier prompt or model, call `get-agent-configs` with `section: "versions"` and the `variationKey` to list that variation's saved versions, newest first, then pass the chosen version's model and messages to `update-agent-config` with `resource: "variation"`.

### Step 2: Make the Update

**Update config metadata** -- Use `update-agent-config` with `resource: "config"`:
- Change name or description
- Add or replace tags
- Set `defaultVariationKey` (what new environments serve by default; existing environments keep their fallthrough, so change those with `resource: "targeting"`)
- Set the maintainer with `maintainerId` or `maintainerTeamKey` (not both; an empty string removes it)

Configs cannot be archived: the tool rejects `archived`.

**Update a variation** -- Use `update-agent-config` with `resource: "variation"` and the `variationKey` (requires `confirm: true`; pass it after the user agrees):
- Switch model (provide new `modelConfigKey` and `modelName`)
- Rename it with `variationName`
- Change instructions or messages
- Tune parameters (temperature, max_tokens, etc.)
- Attach or detach tools with the top-level `tools` array

**Retire a config** -- Configs cannot be archived. To take one out of service but keep it recoverable, turn its targeting off with `update-agent-config`, `resource: "targeting"`, the `env`, `on: false`, and `confirm: true` (pass it after the user agrees). This is the **preferred** way to retire a config:
- It is reversible (turn targeting back on with `on: true`)
- The config, its variations, and their version history are preserved
- It is per environment: check `get-agent-configs` with `section: "status"` to see where the config is live, and ask which environments to turn off rather than guessing
- When a user says "remove", "retire", "decommission", or "no longer need", default to turning targeting off unless they explicitly say "delete permanently"

**Delete** -- Use `delete-agent-config` with `resource: "config"` or `resource: "variation"` (irreversible, requires `confirm: true`). **Always suggest turning targeting off first.** Only proceed with deletion if the user explicitly confirms they want permanent, irreversible removal.

### Step 3: Verify

Use `get-agent-configs` with the `configKey` to confirm the response shows your updated values.

**Report results:**
- Update applied successfully
- Config reflects changes
- Flag any issues or rollback if needed

## What NOT to Do

- Don't update production configs without testing in another variation first
- Don't change multiple things at once -- make incremental changes
- Don't skip verification
- Don't delete without explicit user confirmation -- always suggest turning targeting off first
- Don't pass `archived` -- configs cannot be archived and the tool rejects it
- Don't retry an update because the API response doesn't echo back the exact values you sent -- verify with `get-agent-configs` instead

## More resources

To learn more about creating and managing variations, read [Create and manage config variations](https://launchdarkly.com/docs/home/agentcontrol/create-variation.md).

## Related Skills

- `launchdarkly-configs-variations` -- Create variations to test changes side-by-side
- `launchdarkly-tools` -- Update tool attachments
