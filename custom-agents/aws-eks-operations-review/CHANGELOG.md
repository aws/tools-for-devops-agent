# Changelog

## 1.0.0

- Initial version
- Orchestrates the `aws-eks-operations-review` skill (requires skill version 1.9.3+) for a full read-only EKS operations review
- Publishes multiple artifacts per run — one Summary plus one per graded pillar — instead of a single cumulative artifact, so most artifacts complete in one or two render calls and each finished pillar is a standalone deliverable
- Grades nine pillars plus AWS API and Cluster Insights rows; every row carries a verdict and cited evidence, and an unassessable row stays in the report as N/A with its exact reason
- Detailed remediation per finding: ordered steps naming the specific resource and field, validation, rollback, effort, and an authoritative documentation link, capped at 150–300 words to bound render payload
- Remediation Depth Contract defines a full form (ten sections, Critical/High) and a compact form (five sections, Medium/Low or budget-demoted), with observed evidence, ordered steps, validation, and a reference as the floor no tier or degradation may drop; bans generic filler as a contract failure
- Evidence & Accuracy Rules require every verdict to come from an observed result — empty output never proves health — with a verification step before any signal is declared missing, and a paired visibility FAIL whenever telemetry is absent
- Coverage & QA Gate checklist judged against the master ledger at S7, including per-unit count match, every check ID exactly once, gate decisions, artifact-plan completeness, and declared-versus-silent degradation
- Artifact schemas fix element types to `data_table`, `chart`, and topology only, with JSON shapes for the Executive Summary cell, per-pillar scorecard, and per-pillar findings table
- JSON escaping rules for the artifact payload, which findings prose breaks most often because remediation steps embed shell commands and JMESPath queries: only JSON's own escapes are valid, backticks are never escaped, and JMESPath single-quoted raw strings are preferred over backtick literals. An encoding failure is classified separately from a stall so it does not trigger batch halving or finding demotion, which cannot fix invalid escaping
- Delegates discovery, telemetry, per-pillar grading, remediation prose, QA, and rendering to subagents so the orchestrator never holds raw payloads or finding bodies
- QA coverage gate must pass before any artifact is rendered; each artifact is read back and reconciled against its section plan afterward
- Per-artifact monotonicity guard plus periodic checkpoint verification detect lost element accumulation under replace semantics rather than deferring all verification to the end of the run
- Runtime budget with a degradation ladder — skipped or compacted scope is declared in the Summary artifact and the final report rather than silently omitted
- Requires `list_artifacts` alongside `create_or_update_artifact` so re-runs update existing artifacts by title instead of creating duplicates
- Uses the `understanding-agent-space`, `tool-use-best-practices`, and `chat-tool-use-best-practices` memory stores
- Scope is pinned to cluster `retail-store-demo` in `us-east-1`; edit Workflow step 1 of the system prompt to target a different cluster
