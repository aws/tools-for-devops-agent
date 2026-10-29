# Agent Graph Reference

> **Out of scope for the main migration workflow.** Read this only after a single-agent migration works end-to-end. The main `SKILL.md` workflow stops at single-agent because multi-agent orchestration is a meaningful jump in complexity and is still evolving in the SDK.

> **Python is still the richer surface.** `launchdarkly-server-sdk-ai` (Python) has the fully-documented graph API used in the traversal pattern below. `@launchdarkly/server-sdk-ai` (Node) exposes Agent Graph Definitions and graph metric tracking — consult the js-core source for the current Node API shape before wiring Node graph code; the Python pattern in this doc is canonical.

## What an agent graph is

An **agent graph** is a directed graph where each node is its own config (with its own instructions, model, parameters, and tools) and each edge carries routing metadata for handoffs. A supervisor node routes incoming requests to worker nodes based on the supervisor's output; worker nodes may themselves route to other workers or terminate. The graph lives in LaunchDarkly — both its topology and each node's config are managed as versioned resources and can be changed at runtime without redeploying.

Why use it:

- **Add or remove an agent by editing LaunchDarkly** — no redeploy
- **A/B test routing strategies** — target different graph topologies to different users
- **Roll out a new worker node to a percentage of traffic**
- **Guardrail a specific path** — attach a judge at a terminal node

## SDK surface (Python, from main)

The current Python API (verified against `launchdarkly-server-sdk-ai` main branch) exposes these methods on `LDAIClient`:

```python
def agent_graph(self, key: str, context: Context) -> AgentGraphDefinition:
    """Retrieve an agent graph by key."""

async def create_agent_graph(
    self,
    key: str,
    context: Context,
    tools: Optional[ToolRegistry] = None,
    default_ai_provider: Optional[str] = None,
) -> Optional[ManagedAgentGraph]:
    """Experimental — not production-ready. Returns a managed graph that can be invoked directly."""
```

**Use `agent_graph` for read-only traversal** (you drive the loop). **`create_agent_graph` + `ManagedAgentGraph.run` is experimental** and carries explicit production-not-ready warnings in the SDK source. Stick with `agent_graph` for now.

### `AgentGraphDefinition`

```python
graph_def: AgentGraphDefinition = ai_client.agent_graph("support-flow", context)

graph_def.is_enabled() -> bool
graph_def.root() -> Optional[AgentGraphNode]
graph_def.traverse(fn, execution_context=None)            # callback over nodes from root
graph_def.reverse_traverse(fn, execution_context=None)    # callback over nodes from terminals
graph_def.get_node(key: str) -> Optional[AgentGraphNode]
graph_def.get_child_nodes(node_key: str) -> List[AgentGraphNode]
graph_def.get_parent_nodes(node_key: str) -> List[AgentGraphNode]
graph_def.terminal_nodes() -> List[AgentGraphNode]
graph_def.get_tracker() -> Optional[AIGraphTracker]
```

### `AgentGraphNode`

```python
node.get_key() -> str
node.get_config() -> AIAgentConfig            # the same shape as agent_config() returns
node.get_edges() -> List[Edge]
node.is_terminal() -> bool
```

### `Edge`

```python
@dataclass
class Edge:
    key: str
    source_config: str
    target_config: str
    handoff: Optional[dict]                    # arbitrary dict; typically has a 'route' key
```

### `AIGraphTracker`

```python
tracker.track_invocation_success() -> None
tracker.track_invocation_failure() -> None
tracker.track_duration(duration: int) -> None          # milliseconds, graph-level total
tracker.track_total_tokens(tokens: TokenUsage) -> None
tracker.track_path(path: List[str]) -> None            # e.g. ["supervisor", "security", "support"]
tracker.track_redirect(source_key: str, redirected_target: str) -> None
tracker.track_handoff_success(source_key: str, target_key: str) -> None
tracker.track_handoff_failure(source_key: str, target_key: str) -> None
```

**Things that are NOT on the graph tracker:**

