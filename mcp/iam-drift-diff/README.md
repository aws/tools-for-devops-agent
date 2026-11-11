# iam-drift-diff MCP server

A read-only Model Context Protocol (MCP) server for AWS DevOps Agent that
captures, persists, and computes an **exact set-difference** of an account's IAM
state over time. It powers the IAM Access Navigator's drift-detection capability:
"what changed in my IAM posture since last week, and which changes made the
account more permissive."

> **Read-only.** No tool in this server mutates IAM. The only writes are the
> server's own snapshot objects (and a small baseline pointer) to its own
> private, encrypted S3 bucket in the same account. There are no "apply fix" tools and none will be added.

## Why not just call the AWS APIs? (the gap this fills)

`iam:GetAccountAuthorizationDetails` returns the **current** state of every
principal and policy, and AWS DevOps Agent can already call it through `use_aws`.
What the agent cannot do reliably is hold a **prior** state and produce an
**exact, complete set-difference** across an entire account. That is a
computation-and-persistence problem, not a data-access problem.

We have direct evidence this matters. In testing on a test account with roughly
190 roles, the agent was asked to diff current IAM against a baseline it held
in a memory store and compare "in its head":

- **Run 1:** a real change (managed policy `shared-readonly` **detached** from a
  role) was **missed** — the agent re-read inline policies broadly but attached
  policy lists only on a subset of "key" roles.
- **Run 2**, with a stronger prompt that explicitly forbade that narrowing and
  demanded a full-coverage statement: the same change was **missed again**, and
  the run reported "28/28 customer-created roles fully re-read" and "No IAM
  drift since last run" — a confident, specific, and **false** coverage claim.
- A positive control (an inline policy added to a role the agent already knew to
  check) **was** caught. So the failure is specific to exhaustive, exact
  comparison over a long tail of principals — precisely what a language model is
  poor at and a deterministic tool is good at.

This server performs that comparison as literal set/hash math. The model never
does the comparison; it consumes the structured diff and supplies judgment (is a
change risky?) and the recommendation text. The split is deliberate: **code does
set math, the model does judgment.**

## Nebula Appendix A note (disclosed up front)

The Nebula contribution guide describes the MCP lane as *data-plane access the
agent cannot reach natively*, and advises against building an MCP when
`use_aws` / CloudWatch / CloudTrail can already reach the data.
`iam:GetAccountAuthorizationDetails` **is** control-plane and **is** reachable by
`use_aws`. We are not claiming a data-access gap. Our justification is the
**computation + persistence gap** documented above: exact, complete, persisted
set-difference over the whole account, which the agent demonstrably cannot do
reliably on its own. We state this plainly rather than stretch the "data-plane"
answer; the intake "needs data-plane access?" field is answered **No
(control-plane only)**. The closest accepted analogue in the public repo is
`aws-vpc-dns-diagnostics-mcp` (Mode B), a symbolic read-only pre-change
computation over control-plane data that no single describe call produces.

## Tools

| Tool | Purpose |
|---|---|
| `iam_snapshot_capture` | Exhaustively page `GetAccountAuthorizationDetails`, normalize every principal + customer-managed policy into an order-independent fingerprint, persist the snapshot, return `snapshot_id` + a machine-readable `coverage` block. Captures inside the minimum interval return the latest snapshot with `throttled: true`. |
| `iam_snapshot_diff` | Literal set-difference between two snapshots (default: latest vs the snapshot the last recorded report used, with `intervening_snapshots`; `record_baseline: true` records a new report). Returns added / removed / changed principals with per-field detail and a neutral direction hint (up/down/lateral/mixed). |
| `iam_snapshot_list` | List stored snapshots newest-first with their coverage summary. |
| `iam_snapshot_get_entity` | Return one principal's normalized fingerprint from a snapshot, for drill-down. |

### Completeness is machine-readable and load-bearing

Every capture returns `coverage.complete` and every diff returns
`comparison_complete`. These are **false** whenever a page truncated or any call
was denied. The consuming agent is instructed to trust these flags and must not
report "no drift" when the comparison was incomplete — closing exactly the
false-coverage failure mode seen in the prompt-only runs. A skipped read can
never hide behind "everything matches."

