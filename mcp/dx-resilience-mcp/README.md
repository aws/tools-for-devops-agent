# dx-resilience-mcp

> **⚠️ Proof of Concept / Sample code:** This project is sample code and is not
> intended for production use without additional review and testing. Validate it
> in a non-production account before using it with production workloads.

> **⚠️ DevOps Agent only:** This MCP server is designed exclusively for
> integration with AWS DevOps Agent via Streamable HTTP + SigV4. It is NOT
> compatible with local MCP clients (Kiro, Cursor, VS Code) that use stdio
> transport.

MCP server for AWS DevOps Agent that answers a question no describe API answers
on its own: **if one of your redundant Direct Connect VIFs fails, which prefixes
stop being reachable?**

Direct Connect resiliency is usually assessed at Layer 1/2 — redundant
connections, diverse locations and devices. This server assesses **Layer 3**:
whether the same prefixes are actually exchanged across redundant VIFs, in both
directions, using the `ListVirtualInterfaceRoutes` API and exact CIDR
containment/set-difference math. A prefix advertised on one VIF with no
coverage on its peer is a silent blackhole that only appears during a real
failover.

## Why not let the agent do the math?

CIDR coverage is exact set arithmetic where a false "covered" is precisely the
failure this tool exists to catch. Route tables run to hundreds of prefixes per
VIF; results must be identical run-to-run for scheduled audits. This server
fetches routes and computes coverage deterministically — route tables never
transit the model's context.

## Tools

| Tool | AWS calls | Purpose |
|---|---|---|
| `get_dx_topology` | Describe/List only | Joined view of connections, VIFs, gateways, and resiliency groups, for redundant-set resolution |
| `analyze_vif_resilience` | Describe/List only | Fetch live routes for a redundant VIF set (both directions, paginated) and run full coverage analysis: gaps, partial-supernet residuals, pairwise failover impact, BGP health, device diversity |
| `compare_prefix_sets` | none | Pure coverage math on caller-supplied prefix lists |

### Finding classes

- **gap** — prefix present on exactly one VIF, zero coverage on all peers → guaranteed blackhole if that VIF fails.
- **partial_supernet** — a supernet on one VIF only partially covered by more-specifics on a peer. The exact uncovered residual is computed (e.g. `10.10.0.0/22` vs peer `10.10.1.0/24` → residual `10.10.0.0/24`, `10.10.2.0/23`). Severity is conditional: the customer must confirm whether workloads exist in the residual ranges.
- **partial** — present on some VIFs, missing from at least one (3+ VIF sets).
- **covered** — exact or full supernet coverage on every peer.
- Default routes, empty tables (BGP up, zero routes), and invalid prefixes are flagged separately and never suppress other findings.

## BYO MCP tool classification

**All tools exposed by this server are non-mutative (read-only).** The Lambda
execution role can only be granted `directconnect:Describe*`, `List*`, and
`GetResiliencyGroup` — no mutating Direct Connect action is grantable to this
function. Classify all three tools as **non-mutative** in your Agent Space;
none require the in-chat action-approval flow.

## Prerequisites

1. AWS SAM CLI and an account/region containing your Direct Connect VIFs.
2. Permissions to create a Lambda function, layer, Function URL, IAM role, and log group.
3. An AWS DevOps Agent Agent Space.

## Deployment

**Same-account** (VIFs live in the account running DevOps Agent):

```bash
sam build
sam deploy --guided --stack-name dx-resilience-mcp
```

**Cross-account** (typical enterprise layout: DX in a dedicated network
account, DevOps Agent + this server in an ops account):

1. In the **ops account**, deploy the server stack as above; note the
   `LambdaExecutionRoleArn` output.
2. In the **network account**, deploy `network-account-role.yaml`, passing
   that execution role ARN. Note the `ReadOnlyRoleArn` output.
3. Update the ops-account stack with
   `--parameter-overrides TargetAccountRoleArn=<ReadOnlyRoleArn>`.

The target role is fixed at deploy time via an environment variable — it is
never taken from tool input, so the agent cannot redirect the server at an
arbitrary account. The assumed role is itself read-only.

Note the stack outputs: `McpEndpoint` (Function URL) and `AccessRoleArn`.

## Registering with DevOps Agent

1. DevOps Agent console → your Agent Space → **Capability Providers → Register MCP Server**.
2. **Endpoint**: the `McpEndpoint` Function URL.
3. **Authentication**: AWS SigV4, using the `AccessRoleArn` role (trust policy for `aidevops.amazonaws.com` is created by the template).
4. **Tool allowlist**: expose only the three tools above (do not "allow all").

## Security model

- Read-only IAM at the execution role — the harmlessness guarantee is structural, not behavioral.
- SigV4-authenticated Function URL (`AuthType: AWS_IAM`); no unauthenticated access. Note that with `AWS_IAM`, any IAM principal **in the deploying account** whose identity policy allows `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` on this function can also call it. The template grants this only to the DevOps Agent access role; review account-wide policies (e.g. `lambda:*` on `*`) that would extend it to other principals.
- No credentials handled; no data-plane access; no shell, SQL, or code evaluation. Tool parameters are VIF IDs, a direction label, and prefix lists; prefixes are parsed with Python's `ipaddress` and only re-serialized canonical CIDRs are returned.
- Tool output contains your network configuration: VIF/connection metadata, coverage counts, and the specific prefixes in each finding (gaps, partial coverage, residuals). It is returned only to the calling DevOps Agent in your account and is not stored by this server.
- Bounded cost by construction: reserved concurrency (`ReservedConcurrency`, default 2) caps parallel executions, so a runaway or prompt-injected invocation loop cannot exceed `cap × timeout × memory` in Lambda spend (≈ $1.50/day at defaults, sustained worst case). All Direct Connect APIs called are free and read-only, so there is no per-call AWS charge and nothing a loop can create, modify, or delete.
- Audit: the STS `AssumeRole` calls and the Direct Connect read calls are CloudTrail management events and are recorded by default. Function URL invocations are CloudTrail **data events**, which are off by default; to record who invoked the server, enable Lambda data events for this function on a trail (additional CloudTrail charges apply). Lambda also writes a START/END/REPORT record per invocation to the function's log group.
- Dependencies are pinned to exact versions and file hashes in `layers/dependencies/requirements.txt`, so pip installs in hash-checking mode and refuses any file that does not match. To change a dependency, edit `layers/dependencies/requirements.in` and regenerate the pinned file with `pip-compile --generate-hashes --strip-extras --no-emit-index-url requirements.in`.
- Each analysis is a point-in-time snapshot of live BGP tables.

## Local development

```bash
python3 -m unittest discover tests  # engine tests (stdlib) + topology tests (need boto3; no AWS account — botocore Stubber)
```
