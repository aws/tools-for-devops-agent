# AWS Network Architecture Review MCP

> **⚠️ Proof of Concept (POC):** This project is sample code and is not intended
> for production use without additional review and testing. Validate it in a
> non-production account before using it with production workloads.

> ⚠️ This MCP server is designed exclusively for integration with AWS DevOps
> Agent via Streamable HTTP + SigV4. It is NOT compatible with local MCP clients
> (Kiro, Cursor, VS Code) that use stdio transport.

MCP server for AWS DevOps Agent that performs a read-only review of an account's hybrid network architecture: **Direct Connect resiliency scoring**, Transit Gateway topology and route tables, Site-to-Site VPN tunnel health, Cloud WAN discovery, VPC endpoints, and DX CloudWatch metrics and alarm coverage, combined into a single architecture summary with severity-classified findings.

The DevOps Agent's built-in AWS access can call these APIs one at a time. This
server correlates them across layers and applies a deterministic scoring
method, so the agent can answer questions such as "is our Direct Connect
resilient?", "which DX connections have no alarms?", or "what is our backup path
if Direct Connect fails?" consistently.

---

## Tools

All 13 tools take a `region` argument and inspect the account the server is
deployed in.

| Tool | Description |
| --- | --- |
| `network_architecture_summary` | Complete architecture discovery combining all layers, DX CloudWatch alarm coverage, and architecture-wide resiliency scoring. Start here. |
| `analyze_dx_topology` | Full DX topology: connections, VIFs, gateways, BGP status, resiliency |
| `check_dx_resiliency` | DX resiliency assessment: location diversity, redundancy, BGP, MTU, MACsec |
| `get_bgp_status` | BGP peer status for all virtual interfaces |
| `get_dx_vif_details` | Detailed VIF config, BGP peers, route filter prefixes |
| `get_dx_gateway_details` | DX Gateway associations, allowed prefixes, VGW/TGW mappings |
| `get_dx_cloudwatch_metrics` | DX utilization, errors, light levels, connection state |
| `get_vpn_details` | VPN connections, tunnel status, BGP, accepted routes |
| `analyze_tgw_topology` | TGW details, attachments, route tables |
| `get_tgw_route_table_details` | Associations, propagations, and routes per TGW route table |
| `get_virtual_gateway_details` | VGW details and VPC attachments |
| `analyze_cloudwan_topology` | Cloud WAN global/core networks, attachments, peerings |
| `get_vpc_endpoints` | VPC endpoints summary with pattern detection |

### Scoring

`check_dx_resiliency` scores Direct Connect from 100 downward:

| Check | Severity | Score impact |
| --- | --- | --- |
| Location diversity (single location) | CRITICAL | −40 |
| Connection redundancy (fewer than 2 connections at a location) | HIGH | −15 per location |
| BGP health (peers down) | HIGH | −10 per peer |
| MTU consistency (mixed values) | MEDIUM | −5 |
| MACsec (capable but not enabled) | MEDIUM | −5 |

The resiliency level is derived from topology alone: **HIGH (Maximum
Resiliency)** with 2+ locations and 2+ connections at each, **MEDIUM (High
Resiliency)** with 2+ locations, otherwise **LOW (Single Location)**.

`network_architecture_summary` adds an architecture-wide score across the
layers present: DX (40 points), TGW (25), VPN backup (15), and Cloud WAN (20),
expressed as a percentage of the maximum possible for the deployed components.

### Unavailable data

If a data source cannot be read (for example, a missing permission), the
summary records it in `data_errors` and the affected section carries an `error`
field. For CloudWatch alarms, `missing_recommended` is `null` in that case
rather than reporting every recommended alarm as missing. The server's
instructions tell the agent to report these as unavailable, not as findings.

Most tools read only the first page of each AWS list or describe call. When AWS
says more data exists (a `NextToken`, or `AdditionalRoutesAvailable` from
`SearchTransitGatewayRoutes`), the result carries `"truncated": true` and
`truncated_sources` naming the calls that were cut off, and the server's
instructions tell the agent to report the result as incomplete. In a large
estate, a truncated result may be missing gateways, attachments, or routes.
Full pagination is a tracked follow-up (see CHANGELOG).

---

## Prerequisites