### What is intentionally skipped

Policy documents of AWS service-linked / service-role principals (reserved path
prefixes `/aws-service-role/`, `/service-role/`) are recorded by presence only —
they are AWS-controlled, not customer drift surface. This is scoped by role
**type**, never by whether a role changed, so it cannot cause the quiet-role
miss.

## Architecture & security

- Python 3.12, FastMCP, **Streamable HTTP**, served at **`/mcp`**.
- **Auth is SigV4 / AWS_IAM at the Lambda Function URL** — the server performs
  no auth of its own and must never be exposed without that gate. The SAM
  template sets `AuthType: AWS_IAM` and restricts invocation to the DevOps Agent
  service principal from the owning account with `SourceAccount` / `SourceArn`
  confused-deputy conditions. See Security model.
- **Startup safety gate:** the server refuses to start without an explicit,
  non-wildcard `ALLOWED_ACCOUNTS` list, and refuses to operate if the live
  account is not in it.
- **Snapshot storage:** a private S3 bucket with all four Block Public Access
  settings on, SSE-KMS (dedicated CMK, rotation on), versioned, 90-day
  noncurrent expiry, and a bucket policy denying non-TLS access. No
  cross-account access, no export (Nebula Tenets 1 and 6).
- **Execution role:** read-only against IAM (`GetAccountAuthorizationDetails`
  only), object access on its own snapshot bucket only, KMS use on its own CMK
  only. See `iam/deployer-permissions-policy.json`. No `iam:*` write action
  appears anywhere.

## Security model

**Trust boundaries.** There are three: (1) DevOps Agent to the Function URL (SigV4, `AuthType: AWS_IAM`, invoke role trusted only by `aidevops.amazonaws.com` from the owning account); (2) the function to IAM (`iam:GetAccountAuthorizationDetails` only); (3) the function to its own private S3 bucket and KMS key. Tool inputs are only snapshot ids, a principal ARN, and a list limit.

**Tool output is untrusted.** Diff and entity results contain customer-controlled strings (role and policy names, Sids, condition values, policy text). The consuming agent must treat them as data and never follow instructions found in them; the bundled agent prompts say so explicitly. Risk decisions that drive recommendations (`high_risk`, `direction`, counts) are computed by the engine, not by the model.

**Snapshot integrity.**
- Only the server's execution role can write or delete objects in the snapshot bucket (`DenyObjectWritesExceptServerRole`). This blocks account administrators too, by design.
- Snapshot ids must be real UTC capture times (`20261102T120000Z`). Keys that are not, or are dated in the future, are ignored, so a foreign object can never become "latest" or push real snapshots out. Ids passed to tools are validated before they reach S3, and each stored snapshot carries its own id, which is checked on read.
- Versioning (90-day noncurrent retention) allows recovery.

**Baseline and capture throttle.** With no arguments, `iam_snapshot_diff` compares the latest snapshot against the one the last complete report used, and returns `intervening_snapshots` (captures made in between). Only a diff called with `record_baseline: true` (the scheduled drift run) moves that baseline, so ad-hoc diffs have no side effects. A capture or an exploratory diff made right after an IAM change therefore cannot hide that change from the next scheduled run. Captures closer together than `MinCaptureIntervalSeconds` (default 300) return the latest snapshot with `throttled: true` and write nothing. Retention keeps the newest `SnapshotRetain` snapshots (minimum 4) and never prunes the pair the last report used. Residual: a caller with invoke rights can still call `iam_snapshot_diff` with `record_baseline: true` to advance the baseline deliberately; every call, including that flag, is in the audit log.

**Encryption.** SSE-KMS with a dedicated, rotating CMK. The key policy denies data-key use except through S3 in the owning account (`kms:ViaService`, `kms:CallerAccount`). TLS is required by bucket policy and all Block Public Access settings are on.

**Access logging.** The snapshot bucket sends S3 server access logs to a separate access-log bucket (`AccessLogBucketName` output, prefix `snapshot-access/`). That bucket uses SSE-S3 (log delivery cannot use a customer managed key), blocks all public access, requires TLS, is versioned, and expires logs and noncurrent versions after 90 days. Only the S3 logging service may write to it, scoped to this account and the snapshot bucket. Log delivery writes only to the log bucket, so the snapshot bucket's write lockdown is unchanged. Delivery is best-effort and can lag by hours.

