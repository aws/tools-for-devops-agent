# Changelog

All notable changes to the AWS Network Architecture Review MCP server are
documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