1. **AWS SAM CLI** — `brew install aws-sam-cli` or `pip install aws-sam-cli`
2. **Python 3.12** (used by `sam build` for the dependency layer)
3. **AWS credentials** for the account to review, able to deploy CloudFormation,
   Lambda, and IAM resources

The server reviews the account and Regions it can reach with its own execution
role. Deploy it in the account that owns your network resources (for a
multi-account landing zone, typically the network or connectivity account).

---

## Deployment

### Step 1 — Deploy the MCP Lambda

```bash
sam build
sam deploy --guided --capabilities CAPABILITY_IAM
```

Or non-interactively:

```bash
sam build
sam deploy \
  --stack-name aws-network-architecture-review-mcp-prod \
  --parameter-overrides StageName=prod \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --region <region>
```

| Parameter | Default | Description |
| --- | --- | --- |
| `StageName` | `prod` | `dev`, `staging`, or `prod`. Used in the function and layer names. |
| `ReservedConcurrency` | `0` (unset) | Caps concurrent executions of the function. Set a value such as `10` so a looping agent can't use up the account's Lambda concurrency and shared EC2 / Direct Connect API quotas. `0` means unset, not throttled. Lambda only lets you reserve up to the account's unreserved concurrency minus 100 ([Configuring reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)), so an account with a low concurrency quota can't set it. |
| `AllowedInvokerRoleArn` | `''` (off) | **Recommended.** ARN of the role DevOps Agent assumes (created in step 2). When set, the server serves only sessions of that role and returns `403` to every other caller that comes through the Function URL, even ones IAM lets invoke it. It does not cover direct `lambda:InvokeFunction` calls; see [Scope `lambda:InvokeFunction`](#scope-lambdainvokefunction-for-every-principal). Set it once the role exists (end of step 2). |

`sam build` installs the dependency layer for `manylinux2014_x86_64` /
Python 3.12 regardless of the build host (see `layers/dependencies/Makefile`),
so building on macOS produces a layer the Lambda runtime can import.

Note the `MCPEndpointUrl` output. You need it in step 2.

### Step 2 — Register with DevOps Agent

Register the MCP endpoint using **AWS SigV4** auth. The endpoint is the
`MCPEndpointUrl` output with `/mcp` appended, because FastMCP serves the
Streamable HTTP transport at `/mcp`. Use `/mcp` exactly: `/mcp/` redirects,
which invalidates the request signature.

| Setting | Value |
| --- | --- |
| Service type | `mcpserversigv4` |
| Endpoint | `MCPEndpointUrl` output, with `/mcp` appended |
| Region | The Region the function is deployed in |
| Service name | `lambda` |
| IAM role | A role trusting `aidevops.amazonaws.com` with `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` on the function |

> **Use a server name of 35 characters or fewer** (for example
> `aws-network-architecture-review`). DevOps Agent names each tool
> `<server-name>_<tool-name>` and limits that to 64 characters; the longest tool
> name here, `network_architecture_summary`, is 28 characters. A longer server
> name registers but fails when you add it to an Agent Space.

Create the IAM role (below) before registering.

#### Option A — DevOps Agent console

1. Open the DevOps Agent console and go to **Capability Providers**.
2. Choose **Register MCP Server**.
3. **MCP server details**: enter a name, and the `MCPEndpointUrl` output with
   `/mcp` appended as the **Endpoint URL**.
4. **Authorization flow**: select **AWS SigV4**.
5. **Authorization configuration**:
   - **Configure IAM role**: select or create a role that trusts
     `aidevops.amazonaws.com` (trust policy below).
   - **AWS Region**: the Region the function is deployed in.
   - **Service Name**: `lambda`.
6. **Review and submit.** DevOps Agent validates the connection by calling the
   MCP `initialize` and `tools/list` methods against your endpoint.

#### Option B — AWS CLI

The console flow (Option A) is the tested path. This CLI equivalent follows the
same settings.

```bash
aws devops-agent register-service \
  --service mcpserversigv4 \
  --service-details '{
    "mcpserversigv4": {
      "name": "aws-network-architecture-review",
      "endpoint": "<MCPEndpointUrl>/mcp",
      "authorizationConfig": {
        "region": "<region>",
        "service": "lambda",
        "mcpRoleArn": "<role-arn>"
      }
    }
  }'
```

Then associate the returned `serviceId` with your Agent Space.

#### IAM role for SigV4 signing

DevOps Agent assumes this role in your account to sign requests to the
endpoint. The trust policy needs confused-deputy conditions:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "aidevops.amazonaws.com" },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": { "aws:SourceAccount": "ACCOUNT_ID" },
      "ArnLike": { "aws:SourceArn": "arn:aws:aidevops:REGION:ACCOUNT_ID:service/*" }
    }
  }]
}
```

Attach only the permissions needed to invoke the endpoint:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunctionUrl",
    "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:aws-network-architecture-review-mcp-STAGE",
    "Condition": { "StringEquals": { "lambda:FunctionUrlAuthType": "AWS_IAM" } }
  },
  {
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:aws-network-architecture-review-mcp-STAGE",
    "Condition": { "Bool": { "lambda:InvokedViaFunctionUrl": "true" } }
  }]
}
```