**Invocation.** With `RestrictInvokeToFunctionUrl=true` (default), the invoke role's `lambda:InvokeFunction` is limited to calls made through the Function URL (`lambda:InvokedViaFunctionUrl`). Set it to `false` only if registration fails with 403.

**Audit log.** Each tool call writes one JSON line to the function's log: tool name, request id, caller account and ARN (from the Function URL request context), and snapshot ids. No policy content or snapshot principals are logged. For a durable record, enable CloudTrail data events for the function and bucket.

**Teardown.** Because object deletes are denied to everyone but the server, delete the bucket policy first (`aws s3api delete-bucket-policy --bucket <SnapshotBucketName>`), empty the bucket including all versions, then empty the access-log bucket (`AccessLogBucketName`) including all versions, then delete the stack.

**Accepted risks** (from the threat model):
- *Other Agent Spaces in the same account* can assume the invoke role (`aws:SourceArn` is `service/*` in the owning account). The account owner controls which spaces exist; pin `SourceArn` to one space ARN if needed.
- *In-account principals with invoke permission* can call the tools directly. Function URL auth requires an explicit IAM grant, and every call is audited.
- *Principals with `s3:GetObject` and the right IAM rights* can read stored snapshots. The content equals what `iam:GetAccountAuthorizationDetails` already returns live; add a `GetObject` deny to the bucket policy if historical state must be restricted further.
- *Administrators* can remove the bucket policy or change `AuthType`. Administrators are trusted; use an SCP that requires `lambda:FunctionUrlAuthType = AWS_IAM` to guard against misconfiguration.
- *Diff engine defects* could cause a false negative. The engine is deterministic and unit-tested, and incomplete reads are always flagged.
- *Capture flooding and cost* are bounded by the capture throttle. No reserved concurrency is set, because new accounts often lack spare concurrency to reserve.
- *AWS error text* in `coverage.denied_calls` is returned to the already-authorized caller and the function log only.
- *Dependencies* are hash-locked: `layers/dependencies/requirements.txt` pins `fastmcp==4.1.2`, `boto3==1.43.123` and every transitive dependency with SHA-256 hashes, and the layer build uses `pip --require-hashes`. Packages come from PyPI, not an AWS-controlled mirror. The Lambda Web Adapter layer version is pinned.

## DevOps Agent only

This MCP server is designed exclusively for integration with AWS DevOps Agent
via Streamable HTTP + SigV4. It is **not** compatible with local MCP clients
(Kiro, Cursor, VS Code) that use stdio transport.

## Prerequisites

- An AWS account where you will deploy the server (it reads that account's IAM
  and stores snapshots in a private bucket in the same account).
- An AWS DevOps Agent Space. The Space's account is the `SourceAccount` below.
- AWS SAM CLI and Python 3.12 (to build the dependencies layer).
- Permissions to create a Lambda function, an S3 bucket, a KMS key, and IAM
  roles in the deployment account.
- Nothing else: no VPC, database, or Secrets Manager entry is needed because
  the server reads only the IAM control plane (`iam:GetAccountAuthorizationDetails`).

## Registering with DevOps Agent

1. Deploy the stack (see Deploy). Note the outputs `MCPEndpointUrl` and
   `McpInvokeRoleArn`.
2. Register the MCP server with DevOps Agent: in the console, **Capability
   Providers -> Register MCP Server**, or from the CLI with
   `register-service --service mcpserversigv4` (the path used to validate this
   server).
3. Endpoint: the `MCPEndpointUrl` output with `/mcp` appended (the Lambda
   Function URL).
4. Authentication: **AWS SigV4**, service `lambda`, region of the deployment.
   Role: the `McpInvokeRoleArn` output (its trust policy allows only
   `aidevops.amazonaws.com` from the owning account).
5. Associate the server with your Agent Space and **allowlist only the four
   tools below**, not "allow all".

## BYO MCP tool classification

DevOps Agent runs tools classified as read-only autonomously; tools classified
as mutative do not run in the autonomous flow and require explicit in-chat
approval. Classify this server's tools as follows:

| Tool | Classification | Why |
|---|---|---|
| `iam_snapshot_capture` | **Read-only** | Reads IAM only. Its single write is the server's own snapshot object, written to its own private, encrypted bucket in the same account. It never changes IAM. |
| `iam_snapshot_diff` | **Read-only** | Computes over stored snapshots. With `record_baseline: true` it also records which snapshot pair it reported (a small pointer object in the server's own bucket). It never changes IAM. |
| `iam_snapshot_list` | **Read-only** | Lists stored snapshots. |
| `iam_snapshot_get_entity` | **Read-only** | Returns one stored principal fingerprint. |

**No tool in this server is mutative.** There is no custom approval workflow, so
nothing here interacts with the in-chat approval flow. If your organization's
classification policy treats any write, including the snapshot write, as
mutative, classify `iam_snapshot_capture` and `iam_snapshot_diff` accordingly and
approve them in chat; the other two remain read-only.

## Non-production disclaimer

This server is sample code, not intended for production use without additional
review and testing. Validate it in a non-production environment first.

## Layout

```
mcp/
├── template.yaml              # SAM: Lambda (Web Adapter) + Function URL (AWS_IAM) + private S3/KMS
├── src/
│   ├── run.sh                 # Lambda Web Adapter entrypoint (starts the FastMCP server)
│   ├── server.py              # FastMCP app + the 4 tools (the LWA handler)
│   └── iam_drift/             # the deterministic core
│       ├── snapshot.py        # normalize GetAccountAuthorizationDetails -> fingerprints
│       ├── diff.py            # literal set-difference
│       ├── ops.py             # capture throttle + baseline-aware diff
│       └── aws.py             # exhaustive paginated capture + private S3 store
├── layers/dependencies/       # FastMCP + boto3, platform-pinned to x86_64/py3.12
│   ├── requirements.txt
│   └── Makefile
├── iam/deployer-permissions-policy.json
└── tests/                     # 51 tests (pure logic + fake S3, no AWS needed)
```

The Lambda Web Adapter pattern (layer + `run.sh` + `response_stream` Function
URL) mirrors the accepted `aws-vpc-dns-diagnostics-mcp` sample so it matches
what Nebula reviewers expect. The dependencies layer is built with
`--platform manylinux2014_x86_64` so the compiled `pydantic_core` wheel targets
the Lambda runtime, not the (possibly macOS/arm64) build host.

## Deploy

```bash
sam build        # builds the deps layer via its Makefile (platform-pinned wheels)
sam deploy --guided \
  --stack-name iam-drift-diff-mcp \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AllowedAccounts=<your 12-digit account id> \
    SourceAccount=<account id that owns the DevOps Agent space>
```

Then register with the DevOps Agent Agent Space via `mcpserversigv4`, using the
`MCPEndpointUrl` output **with `/mcp` appended**, and allowlist the four tools.

## Usage

Once the server is registered and its tools are assigned, ask DevOps Agent, for example:

> "Run an IAM drift check: capture a snapshot with iam-drift-diff and tell me what changed since the last report, leading with anything that made the account more permissive."

The bundled custom agent's `drift-sentinel-prompt.md` is the standing version of this prompt for a weekly schedule trigger.

To call the deployed server directly (SigV4, same path DevOps Agent uses), with credentials for the deployment account:

```bash
python3 tools/sigv4_client.py <MCPEndpointUrl>/mcp list        # tool names
python3 tools/sigv4_client.py <MCPEndpointUrl>/mcp capture     # new snapshot (or throttled)
python3 tools/sigv4_client.py <MCPEndpointUrl>/mcp snapshots   # history + baseline
python3 tools/sigv4_client.py <MCPEndpointUrl>/mcp diff <before_id> <after_id>
```

## Tests

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

The suite includes the exact regression this server exists to fix
(`test_unused_detach_is_caught`) plus the silent-miss scenarios (admin-attach on
a quiet role, trust-policy change, new empty role) and the false-positive guards
(cosmetic reordering, statement reordering) and completeness honesty.
`tests/test_store.py` covers the hardening: forged and foreign keys ignored,
path-like ids rejected, capture throttle, retention floor, the protected
baseline pair, and an out-of-band capture that must not hide a change.
