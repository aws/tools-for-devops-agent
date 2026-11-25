# Runtime sessions (documented facts)

Use these before guessing at session behaviour; cite the pages.
[Sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html),
[Quotas](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html).

- Each session gets its own microVM. A new session (and microVM) is created on the first invoke with a
  new `runtimeSessionId`; reusing the same ID routes later calls to the same microVM and keeps context.
- The session header depends on the runtime's protocol: **MCP → `Mcp-Session-Id`**; HTTP, A2A and
  AG-UI → `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`. A wrong or missing header on an MCP runtime
  means requests are not routed to the same microVM (cold starts, lost in-memory state).
- Quotas (new session creation 25 TPS, data plane 1,000 TPS, active sessions 5,000 in us-east-1/
  us-west-2, 2 vCPU / 8 GB per Runtime session) and how to tell which one a 429 hit: **LLM-AC-011**. Throttling
  with a fresh session ID per call points at the session-creation rate; recommend a stable ID per
  user/conversation and an alarm below the quota.
- Idle timeout 15 min (default), maximum lifetime 8 h on microVMs; the next invoke with the same ID
  provisions a new microVM. A brief retryable HTTP 409 can occur while a session is being provisioned.
- A session ID only routes calls to the same microVM; the runtime does not store conversation history.
  In-process state is lost on idle timeout, lifetime end or a new microVM, and is never shared between
  runtimes. Forgotten turns with a stable session ID: **LLM-AC-012** (AgentCore Memory).