- `track_node_invocation` — not a public method. Use `track_path(execution_path)` at the end of traversal instead.
- `track_tool_call(node_key, tool_name)` — graph-level tool-call tracking does not exist. Track per-node tool calls via `node_tracker.track_tool_call(tool_name)` on each node's tracker (obtained via `node.get_config().create_tracker()`). Trackers returned via a graph traversal are automatically bound to the right graph key — do not pass `graph_key` as a keyword.
- `track_judge_response` — does not exist on `AIGraphTracker`. Record judge results at the config level via `LDAIConfigTracker.track_judge_result(result)` instead.
- No `track_request()`, no `track_duration()` per call — use `track_duration(total_ms)` once per traversal.

If you see older devrel-agents-tutorial code that calls `track_node_invocation`, `track_tool_call`, or pokes `graph_tracker._ld_client.track(...)` directly, that code targets an earlier API shape and needs updating. A PR is in flight against `launchdarkly-labs/devrel-agents-tutorial` to align the tutorial with the current SDK.

## Canonical traversal pattern

```python
from ldai.client import LDAIClient
from ldai.tracker import TokenUsage

async def execute_graph(ai_client: LDAIClient, graph_key: str, context, user_input: str):
    graph = ai_client.agent_graph(graph_key, context)

    if not graph.is_enabled():
        raise ValueError(f"Agent graph '{graph_key}' is not enabled")

    # Build a lookup from node key to AgentGraphNode so we can follow edges.
    nodes: dict[str, object] = {}
    graph.reverse_traverse(lambda node, _: nodes.update({node.get_key(): node}), {})

    graph_tracker = graph.get_tracker()
    start = time.time()
    execution_path = []
    shared_ctx = {"user_input": user_input, "final_response": "", "tool_calls": [],
                  "total_input_tokens": 0, "total_output_tokens": 0}

    current_node = graph.root()
    if not current_node:
        raise ValueError("Graph has no root node")

    prev_node_key = None
    visited = set()
    MAX_HOPS = 10
    hop_count = 0

    try:
        while current_node:
            node_key = current_node.get_key()
            if node_key in visited:
                raise ValueError(f"Cycle detected at {node_key}")
            visited.add(node_key)
            hop_count += 1
            if hop_count > MAX_HOPS:
                raise ValueError(f"Max hops exceeded: {hop_count}")

            config = current_node.get_config()
            execution_path.append(node_key)

            # Track handoff into this node
            if graph_tracker and prev_node_key:
                graph_tracker.track_handoff_success(prev_node_key, node_key)

            # Compute valid routes from outgoing edges
            edges = current_node.get_edges()
            valid_routes = [
                (edge.handoff or {}).get("route")
                for edge in edges
                if (edge.handoff or {}).get("route")
            ]

            # Execute this node — uses your existing agent-mode wiring
            result = await run_node(config, shared_ctx, valid_routes=valid_routes)

            # Per-node tool-call tracking lives on the node's config tracker.
            # Create one tracker per node execution (fresh runId) and reuse it
            # for every tracking call inside that node.
            if result.get("tool_calls"):
                node_tracker = config.create_tracker()
                for tool_name in result["tool_calls"]:
                    node_tracker.track_tool_call(tool_name)

            # Merge node result into shared context
            update_shared_ctx(shared_ctx, result)

            # Terminal?
            if not edges or current_node.is_terminal():
                break

            # Pick next node by matching the node's routing_decision to an edge handoff
            next_node = select_next_node(edges, result, nodes, graph_tracker, source_key=node_key)
            prev_node_key = node_key
            current_node = next_node

        # Graph-level metrics
        if graph_tracker:
            graph_tracker.track_path(execution_path)
            graph_tracker.track_duration(int((time.time() - start) * 1000))
            if shared_ctx["total_input_tokens"] or shared_ctx["total_output_tokens"]:
                graph_tracker.track_total_tokens(TokenUsage(
                    input=shared_ctx["total_input_tokens"],
                    output=shared_ctx["total_output_tokens"],
                    total=shared_ctx["total_input_tokens"] + shared_ctx["total_output_tokens"],
                ))
            graph_tracker.track_invocation_success()

    except Exception:
        if graph_tracker:
            graph_tracker.track_invocation_failure()
        raise

    return shared_ctx


def select_next_node(edges, result, nodes, graph_tracker, source_key: str):
    routing = result.get("routing_decision", "").lower().strip() if result.get("routing_decision") else None
    route_map = {
        (edge.handoff or {}).get("route", "").lower().strip(): edge.target_config
        for edge in edges
        if (edge.handoff or {}).get("route")
    }

    if routing and routing in route_map:
        return nodes.get(route_map[routing])
    if routing:
        # Unrecognized route — signal failure with source + attempted target
        if graph_tracker:
            graph_tracker.track_handoff_failure(source_key, routing)
    # Fallback: first edge
    if edges:
        return nodes.get(edges[0].target_config)
    return None
```

