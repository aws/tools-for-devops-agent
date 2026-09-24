# Changelog

All notable changes to the PostgreSQL DBA MCP skill are documented here.

## [1.18.0] - 2026-09-16

### Removed

- Removed downloadable-HTML report delivery entirely. The AWS DevOps Agent platform cannot reliably deliver a caller-provided downloadable file (the artifact pipeline rejects hand-built HTML, and large tool results are row-truncated in the agent's context), so reports are now delivered **on screen only** as the MCP's validated Markdown tool result in the Output panel.
- Deleted `assets/templates/health-report.html` and `references/html-delivery.md`.
- Removed the `report_format="html"` mode from the companion MCP's `run_full_health_check` and `check_upgrade_readiness` tools (health accepts `markdown`/`quick`; pre-upgrade accepts `markdown`). Deep pre-upgrade data-plane checks remain available via category-10 `execute_health_query`.

### Changed

- Rewrote the Report-mode workflow to on-screen-only: a request phrased as "downloadable", "HTML", "a file", or "a report link" is served the same way (complete on-screen report) with a plain statement that no downloadable file is produced.
- Added an explicit empty-allowlist fallback (state that no instance is available for diagnostics and stop).
- Aligned the MCP server instructions, tool docstrings, and both READMEs to the on-screen-only delivery model.

## [1.17.0] - 2026-09-16

### Changed

- Adopted the agent-authored downloadable-report pattern (Route A), matching the aws-samples Redshift skill. The AWS DevOps Agent platform cannot persist a tool's returned bytes to a downloadable file, so the orchestrator now renders the MCP's validated report content into a locked, self-contained HTML template (`assets/templates/health-report.html`) and emits the filled file as a downloadable `.html` artifact with an in-file self-download button.
- Downloadable-report requests now call `report_format="markdown"` (the validated content source) and render it into the template, instead of relying on the MCP's `html` output being persisted verbatim (which the platform cannot do).
- Removed the verbatim-save / native-file-save delivery wording that instructed a save the platform cannot perform and caused false "download ready" claims.
- Added an explicit HTML-escaping requirement for untrusted database-sourced values (table/column/index names, query text, error messages, endpoints) before substitution into the template.
- No MCP server change: the server still generates and validates the complete report content; only the skill's delivery path changed.

### Added

- `assets/templates/health-report.html` - locked structural template (compact inline CSS, per-section render pattern for all 26 sections plus Automated DBA Assessment blocks, self-download button). Contains no customer data.

## [1.16.0] - 2026-09-16

### Changed

- Fixed the client-side HTML delivery gap: the skill now REQUIRES the orchestrator to persist the MCP's returned HTML verbatim as a downloadable `.html` artifact in the chat Artifacts panel using the native file/artifact save capability, and to re-attach it if the user cannot find it. Previously the skill forbade every native artifact/save path, which — after S3 removal — left no way to deliver the report to the Artifacts panel.
- Clarified the distinction between prohibited report *construction* (no independent diagnostics, no reconstruction/summary/substitute report) and the required report *delivery* (verbatim persistence of the MCP's exact bytes). Delivery via the native file/artifact save is explicitly not report construction.
- No change to report content: the MCP still generates and validates the complete self-contained HTML; only the save/attach step is unblocked.

## [1.15.0] - 2026-09-11

### Changed

- Adopted the client-side HTML delivery pattern: downloadable HTML health and pre-upgrade requests now call MCP `report_format="html"` and save the returned self-contained HTML verbatim as a downloadable `.html` file in the chat Artifacts panel.
- Removed all `html_download`, presigned-URL, and temporary-download-link guidance; the MCP server no longer writes to S3 or returns a URL, so there is no bearer-URL exfiltration path.
- Renamed `references/raw-html-delivery.md` to `references/html-delivery.md` and made it the single HTML download procedure for both report types.

## [1.14.0] - 2026-09-01

### Changed

- Aligned the skill with MCP 1.14, on-screen schema 1.2, and HTML template 1.5.
- Required one natural `Automated DBA Assessment` for evidence-bearing sections, prohibited the superseded `Evidence-Based Insight`, and suppressed assessments for collected zero-row sections.
- Kept internal priority and routine no-change values out of customer-visible prose while preserving validation and remediation ordering.
- Required standard Markdown download-link syntax without angle-wrapping or rewriting presigned URLs.
- Removed the automatic `postgres` fallback; the agent must use an explicitly selected or confirmed allowlisted database.
- Clarified that Agent Space replacement attaches `SKILL.md` and both reference files through the skill-edit workflow, while public repository publication uses the uncompressed directory.

## [1.13.0] - 2026-08-31

### Changed

- Made natural downloadable PostgreSQL health and pre-upgrade requests exclusive direct MCP `html_download` intent.
- Explicitly prohibited delegation to Artifact Agent, other agents/skills, or substitute native artifact workflows.
- Required the MCP-provided clickable Markdown link and structured presigned-URL descriptor to be returned unchanged as the primary response.
- Aligned omitted report names with automatic Aurora cluster or RDS instance labels.

## [1.12.0] - 2026-08-31

### Changed

- Synchronized the skill with the corrected 55-query MCP catalog and canonical total-execution-time and potential-duplicate-index report titles.
- Added Aurora cluster-scoped availability, storage, encryption, deletion-protection, backup, and `VolumeBytesUsed` interpretation rules.
- Added `pg_stat_statements` reset-window and diagnostic-role self-observation boundaries.
- Expanded upgrade guidance through queries 10.1-10.12 with exact target versions, exact-target class orderability, user-created ICU scope, and database-local versus cluster-wide evidence.
- Added table-level physical-bloat and plan-only EXPLAIN analysis guardrails, including precise read-only execution wording.
- Corrected generic-health evaluation behavior for the authoritative Output panel and removed the inaccurate blanket claim that no command executed.

## [1.11.0] - 2026-08-24

### Changed

- Added privacy-aware interpretation of server-produced normalized query previews for performance, long-running activity, and lock diagnostics while prohibiting reconstruction of literals or bind values.
- Split detailed raw-HTML and targeted-investigation procedures into reference artifacts while keeping the primary skill below 500 lines.
- Aligned generic-health guidance with live AWS DevOps Agent behavior: the complete validated Markdown is available from the expandable Output panel, managed primary-chat summaries are platform-controlled, same-chat reruns may be deduplicated, and targeted follow-ups should invoke fresh predefined diagnostics.

## [1.10.0] - 2026-08-24

### Changed

- Required verbatim reproduction of complete 26-section Markdown tool output.
- Added hidden-marker, ordered-heading, remediation, and fail-closed display contracts.

## [1.9.0] - 2026-08-24

### Changed

- Made complete on-screen Markdown the default for generic health checks.
- Restricted quick mode and HTML delivery to explicit user intent.
- Removed the unsupported universal health scorecard.

## [1.8.0] - 2026-08-24

### Added

- Added explicit downloadable HTML routing with complete-report validation and short-lived delivery.

## [1.7.0] - 2026-08-24

### Changed

- Added deterministic report routing and one-question scope clarification.

## [1.6.0] - 2026-08-24

### Added

- Added canonical report section/check ordering and fail-closed truncation guidance.
