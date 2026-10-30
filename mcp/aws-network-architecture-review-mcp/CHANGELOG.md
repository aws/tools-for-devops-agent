# Changelog

All notable changes to the AWS Network Architecture Review MCP server are
documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Pinned dependency versions in `layers/dependencies/requirements.txt`
  (`fastmcp==3.4.11`, `boto3==1.43.118`) instead of version ranges, for
  reproducible and reviewable builds.
- Dropped `--upgrade` from the dependencies-layer build (`layers/dependencies/Makefile`)
  so a build no longer pulls newer transitive versions. A fully hash-locked
  requirements file (`pip-compile --generate-hashes`, resolved in a
  python3.12 / manylinux2014_x86_64 environment) with `--require-hashes` is a
  tracked follow-up (threat T-016 / mitigation M-019).
- Added `THIRD-PARTY-LICENSES.md`, listing the Lambda Web Adapter layer and the
  73 Python packages the dependencies layer resolves to, with their licenses
  (BSC22).

### Known limitations (tracked follow-ups)

- **Pagination (T-014 / M-016).** Most list and describe calls read the first
  page only. Truncated results are flagged (see Security) but not completed.
- **Hash-locked dependencies (T-016 / M-019).** Direct dependencies are pinned;
  transitive dependencies are not yet locked with hashes.
