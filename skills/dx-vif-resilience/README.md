# dx-vif-resilience

> **⚠️ Sample code:** This skill is sample code, not intended for production
> use without additional review and testing. Validate in a non-production
> environment first.

Assesses **Layer-3 failover resilience** across redundant AWS Direct Connect
virtual interfaces: whether the same prefixes are actually exchanged across
redundant VIFs, in both directions (routes received from on-prem and routes
advertised by AWS). Layer-1/2 redundancy (connections, locations, devices) is
commonly reviewed; asymmetric BGP prefix advertisement — a silent blackhole
that only appears during real failover — rarely is. This skill closes that gap.

## What it does

1. Discovers the DX estate (connections, VIFs, gateways, resiliency groups).
2. Resolves intended redundant VIF sets: confirmed intent (memory) → declared
   intent (resiliency groups) → inference (gateway attachment, type, ASN) →
   user confirmation.
3. Runs deterministic CIDR coverage analysis per set, both directions, via the
   companion [`dx-resilience-mcp`](../../mcp/dx-resilience-mcp/) server.
4. Reports gaps, partial-supernet residuals, empty tables, default routes,
   device-diversity issues, and broken resiliency-group pairings — with
   plain-language customer actions.

**Strictly read-only.** The skill never mutates anything; the companion MCP
server's IAM role cannot be granted any mutating action.

## Prerequisites

- Deploy and register the [`dx-resilience-mcp`](../../mcp/dx-resilience-mcp/)
  server in your Agent Space (SAM template included there).
- The connected account must own the Direct Connect VIFs (read-only
  `directconnect:Describe*/List*/Get*` is granted by the MCP server's template).

## Usage

Example chat prompts (no need to name the skill):

- "Is my Direct Connect setup resilient? Will failover actually work?"
- "Check whether the same prefixes are advertised over dxvif-aaa and dxvif-bbb."
- "We lost traffic when a DX connection went down last month — audit our VIF route symmetry."

For recurring audits, use the companion
[`dx-resilience-auditor`](../../custom-agents/dx-resilience-auditor/) custom
agent with a schedule trigger.

## Agent types

Generic (Chat / On-demand recommended).
