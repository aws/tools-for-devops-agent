# Arize AX incident investigation

Teaches DevOps Agent how to investigate incidents in LLM applications and AI agents traced in Arize AX: which Arize AX MCP tools to call, in what order, and how to read the results. It covers model-call errors and latency, token or cost spikes, eval score drops, bad model output, triggered Arize monitors, and prompt changes.

## Prerequisites

- The Arize AX connector is added to the Agent Space, with its read tools enabled.
- The connector uses an Arize AX key with read access to the projects you want investigated. A read-only service key is recommended.

## Sample prompts

- "Our support chatbot started returning errors around 14:00 UTC. It's traced in the Arize project `support-bot`. Find the root cause."
- "The checkout agent got slow after this morning's deploy. Check Arize for what changed."
- "An Arize monitor on token count fired for `checkout-agent`. Investigate."

## What the agent does

1. Finds the project and sets the incident window.
2. Checks the project's Arize monitors.
3. Compares failing traces in the incident window with a baseline window.
4. Reads the spans of a few failing traces for errors, slow steps, token counts and agent loops.
5. Checks eval results and eval task runs.
6. Checks whether a prompt version changed near the incident start.
7. Reports the root cause with trace, span, monitor and prompt version IDs.

The skill only calls read tools.