- **FastMCP 3.x.** The server pins `fastmcp==3.4.11`, the latest 3.x release
  (2026-10-20). FastMCP's security policy lists both 3.x and 4.x as supported
  ([SECURITY.md](https://github.com/PrefectHQ/fastmcp/blob/main/SECURITY.md));
  moving to 4.x is a follow-up, to be re-tested before release.

### Security

- `get_dx_cloudwatch_metrics` now clamps the caller-supplied `hours` lookback to
  a 1-hour..14-day range, bounding the CloudWatch `GetMetricData` window.
- The method-logging middleware now sanitizes the client-supplied tool name
  (exact ASCII allowlist `[A-Za-z0-9_.-]`, max 64 chars) before writing it to
  logs, preventing log forging via crafted tool names.
- Customer-controlled strings returned to the agent (resource names/tags,
  Cloud WAN descriptions, segment names, VPN tags and tunnel status messages,
  alarm names, DX connection/VIF/gateway names, DX partner name) are passed
  through a sanitizer that strips Unicode control and bidirectional/format
  characters and caps length, and the FastMCP server instructions now tell the
  agent that these strings are customer-controlled data and must not be treated
  as instructions (indirect prompt-injection hardening; threat T-006 / M-007).
- Local mode (`python server.py`, no SigV4 in front of it) now enables FastMCP
  host/origin validation with a loopback allowlist, blocking DNS-rebinding
  access to the developer's credentials. Gated off on the Lambda runtime
  (detected via `AWS_LAMBDA_FUNCTION_NAME`, which only the runtime sets), where
  the Function URL Host header must pass through. The guard settings are shared
  with the test via `local_host_origin_guard()` so they cannot be removed from
  startup without failing a test (threat T-020 / M-025).
- All CloudWatch alarm fields returned to the agent are now sanitized too,
  including `MetricName` and the `ConnectionId` dimension value, which
  `PutMetricAlarm` accepts as arbitrary strings — so every customer-influenced
  field returned by the server passes through the sanitizer (T-006 / M-007).
- Unhandled exceptions are masked: an unhandled tool exception now returns a
  generic error to the client (`mask_error_details=True`) instead of the
  exception text or traceback (BSC15). Handled AWS API errors still return the
  SDK error message to the authorized caller in `error` / `data_errors`;
  residual low risk, accepted (T-009).
- boto3 clients use standard retry mode (3 attempts), so throttling backs off
  instead of amplifying (T-013 / M-015).
- New `ReservedConcurrency` template parameter (default `0` = unset) caps the
  function's concurrent executions, so a looping agent can't use up the
  account's Lambda concurrency and shared API quotas (BSC21 / T-013 / M-015).
  Lambda only allows reserving up to the account's unreserved concurrency minus
  100 ([docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)),
  so it stays opt-in.
- New `AllowedInvokerRoleArn` template parameter (default empty = off). When
  set, an ASGI check serves only sessions of the DevOps Agent invoker role,
  using the caller identity Lambda verified for the Function URL request
  (`x-amzn-request-context` from Lambda Web Adapter). It returns `403` to every
  other caller, including any principal whose IAM policy allows invoke, and
  fails closed on a missing, duplicated or garbled context or a malformed
  setting (BSC9). T-004 is mitigated when `AllowedInvokerRoleArn` is set
  (opt-in, recommended in the README); unset deployments keep the residual
  risk. A Lambda resource policy can't express this, because it only supports
  `Allow`.
- Documented that the `AllowedInvokerRoleArn` check covers the Function URL path
  only. A principal allowed `lambda:InvokeFunction` on the function without the
  `lambda:InvokedViaFunctionUrl=true` condition can invoke it directly with a
  forged event that names the invoker role (confirmed in a test deployment).
  The README now tells deployers to keep that condition on `lambda:InvokeFunction`
  for every principal and not to grant `lambda:Invoke*` on `*`; with it, IAM
  denies the direct invoke (BSC9 / T-004).
- Tool results now carry `"truncated": true` and `truncated_sources` when an
  AWS response says more data exists (`NextToken`, or `AdditionalRoutesAvailable`
  from `SearchTransitGatewayRoutes`) and that data wasn't read. The server's
  instructions tell the agent to report such results as incomplete rather than
  treating missing items as absent (T-014). Tests cover a first-page-only call,
  `AdditionalRoutesAvailable`, and a fully paginated call that is not flagged.
- The PR workflow now runs `pip-audit` (pinned 2.10.1) on
  `layers/dependencies/requirements.txt` and fails on any known vulnerability
  in the resolved dependency set (BSC37).
- Tests now check that a VPN pre-shared key never appears in `get_vpn_details`
  or `network_architecture_summary` output (Test-N03, T-008), and that the
  `hours` lookback is clamped to 1 hour–14 days (Test-N08).
- The README Security Model now has a denial-of-service summary, and no longer
  says the read actions don't support resource-level permissions (BSC21, BSC28).
- The `mcp method=` and `mcp rejected` log lines now include the caller ARN
  from the request context (`caller=…`, `-` when there is none). It is limited
  to IAM ARN characters and 256 characters, so a crafted role-session name
  can't forge log lines. CloudWatch now shows who called which tool (BSC40 /
  T-011). Tests cover the served, rejected and injection cases. Lambda verifies
  that ARN only on the Function URL path; on a direct `lambda:InvokeFunction`
  call it is the identity the caller claimed, and only CloudTrail data events
  for the function record the real principal.
- AWS API errors (botocore `ClientError`) a tool doesn't handle itself now
  return `{"error": "<Code>: <Message>"}` (control characters stripped, capped
  at 512 characters) instead of a generic masked error, so the agent can report
  an unknown resource ID or a missing permission. All other exceptions stay
  masked (T-009).
- The execution-role comment in `template.yaml` no longer says none of the
  actions support resource-level permissions. It now says the resource is `*`
  because the resources aren't known at deploy time (BSC28).
- A test now checks that the README's invoker-role trust policy keeps the
  confused-deputy conditions: `aidevops.amazonaws.com` principal,
  `aws:SourceAccount`, and `aws:SourceArn` scoped to `service/*` (BSC6 /
  T-002, T-003).
- CI now installs `pyyaml==6.0.3`, and the template tests import it directly
  instead of skipping when it's missing, so the Function URL auth and
  reserved-concurrency guards (Test-N01) always run.
- FastMCP's startup update check, which fetched
  `https://pypi.org/pypi/fastmcp/json` (seen in Lambda logs as an "Update
  available" banner), and the banner are now off: `FASTMCP_CHECK_FOR_UPDATES=off`
  and `FASTMCP_SHOW_SERVER_BANNER=false` in `template.yaml`, with the same
  defaults set in `server.py` before FastMCP is imported. The server's only
  outbound calls are now AWS APIs (BSC22). A test asserts both settings and that
  the update check makes no network call.

### Added

- Tests: the Function URL stays `AWS_IAM` and nothing in the template grants
  public invoke (Test-N01); `ReservedConcurrency` is wired to the function;
  unhandled errors are masked.
- CI: `.github/workflows/test-network-architecture-review-mcp.yml` runs these
  tests on every pull request (M-021). It blocks merges once an admin makes it a
  required status check.
- README: a trust-policy check (`get-role` + `accessanalyzer validate-policy`)
  confirming both confused-deputy conditions are present (M-004); an
  encryption-in-transit / at-rest note; a note that IAM invoke permission is the
  only access check (T-004).

### Fixed

- README no longer says customer-controlled values are returned "unchanged"; it
  now describes the sanitization.
- README IAM guidance: removed `lambda:InvokeFunctionWithResponseStream`, which
  is not a real IAM action — streaming invokes are authorized by
  `lambda:InvokeFunction`. The required actions are `lambda:InvokeFunctionUrl`
  and `lambda:InvokeFunction`. (`simulate-principal-policy` echoes any action
  string, so it had not flagged the non-existent action.)
- README: clarified the single-account scope note — in a hub/network account the
  tools also return configuration of spoke accounts attached to shared TGW /
  Cloud WAN / DX gateways, because the deploying account can read it as owner.
- Added tests: `_clean_label` sanitization behaviour and output coverage;
  local-mode rejection of a foreign `Host` header.

## [1.0.0] — 2026-10-05

Initial release, adapted for AWS DevOps Agent from the stdio sample
[aws-samples/sample-aws-network-architecture-review-mcp-server](https://github.com/aws-samples/sample-aws-network-architecture-review-mcp-server).
Tool logic and resiliency scoring are unchanged from the sample, apart from the
fixes listed below, which were also applied to the sample.

### Added

- 13 read-only tools covering Direct Connect, Transit Gateway, Site-to-Site VPN,
  virtual private gateways, Cloud WAN, VPC endpoints, and DX CloudWatch metrics
  and alarms, plus `network_architecture_summary` combining all layers.
- DX resiliency scoring (`check_dx_resiliency`) and architecture-wide resiliency
  scoring in the summary.
- Streamable HTTP transport through the Lambda Web Adapter and a Lambda Function
  URL with `AWS_IAM` (SigV4) auth, running stateless.
- SAM template with an execution role limited to the 21 read actions the tools
  call, and a platform-pinned dependency layer build.
- Tool descriptions and server instructions that tell the agent when to prefer
  these tools over individual AWS API calls.
- Method-name logging (`mcp method=…`, plus the tool name for `tools/call`) to
  CloudWatch. Arguments and results are not logged.
- `test-infra/network-lab.yaml`, an optional test network.
- Offline tests for the tools, the IAM policy, and the Lambda transport.

### Fixed

Found while testing with DevOps Agent:

- Registration failed with `403 Forbidden`: function URLs created since October
  2025 also require `lambda:InvokeFunction`. The documented signing-role policy
  now includes it.
- Sessions failed across Lambda execution environments (`404`): the server now
  runs stateless and returns an `Mcp-Session-Id` header.
- Empty response bodies (such as `202 Accepted`) never terminated under Lambda
  response streaming, which made the agent report the tools as unavailable.
  Empty bodies now carry a single newline.
- `get_tgw_route_table_details` reported "no route tables" for a Transit Gateway
  shared through AWS RAM. It now names the shared Transit Gateway and its owner.

Also applied to the stdio sample:

- `network_architecture_summary` no longer hides data-source failures. Each is
  listed in `data_errors`, so a denied `DescribeAlarms` call is not reported as
  every recommended alarm being missing.
- BGP `health_pct` is `null` when there are no BGP peers, rather than `0`.
- Several fields were read with the wrong letter case and were always null: VPN
  state, tunnel status, accepted routes, and static routes; virtual private
  gateway state and attached VPC; Cloud WAN states; and the Amazon-side ASN of
  Direct Connect virtual interfaces.
