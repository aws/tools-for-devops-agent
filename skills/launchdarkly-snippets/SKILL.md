---
name: launchdarkly-snippets
description: "Create and manage prompt snippets — reusable text blocks referenced inside config variation prompts. Keeps common instructions, personas, and guardrails consistent across multiple configs."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# Config Prompt Snippets

You're using a skill that will guide you through creating and managing prompt snippets in LaunchDarkly. Your job is to identify reusable text, create snippets, reference them in config variations, and verify everything is wired correctly.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `create-prompt-snippet` -- create a new reusable text block
- `list-prompt-snippets` -- browse existing snippets in the project
- `get-prompt-snippet` -- inspect a specific snippet's content

**Optional MCP tools:**
- `update-prompt-snippet` -- edit a snippet's text, name, or tags
- `delete-prompt-snippet` -- permanently remove a snippet
- `update-ai-config-variation` -- update variation prompts to reference snippets

## Core Concepts

### What Are Prompt Snippets?

Prompt snippets are named, versioned text blocks stored at the project level. They contain reusable pieces of prompt text — personas, guardrails, output format instructions, domain knowledge — that can be shared across multiple config variations.

When a snippet is updated, a new version is created. Config variations that reference the snippet can pick up the latest version, keeping all your configs in sync.

### When to Use Snippets

| Scenario | Example |
|----------|---------|
| **Shared persona** | "You are a helpful customer support agent for Acme Corp..." used by 5 different configs |
| **Safety guardrails** | "Never reveal internal pricing. Never generate code that accesses production databases." |
| **Output format** | "Always respond in JSON with keys: answer, confidence, sources." |
| **Domain knowledge** | Company-specific terminology, product names, or process descriptions |
| **Regulatory text** | Compliance disclaimers that must appear in every response |

### When NOT to Use Snippets

- Text that is unique to a single variation — just put it in the prompt directly
- Dynamic content that changes per-request — use template variables instead
- Entire prompts — snippets are building blocks, not complete prompts

## Core Principles

1. **Reusability First**: Only create a snippet if the text will be used in 2+ places
2. **Single Responsibility**: Each snippet should cover one concern (persona OR guardrails, not both)
3. **Descriptive Keys**: Use keys like `safety-guardrails`, `json-output-format`, `support-persona`
4. **Tag for Discovery**: Add tags so teammates can find snippets by category
5. **Verify References**: After creating a snippet, confirm it appears in the project

## Workflow

### Step 1: Identify Reusable Text

Before creating snippets, understand what's shared:

1. List existing configs in the project using `get-ai-config` for each
2. Look for repeated text across variation prompts
3. Identify text that should stay consistent (guardrails, personas, formats)
4. Check existing snippets with `list-prompt-snippets` to avoid duplicates

### Step 2: Create Snippets

Use `create-prompt-snippet` with:
- `key` -- unique identifier (lowercase, hyphens, e.g. `safety-guardrails`)
- `name` -- human-readable display name
- `text` -- the reusable prompt text content
- `description` (optional) -- explain when/why to use this snippet
- `tags` (optional) -- categorize for discovery (e.g. `["guardrails", "safety"]`)

```json
{
  "projectKey": "my-project",
  "key": "support-persona",
  "name": "Customer Support Persona",
  "text": "You are a friendly, knowledgeable customer support agent for Acme Corp. Always greet the customer by name when available. Be empathetic but concise. If you don't know the answer, say so honestly and offer to escalate.",
  "description": "Standard persona for all customer-facing support configs",
  "tags": ["persona", "support"]
}
```

### Step 3: Verify

1. Use `get-prompt-snippet` to confirm the snippet was created with the correct text
2. Use `list-prompt-snippets` to see it in the project listing
3. Check that version is 1 for newly created snippets

**Report results:**
- Snippet created with key, name, and text
- Version number confirmed
- Tags applied correctly

### Step 4: Update Snippets (When Needed)

Use `update-prompt-snippet` to modify an existing snippet. Only pass the fields you want to change:

```json
{
  "projectKey": "my-project",
  "snippetKey": "safety-guardrails",
  "text": "Updated guardrail text with new compliance requirements..."
}
```

Each update creates a new version. Existing config variations referencing the snippet can pick up the new version.

## Edge Cases

| Situation | Action |
|-----------|--------|
| Snippet key already exists | Use `get-prompt-snippet` to check, then either update or choose a different key |
| Very long text | Snippets can hold large blocks — but consider splitting into multiple snippets for modularity |
| Snippet referenced by configs | Update carefully — changes propagate to all referencing configs |
| Deleting a referenced snippet | Warn the user that configs will lose the reference. Use `delete-prompt-snippet` with `confirm: true` |

## What NOT to Do

- Don't create snippets for text used in only one place
- Don't put an entire prompt in a single snippet — break it into focused pieces
- Don't delete snippets without checking which configs reference them
- Don't duplicate existing snippets — check `list-prompt-snippets` first

## More resources

To learn more about setting up prompt snippets in the LaunchDarkly UI, read [Prompt snippets](https://launchdarkly.com/docs/home/agentcontrol/snippets.md).