Both actions are required:

- `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` — function URLs created
  since October 2025 require both ([Control access to Lambda function
  URLs](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)). The
  `lambda:InvokedViaFunctionUrl` condition limits `InvokeFunction` to calls made
  through the function URL. The Function URL uses `InvokeMode: RESPONSE_STREAM`,
  but the streaming invoke path is authorized by `lambda:InvokeFunction` as
  well — there is no separate `InvokeFunctionWithResponseStream` IAM action.

A missing action surfaces at registration as `403 Forbidden` from the Function
URL, with no invocation recorded in the function's CloudWatch log group.

Save the two policies above as `trust-policy.json` and `invoke-policy.json`
(replacing `ACCOUNT_ID`, `REGION`, and `STAGE`), then create the role:

```bash
aws iam create-role \
  --role-name DevOpsAgentNetArchReviewMCP-STAGE \
  --assume-role-policy-document file://trust-policy.json
aws iam put-role-policy \
  --role-name DevOpsAgentNetArchReviewMCP-STAGE \
  --policy-name InvokeNetworkArchReviewMCP \
  --policy-document file://invoke-policy.json
```

Verify both actions before registering:

```bash
for action in lambda:InvokeFunctionUrl lambda:InvokeFunction; do
  aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/DevOpsAgentNetArchReviewMCP-STAGE \
    --action-names "$action" \
    --resource-arns arn:aws:lambda:REGION:ACCOUNT_ID:function:aws-network-architecture-review-mcp-STAGE \
    --context-entries "ContextKeyName=lambda:FunctionUrlAuthType,ContextKeyValues=AWS_IAM,ContextKeyType=string" \
                      "ContextKeyName=lambda:InvokedViaFunctionUrl,ContextKeyValues=true,ContextKeyType=boolean" \
    --query 'EvaluationResults[0].[EvalActionName,EvalDecision]' --output text
done
```

Both must report `allowed`. Note `simulate-principal-policy` echoes back any
action string you pass, including ones that are not real IAM actions, so it only
confirms the policy grants the names you list — not that those names exist.

Then confirm the trust policy still carries both confused-deputy conditions.
Without them, another account's DevOps Agent could assume this role:

```bash
aws iam get-role \
  --role-name DevOpsAgentNetArchReviewMCP-STAGE \
  --query 'Role.AssumeRolePolicyDocument.Statement[].Condition'
aws accessanalyzer validate-policy \
  --policy-type RESOURCE_POLICY \
  --validate-policy-resource-type AWS::IAM::AssumeRolePolicyDocument \
  --policy-document file://trust-policy.json \
  --query 'findings[].[findingType,issueCode]' --output text
```

The first command must show both `aws:SourceAccount` and `aws:SourceArn`. The
second should print nothing (no findings).

#### Recommended: restrict the server to the DevOps Agent role

Do this step for every deployment. Without it, any principal in the account
whose IAM policy allows `lambda:InvokeFunctionUrl` on the function (or on `*`)
can call every tool and read the network configuration the execution role can
read. Now that the role exists, redeploy with its ARN:

```bash
sam deploy \
  --stack-name aws-network-architecture-review-mcp-prod \
  --parameter-overrides StageName=prod \
    AllowedInvokerRoleArn=arn:aws:iam::ACCOUNT_ID:role/DevOpsAgentNetArchReviewMCP-STAGE \
  --capabilities CAPABILITY_IAM --resolve-s3 --region <region>
```

