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

### Fixed

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
