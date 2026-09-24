# PostgreSQL DBA MCP skill

This AWS DevOps Agent skill provides read-only diagnostic workflows for Amazon RDS for PostgreSQL and Aurora PostgreSQL through the companion `postgresql-dba-mcp` server's 10 tools and 55 predefined queries. It routes health checks to a complete validated 26-section Markdown tool result presented on screen, and guides targeted PostgreSQL investigations while enforcing fail-closed evidence and recommendation rules. Reports are delivered on screen only: in AWS DevOps Agent the complete Markdown is available from the expandable Output panel while the managed primary chat may add a summary. There is no downloadable-file or HTML delivery, and the MCP server never writes to S3 or returns a URL.

The current v1.18 report contract preserves all 26 canonical sections, renders raw evidence followed by at most one natural `Automated DBA Assessment`, suppresses the assessment for collected zero-row sections, and never renders the superseded `Evidence-Based Insight` paragraph. Internal priority and routine no-change fields remain available for validation without appearing in customer prose.

> **Non-production disclaimer:** This skill is sample code and is not intended for production use without additional security review, operational review, and testing. Validate it with representative resources in a non-production environment first.

## Prerequisites

- An AWS DevOps Agent Space authorized for non-production validation
- The companion [`../../mcp/postgresql-dba-mcp/`](../../mcp/postgresql-dba-mcp/) server deployed and registered with exactly its 10 read-only tools
- An allowlisted RDS for PostgreSQL or Aurora PostgreSQL target, database, and endpoint
- A dedicated least-privilege PostgreSQL monitoring login configured by the MCP deployment
- Agent Space access to the intended Chat and investigation experiences

The skill never accepts credentials. The MCP server retrieves one configured Secrets Manager secret and enforces its own resource, TLS, and read-only transaction boundaries.

## Installation

Create upload artifacts from tracked package files only; do not recursively package the working directory because it can contain `.aws-sam`, bytecode, test caches, `debug.log`, or generated evidence. For the Agent Space skill-edit workflow, attach `SKILL.md` as the primary definition and attach `references/investigation-workflows.md` as a reference file. Preserve the existing skill identity and Chat association when replacing content. A standalone `SKILL.md` is incomplete because it delegates detailed procedures to that reference. Start a new Chat after replacement so prior conversation state does not mask activation. Keep README, changelog, tests, and eval evidence in source control as required by the target repository. For public repository publication, submit the uncompressed directory rather than a ZIP.

## When it activates

The description is designed to trigger for PostgreSQL health checks, upgrade readiness, vacuum and bloat analysis, parameter and memory sizing, index review, SQL plans, replication, connections, and lock investigation. Operators should use natural language and should not need to name the skill.

Example prompts:

- `Run a PostgreSQL health check.`
- `Create a PostgreSQL health report for this cluster.`
- `Check whether this Aurora PostgreSQL cluster is ready for a major version upgrade.`
- `Analyze shared_buffers for this PostgreSQL instance.`
- `Investigate vacuum and transaction ID risk.`
- `Review expensive PostgreSQL statements and explain the approved SELECT without running it.`

A health-check prompt produces the complete on-screen Markdown report. The five-query quick path requires explicit user intent. There is no downloadable-file or HTML delivery.

## Safety model

- Diagnostics and evidence collection are read-only.
- Remediation commands are inert proposals and are never executed by this skill.
- The complete health report is available from the AWS DevOps Agent tool's
  expandable **Output** panel. The managed primary chat may add a summary; the
  skill does not control or suppress that platform response.
- Query previews are bounded, normalized, and redacted by the MCP server; the skill never reconstructs literals or bind values.
- RDS PostgreSQL and Aurora PostgreSQL are evaluated separately.
- Configuration recommendations require exact platform, provenance, workload, and approval evidence.
- Upgrade output is supporting evidence, not approval.

Detailed procedures are in:

- [`references/investigation-workflows.md`](references/investigation-workflows.md)

## Testing

Run deterministic contract tests from this skill directory:

```bash
python -m pytest tests -q
```

Run Agent Skill Eval after installing the published evaluator:

```bash
skill-eval --debug-log debug.log report . --timeout 1200 --runs-trigger 1
```

The root `passed` field in `evals/report.json` must be `true`. Review every audit, functional, and trigger result before publication. Also test at least three natural-language runs in the intended Agent Space, confirm activation in the reasoning trace, and test every relevant subagent.

## Limitations

- The skill depends on the separately deployed MCP server and its allowlists.
- AWS DevOps Agent may place the complete Markdown in an expandable Output panel,
  append managed commentary in the primary chat, or deduplicate a repeated request
  in the same conversation. Start a new chat for an independent rerun; custom
  skills cannot reliably override the managed final-response format.
- Plan-only `EXPLAIN` executes planning but does not execute the underlying `SELECT`; PostgreSQL planning-time function evaluation remains a documented risk that requires a separate security review before enabling this optional surface.
- Production use requires the documented MCP security and operational approval process.
