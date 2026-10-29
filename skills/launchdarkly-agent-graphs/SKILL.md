---
name: launchdarkly-agent-graphs
description: "Create and manage agent graphs — directed graphs of configs connected by edges with handoff logic. Use when building multi-agent workflows where configs route to each other."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Config Agent Graphs

You're using a skill that will guide you through creating and managing agent graphs in LaunchDarkly. Your job is to design the graph topology, create it with the right edges and handoffs, and verify the routing between config nodes.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `create-agent-graph` -- create a new graph with nodes and edges
- `get-agent-graph` -- inspect a graph's structure and edges
- `list-agent-graphs` -- browse existing graphs in the project

**Optional MCP tools:**
- `update-agent-graph` -- modify edges, root config, or description
- `delete-agent-graph` -- permanently remove a graph
- `get-ai-config` -- inspect individual configs that serve as nodes
- `create-ai-config` -- create new configs to use as graph nodes

## Core Concepts

### What Are Agent Graphs?

An agent graph is a directed graph where:
- **Nodes** are configs (each config is an agent with its own model, prompt, and tools)
- **Edges** define routing between configs (source -> target)
- **Handoff data** on edges controls how context is passed between agents
- **Root config** is the entry point — the first agent that receives user input

### When to Use Agent Graphs

| Scenario | Example |
|----------|---------|
| **Multi-step workflows** | Triage agent -> Specialist agent -> Summary agent |
| **Routing by intent** | Router agent decides which specialist handles the request |
| **Escalation chains** | L1 support -> L2 support -> Human handoff |
| **Pipeline processing** | Extract -> Transform -> Validate -> Store |

### Graph Structure

```
[Root Config] --edge--> [Config A] --edge--> [Config C]
                  \--edge--> [Config B]
```

Each edge has:
- `key` -- unique identifier for the edge
- `sourceConfig` -- the config key that routes FROM
- `targetConfig` -- the config key that routes TO
- `handoff` (optional) -- data/instructions passed during the transition

## Core Principles

1. **Design Before Building**: Map out nodes and edges on paper/whiteboard first
2. **One Agent, One Job**: Each node should have a clear, focused responsibility
3. **Root Config Is the Router**: The entry point should understand how to dispatch
4. **Handoff Data Matters**: Define what context flows between agents
5. **Verify the Full Path**: Test that routing works end-to-end

## Workflow

### Step 1: Design the Graph

Before creating anything:

1. Identify the agents (configs) needed — each is a graph node
2. Map the routing: which agent hands off to which?
3. Define handoff data: what context does each edge carry?
4. Identify the root config: which agent receives initial input?
5. Check existing graphs with `list-agent-graphs` to avoid duplicates
6. Check existing configs with `get-ai-config` to see what nodes already exist

### Step 2: Ensure Nodes Exist

Each node in the graph must be an existing config. If configs don't exist yet:
1. Use `create-ai-config` to create each agent config
2. Set up variations with appropriate models and prompts for each agent's role
3. Verify each config exists with `get-ai-config`

### Step 3: Create the Graph

Use `create-agent-graph` with:
- `projectKey` -- the project containing the configs
- `key` -- unique identifier for the graph
- `name` -- human-readable display name
- `description` (optional) -- explain the graph's purpose
- `rootConfigKey` -- the entry-point config key
- `edges` -- array of connections between configs

```json
{
  "projectKey": "my-project",
  "key": "support-triage-graph",
  "name": "Customer Support Triage",
  "description": "Routes customer queries to the appropriate specialist agent",
  "rootConfigKey": "triage-agent",
  "edges": [
    {
      "key": "triage-to-billing",
      "sourceConfig": "triage-agent",
      "targetConfig": "billing-specialist",
      "handoff": {"category": "billing", "priority": "normal"}
    },
    {
      "key": "triage-to-technical",
      "sourceConfig": "triage-agent",
      "targetConfig": "technical-specialist",
      "handoff": {"category": "technical", "priority": "normal"}
    }
  ]
}
```

### Step 4: Verify

1. Use `get-agent-graph` to confirm the graph was created with the correct structure
2. Verify edges connect the right source and target configs
3. Check that the root config key matches the intended entry point
4. Confirm handoff data is present on edges that need it

**Report results:**
- Graph created with N nodes and M edges
- Root config set correctly
- All edges verified

## Edge Cases

| Situation | Action |
|-----------|--------|
| Config doesn't exist yet | Create it first with `create-ai-config` before referencing in a graph |
| Circular routing | Allowed but warn user — ensure there's a termination condition in the agent logic |
| Single-node graph | Valid but unusual — consider if a graph is actually needed |
| Updating edges | Use `update-agent-graph` — provide the complete new edge list |

## What NOT to Do

- Don't create a graph before the config nodes exist
- Don't forget handoff data when agents need context from predecessors
- Don't create overly complex graphs — start simple and add nodes as needed
- Don't delete a graph without understanding if it's actively used in agent workflows

## Other Resources

To learn more, read [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs.md).
