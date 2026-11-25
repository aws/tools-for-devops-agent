# Changelog

## [0.1.0] - 2026-09-24
### Added
- Initial release.
- `analyze_vif_resilience`: two-direction (accepted/advertised) deterministic
  CIDR coverage analysis over `ListVirtualInterfaceRoutes`, with gap /
  partial-supernet-residual / partial / covered classification, pairwise
  failover impact, BGP health pre-check, and device-diversity check.
- `get_dx_topology`: joined connections / VIFs / gateways / resiliency-groups view.
- `compare_prefix_sets`: pure coverage math tool.
- SAM template: Lambda + Function URL (SigV4), read-only IAM, DevOps Agent access role.

## [0.1.1] - 2026-09-25
### Fixed
- Serve MCP in stateless HTTP mode (`http_app(stateless_http=True)`) — required
  on Lambda, where invocations do not share memory and a session from
  `initialize` is lost on the next call ("Session terminated"). Pin fastmcp>=2.11.

## [0.2.0] - 2026-09-25
### Added
- Report physical diversity at TWO independent levels: AWS device AND DX
  location (both read from the VIF, so they work for hosted/cross-account VIFs).
  A device-diverse-but-same-location set is now flagged for site-failure risk.
- get_dx_topology reports connection_visibility: when a hosted/cross-account
  VIF's parent connection is not owned by the analyzed account, resiliency-group
  and LAG checks are marked INDETERMINATE rather than absent.

## [0.2.1] - 2026-09-25
### Fixed
- Supernet fully tiled by a peer's more-specifics is now classified COVERED
  (residual set-difference resolves to empty) instead of a false partial_supernet.
  Found by the aggregate-tiling test scenario (S4).

## [0.3.0] - 2026-10-08
### Added
- `ReservedConcurrency` template parameter (default 2) applied as Lambda
  reserved concurrency — a structural bound on cost/DoS abuse: an invocation
  loop (rogue prompt, leaked signing context) can never exceed
  cap x timeout x memory in spend. Raised during AppSec (Talos) review.

## [0.3.1] - 2026-10-12
### Changed
- Pin every dependency-layer package (direct and transitive) to the exact
  versions of the build validated in the live DX lab suite and the DevOps
  Agent functional evals. `sam build` now reproduces that build exactly.
  No code or behavior change.
### Documentation
- README security model: same-account callers under `AWS_IAM`, what tool
  output contains, and how to enable CloudTrail data events for Function URL
  invocations (off by default).

## [0.3.2] - 2026-10-21
### Changed
- Pin every dependency-layer package to a file hash as well as an exact
  version. `layers/dependencies/requirements.in` lists the three direct
  dependencies. `requirements.txt` is generated from it with
  `pip-compile --generate-hashes`, so pip installs in hash-checking mode and
  rejects any file that does not match. The installed package set is unchanged
  (the same 84 packages at the same versions). No code or behavior change.

## [0.3.3] - 2026-10-21
### Security
- Update the pinned `certifi` from 2026.7.22 to 2026.10.19
  (GHSA-6q48-6c7w-9gw2). The older CA bundle trusts the
  `emSign ECC Root CA - G3` root, whose revoked intermediates had
  compromised keys. botocore uses this bundle to verify TLS to AWS
  endpoints. The other 83 packages and the function code are unchanged.

## [0.3.4] - 2026-11-03
### Fixed
- Resiliency-group lookup in `get_dx_topology` (SME review finding):
  `ListResiliencyGroups` and `ListResiliencyGroupAssociations` return their
  results under `items` (with `nextToken` pagination), and associations
  reference connections by `connectionArn` — the previous code read
  `resiliencyGroups`/`associations`/`connectionId`, so every connection
  silently reported no group membership. Both calls now paginate `items` and
  the connection ID is extracted from the association ARN.
- A failing resiliency-group listing is now reported per region in the tool
  output (`resiliency_group_errors`) instead of being silently swallowed, so
  "API unavailable" is distinguishable from "no groups".
### Added
- `tests/test_topology.py`: botocore-Stubber tests for `get_dx_topology` —
  non-hosted-VIF connection↔group join, `items`/`nextToken` pagination,
  `connectionArn` extraction, hosted-VIF indeterminate visibility, and the
  error-surfacing path. Response shapes are validated against the real
  botocore service model; no AWS account needed.
