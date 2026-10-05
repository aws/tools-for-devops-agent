# Changelog

All notable changes to the SaaS Status MCP server are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-08-31

Initial release.

### Added

- **Four provider-agnostic MCP tools** for correlating AWS DevOps Agent
  investigations with upstream SaaS health:
  - `list_providers` — returns every provider in the registry (local read, no
    external call).
  - `get_service_status` — current overall Statuspage.io indicator for one
    provider, normalized so `none` maps to `operational`.
  - `get_active_events` — the core investigation tool; merges unresolved
    incidents and active scheduled maintenances into a single normalized event
    list, with optional `include_history` for full update trails.
  - `check_all_dependencies` — bulk status + active-event count across up to 10
    providers, fanned out in parallel with `asyncio.gather`.
- **Generic Statuspage.io client.** A single async `httpx` client speaks the
  public `/api/v2/*` contract (`status.json`, `incidents/unresolved.json`,
  `scheduled-maintenances/active.json`) — covering 80%+ of major SaaS providers
  with no provider-specific code and no authentication.
- **28-provider seed registry** (`agent/providers.json`) covering Snowflake,
  Datadog, MongoDB, GitHub, PagerDuty, and more.
- **S3-backed live registry with conditional GET.** The running server reads the
  provider registry from S3 using ETag / `If-None-Match`, so operators can add or
  remove providers by pushing a new `providers.json` (via `refresh-providers`)
  with no redeploy. Local development falls back to the repo-local seed.
- **Stateless AgentCore Runtime hosting.** Deployed to Amazon Bedrock AgentCore
  Runtime over the `streamable-http` transport (`stateless_http=True`,
  `json_response=True`), `PUBLIC` network mode, Python 3.13 — no VPC, no database,
  every call a fresh read.
- **SigV4 security model.** The runtime is IAM-protected; DevOps Agent assumes a
  dedicated signing role scoped to `bedrock-agentcore:InvokeAgentRuntime` on the
  runtime ARN, with a trust policy limited to `aidevops.amazonaws.com` in the
  caller's account and Agent Space region.
- **Two IaC paths.** CDK (Python) and Terraform, both producing the same runtime
  stack plus an optional DevOps Agent registration stack (SigV4 signing role,
  `AWS::DevOpsAgent::Service`, `AWS::DevOpsAgent::Association` enabling the four
  tools).
- **One-command deploy scripts** for Windows (PowerShell) and macOS/Linux (bash),
  covering both the CDK and Terraform paths, plus `setup-devops-agent` for
  registration and `refresh-providers` for live registry updates.
- **Optional stdio testing bridge** (`local-proxy/proxy.py`) that lets a local MCP
  client exercise the deployed runtime by SigV4-signing calls with local AWS
  credentials — a testing aid only, not a supported production client.
- **Unit tests** (`tests/test_tools.py`) covering all four tools with mocked
  Statuspage.io responses (operational, degraded, active incident, active
  maintenance, history, bulk-check, and the 10-provider cap), plus an end-to-end
  `invoke_test.py` against a deployed runtime.

[1.0.0]: https://github.com/aws/tools-for-devops-agent