## Migrating a multi-agent app to graphs

Do this in phases, not one big bang:

1. **Pick one worker node to migrate first.** Use the single-agent skill workflow on that worker in isolation — extract, wrap, tools, tracking, evals. Leave the rest of the multi-agent app hardcoded.
2. **Confirm the wrapped worker runs in production** for the traffic it serves today, with metrics flowing in the Monitoring tab.
3. **Migrate the supervisor** the same way — single-agent workflow — but keep its routing logic hardcoded initially (a big if/elif over the other workers).
4. **Create the agent graph in LaunchDarkly** via the UI. Define nodes (one per worker + supervisor) and edges (with `handoff.route` metadata).
5. **Replace the hardcoded router** with the traversal pattern above. Call `ai_client.agent_graph(...)` instead of assembling the pipeline by hand.
6. **Verify the Monitoring tab** shows the graph-level metrics (`track_path`, `track_duration`, `track_total_tokens`, handoff success/failure counts) in addition to the per-node metrics.
7. **Only then** start moving routing decisions into LaunchDarkly edges and using targeting to change the graph topology per user segment.

Each phase is reversible. If something breaks at phase 5, the supervisor can fall back to the hardcoded router while the graph issue is fixed.

## Limitations to know about

- **Python has the canonical surface.** The Python traversal pattern above is what this doc covers in full. For Node graphs, consult the `@launchdarkly/server-sdk-ai` source for the current API.
- **`create_agent_graph` is experimental.** Do not build production features on `ManagedAgentGraph.run`. Use the traversal pattern above.
- **Graph tracker is less granular than the config tracker.** If you want per-node duration or per-node token breakdowns, obtain a per-node tracker via `node.get_config().create_tracker()` — the graph tracker handles totals only.
- **Cycles must be caught in your code.** The SDK does not stop cycle traversal automatically; track `visited` and `hop_count` yourself.
- **Fallback shape.** There is no `AIAgentGraphDefault`. Each node's `AIAgentConfig` still takes an `AIAgentConfigDefault`, but the graph itself has no aggregate fallback. If `agent_graph` fails, handle it at the app level — typically by falling back to the hardcoded pre-migration pipeline.

## Resources

- Python SDK source: https://github.com/launchdarkly/python-server-sdk-ai
  - `packages/sdk/server-ai/src/ldai/agent_graph/__init__.py` — `AgentGraphDefinition` and `AgentGraphNode`
  - `packages/sdk/server-ai/src/ldai/tracker.py` — `AIGraphTracker` (near the bottom of the file)
  - `packages/sdk/server-ai/src/ldai/client.py` — `LDAIClient.agent_graph` and `create_agent_graph`
- Node SDK source: https://github.com/launchdarkly/js-core/tree/main/packages/sdk/server-ai
- SDK CHANGELOGs (for per-release breaking changes and the version each method landed in):
  - Python: https://github.com/launchdarkly/python-server-sdk-ai/blob/main/packages/sdk/server-ai/CHANGELOG.md
  - Node: https://github.com/launchdarkly/js-core/blob/main/packages/sdk/server-ai/CHANGELOG.md
- Devrel reference implementation (Python, after PR alignment): https://github.com/launchdarkly-labs/devrel-agents-tutorial on the `tutorial/agent-graphs` branch
