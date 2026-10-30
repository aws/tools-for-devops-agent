---
name: launchdarkly-configs-variations
description: "Experiment with configs by creating and managing variations. Helps you test different models, prompts, and parameters to find what works best through systematic experimentation."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Config Variations

You're using a skill that will guide you through testing and optimizing configs through variations. Your job is to design experiments, create variations, and systematically find what works best.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Primary MCP tool:**
- `clone-ai-config-variation` -- clone a baseline variation with selective overrides (recommended for experimentation)

**Alternative MCP tools (for more control):**
- `get-ai-config` -- review existing variations before adding new ones
- `create-ai-config-variation` -- create new variations from scratch

**Optional MCP tools:**
- `update-ai-config-variation` -- refine a variation after creation
- `delete-ai-config-variation` -- remove variations that didn't work out

## Core Principles

1. **Test One Thing at a Time**: Change model OR prompt OR parameters, not all at once
2. **Have a Hypothesis**: Know what you're trying to improve
3. **Measure Results**: Use metrics to compare variations
4. **Verify via Tool**: The agent fetches the config to confirm variations exist

## Workflow

### Step 1: Identify What to Optimize

What's the problem? Cost, quality, speed, accuracy? How will you measure success?

### Step 2: Design the Experiment

| Goal | What to Vary |
|------|--------------|
| Reduce cost | Cheaper model (e.g., `gpt-4o-mini`) |
| Improve quality | Better model or more detailed prompt |
| Reduce latency | Faster model, lower `max_tokens` |
| Increase accuracy | Different model family (Claude vs GPT-4) |

### Step 3: Create Variations (Recommended: Clone with Overrides)

Use `clone-ai-config-variation` to duplicate the baseline and override only what you're testing. The tool reads the source variation, merges your overrides, and creates the new variation. Everything you **don't** pass is inherited from the source automatically.

**Required fields:**
- `sourceVariationKey` -- the baseline to clone from
- `key` and `name` -- identifiers for the new variation (e.g., `gpt4o-mini-cost-test`)

**Override ONLY the fields you are testing.** Leave all other fields unset -- do not pass them even if you know their current values. The clone tool inherits them from the source. This enforces the one-variable-at-a-time principle:

- Testing a cheaper model? Pass only `modelConfigKey` and `modelName`. Do NOT pass `instructions`, `messages`, or `parameters`.
- Testing different instructions? Pass only `instructions`. Do NOT pass `modelConfigKey` or `modelName`.
- Testing a parameter? Pass only `parameters`. Do NOT pass model or prompt fields.

The response returns both the source and created variation, so you can immediately verify the diff.

### Step 3 (Alternative): Create from Scratch

If you need full control, use `get-ai-config` first to review the current state, then `create-ai-config-variation` with all fields specified manually. Always fetch before creating so you understand the existing config's mode, model, and parameters.

### Step 4: Verify

If you used `clone-ai-config-variation`, the response includes both source and created variations for immediate comparison. Otherwise, use `get-ai-config` to confirm.

**Report results:**
- Variations created with correct models and parameters
- Only the intended variable differs between variations
- Flag any issues

**Note on API responses:** After calling a creation or clone tool, treat a successful response as confirmation that the operation succeeded. The API response may not echo back every field you sent (e.g., model fields may show defaults). Do not retry or assume failure based on response field values alone -- verify with `get-ai-config` if needed.

## modelConfigKey Format

Required for models to display in the UI. Format: `{Provider}.{model-id}`:
- `OpenAI.gpt-4o`, `OpenAI.gpt-4o-mini`
- `Anthropic.claude-sonnet-4-5`, `Anthropic.claude-3-5-sonnet`

## Safety: Protect the Baseline

When the user wants to try a different model, prompt, or parameters, **always create a new variation alongside the baseline**. Never modify or delete the existing baseline variation. This applies even if the user says "replace" or "switch" -- the correct action is to create a new variation and let targeting/rollouts control traffic, not to edit the original.

- Use `clone-ai-config-variation` or `create-ai-config-variation` to add the new variation
- Do NOT use `update-ai-config-variation` on the baseline to change its model or instructions
- Do NOT use `delete-ai-config-variation` on the baseline
- Explain to the user that keeping the baseline enables comparison and safe rollback

## What NOT to Do

- Don't test too many things at once -- change one variable per variation
- Don't pass unchanged fields when cloning -- let the tool inherit them from the source
- Don't forget modelConfigKey (variations without it show as "NO MODEL" in the UI)
- Don't make decisions on small sample sizes
- Don't modify or remove the baseline variation -- create new variations alongside it
- Don't use `update-ai-config-variation` to "replace" a baseline -- create a new variation instead
   
## More resources

To learn more about creating and managing variations, read [Create and manage config variations](https://launchdarkly.com/docs/home/agentcontrol/create-variation.md).

## Related Skills

- `launchdarkly-configs-create` -- Create the initial config
- `launchdarkly-configs-update` -- Refine based on learnings