The server then returns `403` to any caller that isn't a session of that role.
It reads the caller from the identity Lambda verified for the Function URL
request, so a caller that comes through the Function URL can't claim to be
someone else. A direct invoke is different; see the next section. The setting
is opt-in only because the role is created after the stack; a deployment that
leaves it unset keeps the risk described above.

With the setting on, expect one `mcp rejected caller=- not in
ALLOWED_INVOKER_ROLE_ARN` line, followed by `"GET /mcp HTTP/1.1" 403`, in the
function's log at every cold start. That's the Lambda Web Adapter's readiness
probe: it calls `/mcp` from inside the execution environment with no caller
identity, so the check rejects it. The adapter treats any status below 500 as
ready, so this is expected and harmless.

#### Scope `lambda:InvokeFunction` for every principal

`AllowedInvokerRoleArn` checks the caller of requests that come through the
Function URL. It can't check a direct `lambda:InvokeFunction` call: whoever
invokes the function directly writes the event, including the caller identity
in it, so they can claim to be the DevOps Agent role. Any principal whose policy
allows `lambda:InvokeFunction` on this function without the
`lambda:InvokedViaFunctionUrl` condition can therefore get around the check.

- Keep the `"Bool": { "lambda:InvokedViaFunctionUrl": "true" }` condition on
  `lambda:InvokeFunction` for the DevOps Agent role, as in the policy above.
- Don't grant `lambda:InvokeFunction` or `lambda:Invoke*` on `*`, or on this
  function, to any other principal in the account unless it carries the same
  condition. Review existing broad grants (for example `AWSLambda_FullAccess`
  or `*:*` administrator policies) before you rely on the check.
- With the condition in place, IAM denies a direct invoke with
  `AccessDeniedException` before the function runs.

### Step 3 — Configure tools in your Agent Space

1. In the DevOps Agent console, select your Agent Space.
2. Go to the **Capabilities** tab.
3. Select the registered MCP server.
4. Choose **Select specific tools**, not *Allow all tools*.
5. Allowlist the tools that Agent Space needs, then choose **Add**.

| Use case | Allowlist |
| --- | --- |
| Architecture reviews | `network_architecture_summary`, `check_dx_resiliency`, `analyze_tgw_topology`, `get_vpn_details` |
| Direct Connect troubleshooting | `analyze_dx_topology`, `get_bgp_status`, `get_dx_vif_details`, `get_dx_gateway_details`, `get_dx_cloudwatch_metrics` |
| Full review | all 13 tools |

---

## Tool classification

All 13 tools are **read-only**. None is mutative: every AWS call is a
`Describe*`, `List*`, `Get*`, or `Search*` operation, and the execution role
grants no write permission. Classify every tool as **read-only** in DevOps
Agent. No tool requires in-chat action approval, and the server has no approval
workflow of its own.

---

## Running on Lambda

The server runs FastMCP's Streamable HTTP transport behind the Lambda Web
Adapter in `response_stream` mode. Three behaviours make it work reliably with
DevOps Agent; `tests/test_transport.py` covers each.

- **Stateless.** Lambda can route consecutive requests from one client to
  different execution environments, so the server keeps no MCP session state
  (`stateless_http=True`). Any environment can answer any request.
- **`Mcp-Session-Id` header.** A stateless server sends no session ID, but some
  clients only continue past `initialize` when one is present. A small ASGI
  middleware returns the client's session ID, or a random one. The value is
  never used to store state.
- **No empty response bodies.** Under response streaming, a response with an
  empty body (such as `202 Accepted` for a notification) never terminates, which
  leaves the client waiting and ties up the execution environment. The
  middleware gives empty bodies a single newline. `DELETE` returns `200`; `GET`
  returns `405`, meaning no server-to-client stream is offered.

Memory is 1024 MB to shorten cold starts, since DevOps Agent opens several
sessions in parallel. Each request logs its MCP method name, the tool name for
`tools/call`, and the caller ARN from the request context (`caller=`, or `-`
when there is none) to CloudWatch. A request the `AllowedInvokerRoleArn` check
rejects is logged with its caller ARN too. Arguments and results are never
logged. Lambda verifies that ARN only for requests through the Function URL; on
a direct `lambda:InvokeFunction` call it is whatever identity the caller put in
the event (see [Scope `lambda:InvokeFunction`](#scope-lambdainvokefunction-for-every-principal)).
To record the real calling principal for every invoke, enable CloudTrail data
events for the function (`AWS::Lambda::Function`).

## Security Model

- **Read-only by construction.** The execution role in `template.yaml` lists
  exactly the 21 read actions the tools call. Some of them support
  resource-level permissions, but the tools read whatever gateways, route tables
  and connections exist in the account, which aren't known when you deploy, so
  the resource is `*`; the boundary is the read-only action list.
- **No credentials or secrets.** The server uses its Lambda execution role. It
  stores no data, writes nothing, and makes no calls outside AWS APIs. FastMCP's
  startup update check (a request to `pypi.org`) and banner are turned off, in
  `template.yaml` and in `server.py` for local runs.
- **Single-account scope.** The server uses only its own execution role and does
  not assume roles into other accounts. It returns the resources that account can
  read as owner — so in a hub/network account that owns shared Transit Gateways,
  Cloud WAN, or DX gateways, the output includes configuration of the spoke
  accounts attached to them. Deploy it in an account whose operators are allowed
  to see that data.
- **Authenticated endpoint.** The Function URL uses `AWS_IAM` auth, so every
  request must be SigV4-signed by a principal allowed to invoke the function.
  Unsigned requests are rejected with `403`. IAM alone admits any principal in
  the account whose policy allows `lambda:InvokeFunctionUrl` on this function
  (or on `*`), and a Lambda resource policy can't deny them, because it only
  supports `Allow`. Setting `AllowedInvokerRoleArn` (recommended; see step 2)
  makes the server itself return `403` to every Function URL caller except the
  DevOps Agent role. A deployment that leaves it unset keeps this residual risk.
  The check doesn't cover direct `lambda:InvokeFunction` calls, so it only holds
  if no other principal is allowed `lambda:InvokeFunction` on this function
  without the `lambda:InvokedViaFunctionUrl` condition (see step 2).
- **Encrypted in transit; nothing stored at rest.** The Function URL accepts
  HTTPS only, and the server calls AWS APIs over TLS. The only plain-HTTP hop is
  the Lambda Web Adapter talking to the server on `127.0.0.1` inside the Lambda
  execution environment. The server stores no data; the only thing written is
  one CloudWatch Logs line per request (method, tool name and caller ARN),
  which CloudWatch encrypts at rest.
- **Denial of service.**
  - Only SigV4-signed callers that IAM allows can invoke the function, and unsigned requests are rejected before it runs.
  - Tools make read-only calls, and most read only the first page, which caps the work per request. The `hours` lookback is clamped to 1 hour–14 days.
  - boto3 uses standard retry mode, so throttling backs off instead of retrying harder.
  - The function times out at 120 seconds.
  - When the first page isn't the whole result, the tool flags it `truncated` rather than reading more pages.
  - Set `ReservedConcurrency` (step 1) to cap concurrent executions, so a looping agent can't use up the account's Lambda concurrency or shared EC2 and Direct Connect API quotas.
  - No load test has been run; size `ReservedConcurrency` to the account's quotas.
- **Structured parameters only.** Tools accept a Region and, where relevant, a
  resource ID or lookback window. No tool accepts arbitrary API names or
  queries.
- **Returned data is untrusted.** Tool output includes values set by whoever
  manages the account, such as resource names, tags, and descriptions. The
  server strips control and bidirectional characters from them and caps their
  length, but otherwise returns their content; the agent should treat them as
  data, never as instructions.
- **Unhandled exceptions are masked.** An unhandled exception returns a generic
  error to the caller (`mask_error_details`), with no exception text or
  traceback. AWS API errors (for example an unknown resource ID or a missing
  permission) return their error code and SDK message in an `error` or
  `data_errors` field to the caller, who is already SigV4-authorized in the same
  account. The message can name ARNs or the account ID; that residual risk is
  low and accepted.
- **Local runs bind loopback.** Running `server.py` directly listens on
  `127.0.0.1`, because that path has no SigV4 boundary in front of it.

---

## Usage Examples

Ask DevOps Agent in chat:

- "Review the network architecture in us-east-1 and summarize the resiliency
  risks."
- "Is our Direct Connect setup resilient to a location failure?"
- "Which Direct Connect connections are missing recommended CloudWatch alarms?"
- "Are any BGP sessions down on our Direct Connect virtual interfaces?"
- "Do we have a VPN backup path if Direct Connect fails?"

---

## Structure

```
aws-network-architecture-review-mcp/
├── src/
│   ├── server.py          # FastMCP server and the 13 tools
│   └── run.sh             # Lambda Web Adapter entry point
├── layers/dependencies/
│   ├── requirements.txt   # fastmcp, boto3
│   └── Makefile           # platform-pinned layer build
├── tests/
│   ├── test_server.py     # tools, read-only IAM, data handling
│   └── test_transport.py  # Lambda transport behaviours
├── test-infra/
│   └── network-lab.yaml   # optional test network (see Test infrastructure)
├── template.yaml          # SAM: Lambda + Function URL (AWS_IAM) + layer
├── README.md
├── CHANGELOG.md
└── THIRD-PARTY-LICENSES.md # licenses of the layer and its dependencies
```

## Test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r layers/dependencies/requirements.txt pytest
pytest tests/
```

The tests run offline: tool tests use mocked AWS clients, and transport tests
start the server on a loopback port (`uvicorn` and `httpx` are installed with
`fastmcp`).

## Local Testing

```bash
cd src
python server.py   # Streamable HTTP on http://127.0.0.1:8080/mcp
```

The local server uses your default AWS credentials. Connect any MCP client that
supports Streamable HTTP to `http://127.0.0.1:8080/mcp`.

## Test infrastructure

`test-infra/network-lab.yaml` creates a small network the tools can inspect: two
VPCs, a Transit Gateway with two segmented route tables and a blackhole route, a
BGP VPN to the Transit Gateway, a static VPN to a virtual private gateway, and
VPC endpoints. The VPN tunnels stay down by design (the customer gateway uses a
documentation IP address), which exercises the tunnel-down findings.

It costs about USD 0.26 per hour while it runs. Deploy it in a non-production
account and delete it when you finish.

```bash
aws cloudformation deploy \
  --stack-name narmcp-network-lab \
  --template-file test-infra/network-lab.yaml
```

CloudFormation has no Direct Connect gateway resource. To include one (free),
create it and associate it with the lab Transit Gateway:

```bash
TGW=$(aws cloudformation describe-stacks --stack-name narmcp-network-lab \
  --query "Stacks[0].Outputs[?OutputKey=='TransitGatewayId'].OutputValue" --output text)
DXGW=$(aws directconnect create-direct-connect-gateway \
  --direct-connect-gateway-name narmcp-lab-dxgw --amazon-side-asn 64800 \
  --query directConnectGateway.directConnectGatewayId --output text)
aws directconnect create-direct-connect-gateway-association \
  --direct-connect-gateway-id "$DXGW" --gateway-id "$TGW" \
  --add-allowed-prefixes-to-direct-connect-gateway cidr=10.10.0.0/16 cidr=10.20.0.0/16
```

Example questions for DevOps Agent against this network: "Review the network
architecture in us-east-1 and summarize the resiliency risks", or start an
investigation such as "VPN backup connectivity down in us-east-1".

To delete it, remove the Direct Connect gateway association and gateway first,
then the stack:

```bash
aws directconnect delete-direct-connect-gateway-association \
  --association-id <association-id>
aws directconnect delete-direct-connect-gateway --direct-connect-gateway-id "$DXGW"
aws cloudformation delete-stack --stack-name narmcp-network-lab
```

## Cleanup

```bash
sam delete
aws iam delete-role-policy --role-name DevOpsAgentNetArchReviewMCP-STAGE \
  --policy-name InvokeNetworkArchReviewMCP
aws iam delete-role --role-name DevOpsAgentNetArchReviewMCP-STAGE
```

Also deregister the MCP server from DevOps Agent Capability Providers.

## License

This library is licensed under the Apache-2.0 License. See the
[LICENSE](../../LICENSE) file. Third-party components in the deployed function
and their licenses are listed in [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).
