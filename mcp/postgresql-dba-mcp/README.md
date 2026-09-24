# PostgreSQL DBA MCP Server for AWS DevOps Agent

A Model Context Protocol (MCP) server for read-only diagnostics of Amazon RDS for PostgreSQL and Aurora PostgreSQL. It exposes exactly 10 MCP tools, including 55 predefined SQL diagnostics across 11 categories, and complete Markdown health/pre-upgrade reports presented on screen (`report_format="markdown"`, plus an explicit five-query `quick` health mode). Reports are returned as the tool result and shown in the AWS DevOps Agent Output panel; the server produces no downloadable file, no HTML document, and never writes to S3 or mints a presigned URL. Its higher-risk free-form EXPLAIN surface remains registered but is disabled by default in the non-production demo configuration.

This MCP server is sample code for technical review. Validate it in a non-production account and database before broader use.

> **AWS DevOps Agent only:** This server uses Streamable HTTP with AWS IAM/SigV4 and is designed exclusively for AWS DevOps Agent. It is not compatible with stdio-based local MCP clients such as Kiro, Cursor, or VS Code.

## Deployment status and boundaries

The SAM template creates or updates:

- A Python 3.12 Lambda function running FastMCP over Streamable HTTP
- An IAM-authenticated Lambda Function URL using response streaming
- A Lambda layer with pinned Python dependencies
- A VPC attachment for database connectivity
- A Lambda execution role scoped to the configured secret and diagnostic AWS APIs, plus the EC2 network-interface lifecycle actions required for Lambda VPC attachment
- Four private AWS API interface endpoints in one approved subnet, protected by a dedicated endpoint security group

The stack does **not** create the database login, secret, subnets, Lambda/database security groups, NAT gateway, AWS DevOps Agent registration, or Agent Space association. Those remain separate changes requiring explicit approval.

The MCP endpoint is the `MCPEndpointUrl` stack output and ends in `/mcp`.

### Default-off non-production demo surface

The non-production demo configuration keeps one higher-risk surface inert by
default:

- `EXPLAIN_QUERY_ENABLED=false` keeps `explain_query` registered and documented,
  but the tool returns a disabled error before parsing SQL or opening a database
  connection.

This is a deployment-controlled flag, not an MCP tool argument. Enabling it
requires an explicit deployment change and a separate security review of the
resulting input and output surface. The SAM parameter `ExplainQueryEnabled`
defaults to `false`.

### Report delivery: on screen only, no server publication

Reports are delivered on screen only. `run_full_health_check` and
`check_upgrade_readiness` return the complete, validated report as one Markdown
tool result, which the AWS DevOps Agent shows in its expandable Output panel. The
server produces **no** downloadable file, no HTML document, no S3 object, and no
URL: it does not write to Amazon S3, create a bucket, or mint a presigned URL, so
there is no server-side report publication Way Out and no bearer download
credential. No tool accepts a bucket, key, AWS account, role, ARN, URL, or
external domain. Report delivery is therefore read-only from the server's
perspective.

## Safety model

1. `execute_health_query` accepts only one of 55 predefined SQL queries.
2. `explain_query` is registered but returns a disabled error by default under `EXPLAIN_QUERY_ENABLED=false`, before parsing or connecting. If a separately reviewed deployment enables it, the retained validator requires exactly one PostgreSQL `SelectStmt`, rejects every function call plus data-changing CTEs, `SELECT INTO`, and row-locking clauses, and runs plan-only `EXPLAIN` with `search_path` restricted to `pg_catalog`.
3. Each database connection explicitly opens `BEGIN READ ONLY`, verifies `transaction_read_only=on`, and applies local timeouts before diagnostic SQL.
4. Database names, RDS instance identifiers, and database endpoint hostnames require explicit allowlists. The runtime fails closed when a required value is missing or its entire value is `*`; deployment instructions prohibit wildcards.
5. Data-plane tools can use only the one `SECRET_ARN` configured on the Lambda function.
6. The secret must contain exactly non-empty string `username` and `password` fields.
7. PostgreSQL TLS verifies the certificate and endpoint hostname against the SHA-256-pinned Amazon RDS global CA bundle packaged by the layer build.
8. The Lambda Function URL uses `AWS_IAM`; do not change it to `NONE`.
9. Use a dedicated PostgreSQL login with `CONNECT` and `pg_monitor`, not an application owner or `rds_superuser`.
10. In AWS DevOps Agent, register only the 10 documented tools. All tools are read-only: diagnostics return evidence, and reports are returned as on-screen Markdown tool results with no S3 write, URL, or downloadable file. Do not enable free-form EXPLAIN (`EXPLAIN_QUERY_ENABLED=true`) without a separate security review and explicit deployment change.
11. Every `shared_buffers` analysis uses explicit fail-closed evidence gates. Call `list_rds_instances()` first; for Aurora, analyze the sole current allowlisted writer, collect `get_instance_config`, 60 minutes of `get_instance_metrics`, DB instance parameter-group evidence, and live query 2.1, then finish with `list_rds_instances(expected_writer_id="<writer-id>")`. The analysis may continue only when that call emits `SHARED_BUFFERS_FINAL_GATE: PASS`; on failure, discard mixed evidence and restart once. The PASS response emits the exact reader opt-in question. Reader analysis, when approved, uses individual allowlisted reader instance endpoints rather than the load-balanced reader endpoint. Query 2.1 reports effective PostgreSQL settings, not AWS parameter provenance. `get_parameter_group` reads only the DB instance parameter group; with `filter_modified=True` it returns only `AWS Source=user` values, because `Source=system` formulas are not user overrides. Aurora cluster provenance and exact engine defaults remain `UNKNOWN` unless separately proven. `get_instance_config` and `get_instance_metrics` emit `MEMORY_SIZING_GATE: INSUFFICIENT_EVIDENCE`; metrics emit `CACHE_FIT_GATE: OBSERVATION_ONLY`. Therefore, no percentage, page count, formula, byte/GiB target, reset, or reboot action may be inferred from advertised RAM, cache-hit ratio, or FreeableMemory, or back-solved from `effective_cache_size`, another live setting, or a sibling formula. A perfect cache-hit observation does not prove the working set fits, and FreeableMemory is availability/reclaimability evidence—not wasted or unused memory. For Aurora, the baseline policy is `USE_VERIFIED_AURORA_ENGINE_DEFAULT`: once exact cluster provenance and the exact engine default are independently verified, recommend that verified default unless an approved workload-specific reason supports a custom value. A perfect cache-hit ratio does not change this policy, and the default must not be described as a fixed percentage without exact version-specific evidence. RDS PostgreSQL uses query 6.3 for its connected-database cache observation and does not use the Aurora final-writer or reader-question flow.

These application controls supplement—not replace—IAM, VPC, security-group, database privilege, and change-management controls.

### Security review focus: planning-time function evaluation

`explain_query` is the server's only free-form SQL surface. PostgreSQL can evaluate `IMMUTABLE` or `STABLE` expressions while planning an `EXPLAIN`, even when `ANALYZE` is absent and the execution plan itself is not run. The server therefore rejects every parsed `FuncCall`, including built-in, extension, user-defined, and schema-qualified function calls.

The parser and fail-closed AST walk require one `SelectStmt` containing no function call, data-changing CTE, `SELECT INTO`, or row-locking clause. The independently verified read-only transaction and `SET LOCAL search_path = pg_catalog` provide additional runtime boundaries. Keep the dedicated least-privilege diagnostic login and restricted network path as defense in depth, and validate first in a non-production environment.

### IAM wildcard rationale

Secrets Manager access is scoped to the configured secret ARN. The template uses `Resource: "*"` only for the narrowly enumerated RDS and EC2 describe calls, CloudWatch metric retrieval, and Lambda VPC network-interface lifecycle actions for which resource-level permissions are unavailable or incomplete. The exact action sets, configured Region and resource allowlists, VPC endpoint policies, security groups, and private network path provide additional boundaries. Apply supported condition keys where practical without weakening deployment functionality.

The interface endpoint policies also use `Principal: "*"` and `Resource: "*"` for their narrow action lists. This does not make an interface endpoint public: callers still require IAM authorization and network reachability through the VPC endpoint and security groups.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `execute_health_query` | Run one predefined diagnostic by category and query ID |
| `list_health_queries` | List the 55 query IDs and 11 categories |
| `run_full_health_check` | Run the complete 26-section on-screen health check (`markdown`) by default, or the explicit five-query `quick` check |
| `list_rds_instances` | List only allowlisted instances and resolve current Aurora writer/reader topology |
| `get_instance_config` | Read instance, engine, storage, parameter-group, and Aurora-role metadata |
| `get_instance_metrics` | Read CloudWatch CPU, memory, I/O, latency, connection, and Aurora `BufferCacheHitRatio` metrics for 1 to 50,400 minutes with a datapoint-safe dynamic period |
| `explain_query` | Run plan-only `EXPLAIN` for one conservatively validated `SELECT` |
| `get_parameter_group` | Read an RDS DB parameter group |
| `get_log_files` | List RDS PostgreSQL log-file metadata; it does not read log contents |
| `check_upgrade_readiness` | Run on-screen Markdown control-plane pre-upgrade heuristics (`markdown`); deeper data-plane checks are available via category-10 `execute_health_query` |

### BYO MCP tool classification

Classify tools from their **enabled deployment behavior**, not from the name of
the server or its normal diagnostic use:

| Deployment configuration | Tool classification |
| --- | --- |
| Default: `ExplainQueryEnabled=false` | Classify all 10 registered tools as **Read only**. Diagnostics return evidence, and reports are returned as on-screen Markdown tool results with no S3 write, URL, or downloadable file. The disabled `explain_query` tool returns before parsing or connecting. |
| Separately reviewed deployment with `ExplainQueryEnabled=true` | Classify `explain_query` as **Mutative** and keep it unavailable in autonomous mode because PostgreSQL planning can evaluate database-defined behavior. The current public sample does not approve enabling this surface. |

The remaining tools stay **Read only**. This MCP exposes no **Destructive**
tool and performs no S3 write or bearer-URL creation. Tool classification is
defense in depth: it does not replace the `ExplainQueryEnabled` flag, target
allowlists, least-privilege PostgreSQL role, or the separate security review
required before the EXPLAIN surface is enabled.

`check_upgrade_readiness` is not upgrade approval. Combine it with category 10 diagnostics, extension compatibility checks, AWS pre-upgrade checks, and testing on a restored snapshot or clone.

### On-screen customer-shareable reports

Reports are delivered on screen as a Markdown tool result; the server produces
no downloadable file and no HTML document. The diagnostic content derives from
the public MIT-0
[`aws-samples/sample-rds-aurora-postgres-dba-toolkit`](https://github.com/aws-samples/sample-rds-aurora-postgres-dba-toolkit)
at pinned commit `5172525155139b455c25cd7f879bfdda38c13bf3`. Every dynamic value
is escaped, and the report footer identifies the upstream source/commit.

By default, `run_full_health_check(..., report_format="markdown",
instance_id="...", report_name="...")` runs all 26 canonical sections and
returns one server-validated Markdown tool result with begin/end completeness
markers and section-aware metadata. In AWS DevOps Agent, live testing shows the
complete report in the tool's expandable **Output** panel; the managed primary
chat may add its own summary or commentary. Custom skill instructions and MCP
metadata cannot reliably override that managed final-response behavior. The
Output result includes 1-day, 15-day, and 35-day CloudWatch averages, a focused
reference-toolkit parameter table, and a deterministic structured assessment model
for all 26 canonical sections. Customer-facing reports render an `Automated DBA
Assessment` only when evidence exists or an evidence gap needs explanation. The internal model retains
`Finding`, `Priority`, `Why it matters`, `Recommendation`, `Validation required`,
`Limitations`, and explicitly inert `Proposed changes`; customer-facing HTML and
Markdown project applicable fields into one natural paragraph without visible
field labels. Internal priority and routine no-change values remain hidden, and a
collected zero-row section renders only `No rows returned` plus references rather
than a generic assessment. Hidden ordered boundaries preserve fail-closed
completeness validation.
Cross-section relation, index, and statement conclusions use catalog identities
rather than display names.
Index reviews report OID-deduplicated counts and bytes, category overlap, and the
top three exact objects. The prioritized remediation summary is projected from
these assessments with validation, risk/approval, and rollback guidance. The
legacy `Evidence-Based Insight` paragraph is not rendered, preventing duplicate
recommendations; each section with collected evidence or an evidence gap shows raw evidence followed by at most one assessment. Collected zero-row sections remain present without an assessment. Use
`report_format="quick"` only for the explicit legacy five-query check.

`run_full_health_check(..., report_format="markdown", instance_id="...",
report_name="...")` returns the complete structured 26-section evidence and
guidance as one Markdown tool result. `check_upgrade_readiness(...,
report_format="markdown", ...)` returns the on-screen Markdown control-plane
pre-upgrade heuristics; deeper data-plane pre-upgrade evidence is available via
category-10 `execute_health_query`. The server validates completeness and
explicit evidence states, then returns the report as the tool result; it
produces no downloadable file, no HTML, no S3 write, and no URL. It also binds
the selected instance to its current standalone or Aurora writer endpoint;
independently allowlisted but unrelated targets are rejected. Customer report
statement sections are restricted to the connected database and retain each
query fingerprint alongside a server-generated `normalized_query_preview`. The
preview is limited to 240 characters, accepts only parsed DML, removes comments,
and replaces literals and bind references before report serialization. Raw or
full query text and usernames are not included. A full normalized statement
still requires a separate, explicit, approved `pg_stat_statements` lookup.

Reports are delivered on screen only. In AWS DevOps Agent, the complete Markdown
tool result is available from the expandable **Output** panel, while the managed
primary chat may show an additional summary.

Every canonical section is always rendered. Missing evidence appears as `No
rows returned`, `Not applicable`, `Not collected`, or `Error`; incomplete
output is never silently omitted. Only the connected allowlisted database is
checked for database-local upgrade evidence. Other allowlisted databases are
marked `Not collected` until separately connected and checked.

The renderer intentionally does not reproduce unsafe advice from the historical
sample. It keeps dead-tuple ratios separate from the pinned toolkit's statistical
physical-layout bloat estimate, labels that estimate as heuristic rather than
measured reclaimable space, does not infer cache fit, derive `shared_buffers`
from memory or sibling settings, prescribe index/slot/reader actions, issue
immediate maintenance commands, or claim upgrade approval.

## Example AWS DevOps Agent chat prompts

Replace the placeholders with values from the configured allowlists:

- `<allowlisted-endpoint>`: an approved RDS instance endpoint, Aurora cluster writer endpoint, or Aurora reader **instance** endpoint used by database tools; scoped reader analysis does not use the load-balanced cluster reader endpoint
- `<allowlisted-database>`: an approved PostgreSQL database name, such as `postgres`
- `<allowlisted-instance-id>`: an approved RDS or Aurora DB **instance identifier** used by AWS control-plane tools

The server supplies its configured Secrets Manager credential automatically. Do not include usernames, passwords, or alternate secret ARNs in chat. These prompts request diagnostics only; review and approve any remediation separately.

| Goal | Example chat prompt |
| --- | --- |
| Discover targets | “List the PostgreSQL instances available to this diagnostic server.” |
| Discover checks | “Show all available PostgreSQL health queries and their category and query IDs.” |
| Complete Markdown health check | “Run a complete health check for `<allowlisted-instance-id>` against `<allowlisted-endpoint>`, database `<allowlisted-database>`. In AWS DevOps Agent, expand the tool Output panel to view all 26 sections; the primary chat may show a managed summary.” |
| Quick health check | “Run the explicit five-query quick health check against `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Customer-shareable report | “Create a health report for `<allowlisted-instance-id>` against `<allowlisted-endpoint>`, database `<allowlisted-database>`, using report name `<approved-report-name>`. Present it on screen in the Output panel.” |
| Server and configuration | “Run PostgreSQL version check 1.1 and key-parameter check 2.1 against `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Instance configuration | “Show the RDS/Aurora configuration for `<allowlisted-instance-id>`.” |
| CloudWatch metrics | “Show CPU, memory, connections, I/O, latency, storage, and swap metrics for `<allowlisted-instance-id>` over the last 60 minutes. Include `BufferCacheHitRatio` when the target is Aurora.” |
| `shared_buffers` review | “Analyze `shared_buffers`. Resolve the current Aurora writer and analyze it first; include 60 minutes of CloudWatch `BufferCacheHitRatio`, then recheck that the writer did not change. For RDS PostgreSQL, run cache-hit query 6.3 for the connected database instead. Ask before repeating the same analysis on individual allowlisted Aurora reader endpoints.” |
| Connections and locks | “Check connection usage, queries running longer than 30 seconds, and lock waits on `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Replication | “Run replication-status check 4.1 and replication-slot check 4.2 against `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Storage and dead tuples | “Show the largest tables and dead-tuple ratios on `<allowlisted-endpoint>`, database `<allowlisted-database>`. Treat dead tuples as an indicator, not a physical bloat estimate.” |
| Vacuum and transaction IDs | “Check vacuum history and transaction ID wraparound risk on `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Index review | “Show unused indexes, potentially duplicate indexes, and table scan ratios on `<allowlisted-endpoint>`, database `<allowlisted-database>`. Do not make index changes.” |
| Query performance | “Show the queries with the highest total and mean execution time on `<allowlisted-endpoint>`, database `<allowlisted-database>`.” |
| Plan inspection | “Run plan-only `EXPLAIN` for this query on `<allowlisted-endpoint>`, database `<allowlisted-database>`: `SELECT ...`. Do not use `ANALYZE`; report the planning-time function-evaluation caveat.” |
| Parameter group | “Show only modified parameter-group settings for `<allowlisted-instance-id>`.” |
| Log metadata | “List the 20 most recent PostgreSQL log files and their sizes for `<allowlisted-instance-id>`. Do not read log contents.” |
| Upgrade readiness | “Run the control-plane readiness checks for upgrading `<allowlisted-instance-id>` to PostgreSQL 17, then run category 10 database checks against `<allowlisted-endpoint>`, database `<allowlisted-database>`. Report blockers and warnings; do not perform an upgrade.” |
| Customer-shareable pre-upgrade report | “Run the pre-upgrade readiness checks for `<allowlisted-instance-id>` targeting PostgreSQL 17, using report name `<approved-report-name>`. Present it on screen and do not claim approval.” |

If the target value is not allowlisted, the tool returns an error. Mentioning a different cluster, endpoint, database, or instance in chat does not bypass the deployed allowlists.

## Query catalog

| Category | Query IDs | Count | Purpose |
| --- | --- | ---: | --- |
| 1. Server Information | 1.1-1.4 | 4 | Version, uptime, database sizes, and total size/count |
| 2. System Configuration | 2.1-2.3 | 3 | Live settings plus internal report evidence; the visible report is limited to the 11 reference-toolkit key parameters |
| 3. Current Activity | 3.1-3.4 | 4 | Connections, long-running queries, and waits |
| 4. Replication | 4.1-4.2 | 2 | Replication status and slots |
| 5. Storage and Bloat | 5.1-5.5 | 5 | Relation sizes, dead tuples, tablespaces, exact top 10, and heuristic bloat estimate |
| 6. Performance | 6.1-6.9 | 9 | `pg_stat_statements`, reset-window evidence, all-database cache, shared reads, and temporary I/O |
| 7. Vacuum and Maintenance | 7.1-7.4 | 4 | Vacuum status, transaction ID age, and largest-table history |
| 8. Index Optimization | 8.1-8.4 | 4 | Unused/duplicate/rare indexes and scan ratios |
| 9. Summary Health | 9.1 | 1 | Composite health metrics |
| 10. Pre-Upgrade Checks | 10.1-10.12 | 12 | Transactions, types, slots, extensions, GiST, ICU, names, and pending restart |
| 11. Extended Health | 11.1-11.7 | 7 | Keys, invalid indexes, sequences, XID age, activity, and table read I/O |

Query 5.2 reports dead-tuple ratio; it is not a physical bloat measurement.
Query 5.5 reproduces the pinned toolkit's statistical table/index physical-layout
bloat estimate; it remains heuristic and is not measured reclaimable space. Query 10.7 inventories visible user views for manual upgrade
review; it does not prove system-catalog dependency.

## Prerequisites

### AWS DevOps Agent

- A non-production Agent Space for initial validation
- Permission to register MCP servers and associate them with the Agent Space
- An account access type that permits this custom MCP server
- An approved onboarding path that signs Lambda Function URL requests with AWS IAM/SigV4

If registration offers only OAuth or API-key authentication, stop. Use the approved AWS-IAM onboarding path or an approved authenticated gateway. Do not make the Function URL public.

Public reference: [Connect MCP servers to AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html)

### Workstation

- AWS CLI v2
- AWS SAM CLI
- Python 3.12 or newer; Python 3.12 is recommended for Lambda parity
- GNU Make, `curl`, `pip3`, and package-index/network access for the layer build
- AWS credentials for a confirmed non-production account
- A commercial AWS Region where Lambda Web Adapter layer `LambdaAdapterLayerX86:24` from account `753240598075` is published
- Read-only VPC/RDS/Secrets Manager permissions for inventory
- CloudFormation, Lambda, IAM, S3/SAM packaging, and EC2 permissions to create/delete interface endpoints and security groups and manage their rules for deployment, unless CloudFormation uses a separately approved service role

### Database and network

- RDS for PostgreSQL or Aurora PostgreSQL
- Approved subnets in the same VPC as, or routed to, the database
- Lambda security-group egress to the database port and TCP 443 to the interface endpoint ENIs
- Database security-group ingress from the Lambda security group
- VPC DNS support and hostnames enabled
- One approved endpoint subnet in that VPC; the template creates private interface endpoints for:
  - `com.amazonaws.<region>.secretsmanager`
  - `com.amazonaws.<region>.rds`
  - `com.amazonaws.<region>.ec2`
  - `com.amazonaws.<region>.monitoring`

The template also creates a dedicated endpoint security group allowing TCP 443 only from the configured Lambda security group. Each interface endpoint incurs hourly and data-processing charges while it exists.

The layer build downloads the official Amazon RDS global CA bundle and verifies its expected SHA-256 before packaging it. A bundle rotation requires an intentional URL/hash review. See [Using SSL/TLS to encrypt an RDS connection](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html). Content was rephrased for compliance with licensing restrictions.

An internet-gateway route alone does not give a VPC-attached Lambda function internet access because its ENI does not receive a public IP address.

## Local validation (no AWS resource changes)

From this MCP package directory (`mcp/postgresql-dba-mcp/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r layers/dependencies/requirements.txt
python -m pip install pytest==8.4.2

# Unit tests force their own deterministic non-production values and ignore
# conflicting allowlist variables inherited from the shell.
python -m pytest tests -q
sam validate --lint --template-file template.yaml
sam build --template-file template.yaml

# These values are for optional local server startup after validation.
export AWS_DEFAULT_REGION=us-west-2
export AWS_EC2_METADATA_DISABLED=true
export STAGE_NAME=test
export SECRET_ARN=arn:aws:secretsmanager:us-west-2:111122223333:secret:test
export ALLOWED_INSTANCES=test-db
export ALLOWED_DATABASES=postgres
export ALLOWED_ENDPOINTS=test-db.example.rds.amazonaws.com
export RDS_CA_BUNDLE="$PWD/.aws-sam/build/DependenciesLayer/python/rds-global-bundle.pem"
```

To start the local server, keep the explicit test environment above, including `RDS_CA_BUNDLE`, and run:

```bash
python src/server.py
```

The local endpoint is `http://127.0.0.1:8000/mcp`. Local startup validates configuration, but data-plane calls also require the built CA bundle, an approved secret, a network route, and a database.

## Pre-deployment read-only inventory

Set these values without placing secrets in shell history:

```bash
export AWS_PROFILE=<non-production-profile>
export AWS_REGION=<aws-region>
export STACK_NAME=postgresql-dba-mcp

aws sts get-caller-identity --profile "$AWS_PROFILE"
aws rds describe-db-instances --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws ec2 describe-subnets --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws ec2 describe-security-groups --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws ec2 describe-vpc-endpoints --profile "$AWS_PROFILE" --region "$AWS_REGION"
aws secretsmanager describe-secret \
  --secret-id <secret-arn> \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION"
```

Confirm account ownership, non-production classification, Region, VPC alignment, subnet routes, security-group paths, service API reachability, exact database endpoints, instance identifiers, and database names before continuing.

## Database and secret preparation (mutating)

Do not run this section without database-owner and AWS change approval.

### 1. Create a dedicated PostgreSQL login

Run as an authorized database administrator through an approved secret-handling process:

```sql
CREATE ROLE devops_agent_dba LOGIN PASSWORD '<generated-password>';
GRANT CONNECT ON DATABASE <database_name> TO devops_agent_dba;
GRANT pg_monitor TO devops_agent_dba;
```

`pg_monitor` supports monitoring views. `explain_query` for application tables additionally requires narrowly scoped privileges on the referenced objects; do not grant broad application access solely to make plan analysis work.

### 2. Create the secret

```bash
aws secretsmanager create-secret \
  --name postgresql-dba-mcp/dev/credentials \
  --secret-string file://<approved-secure-json-file> \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION"
```

The secure JSON file must contain exactly:

```json
{"username":"devops_agent_dba","password":"<generated-password>"}
```

Delete the local secure file through the approved process after secret creation. If a suitable secret already exists, validate and reuse it rather than creating a duplicate. The server intentionally rejects any additional JSON keys, so the standard RDS-managed primary-user secret format is not directly compatible; create a dedicated secret containing exactly `username` and `password`, or implement and review an explicit compatibility change. The template directly supports secrets encrypted with the Secrets Manager AWS-managed key. A customer-managed KMS key requires a reviewed template extension granting the function role narrowly scoped `kms:Decrypt` access and a compatible key policy; do not reuse such a secret without that change.

### 3. Approve the private endpoint cost and placement

This template creates four interface endpoints and a dedicated endpoint security
group. `EndpointSubnetId` deliberately selects one Availability Zone for the
interface endpoints to minimize non-production cost; this reduces AWS API path
availability and may incur cross-AZ data processing when Lambda runs elsewhere.
Expanding interface endpoints to multiple Availability Zones requires a reviewed
template change and increases hourly endpoint charges.

The template creates no report S3 bucket, no S3 gateway endpoint, and grants the
Lambda role no S3 permission. Reports are returned to the caller as an on-screen
Markdown tool result, so no report object is ever written to S3 and no
downloadable file or URL is produced.

## SAM deployment (mutating)

Use explicit values—never `*`. For Aurora, `AllowedInstances` contains DB **instance** identifiers used by control-plane tools; `AllowedEndpoints` may contain approved cluster, reader, or instance endpoints used by data-plane tools.

```bash
export VPC_ID=<vpc-id>
export ENDPOINT_SUBNET_ID=<one-approved-subnet-id>
export SECRET_ARN=<secret-arn>
export SUBNET_IDS=<subnet-id-1>,<subnet-id-2>
export LAMBDA_SG=<lambda-security-group-id>
export ALLOWED_INSTANCE_IDS=<db-instance-id-1>,<db-instance-id-2>
export ALLOWED_DATABASE_NAMES=postgres,<application-database>
export ALLOWED_ENDPOINT_HOSTS=<approved-endpoint-1>,<approved-endpoint-2>

sam validate --lint --template-file template.yaml
sam build --template-file template.yaml

sam deploy \
  --stack-name "$STACK_NAME" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --confirm-changeset \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --parameter-overrides \
    "StageName=dev" \
    "VpcId=$VPC_ID" \
    "EndpointSubnetId=$ENDPOINT_SUBNET_ID" \
    "SecretArn=$SECRET_ARN" \
    "SubnetIds=$SUBNET_IDS" \
    "ExplainQueryEnabled=false" \
    "SecurityGroupId=$LAMBDA_SG" \
    "AllowedInstances=$ALLOWED_INSTANCE_IDS" \
    "AllowedDatabases=$ALLOWED_DATABASE_NAMES" \
    "AllowedEndpoints=$ALLOWED_ENDPOINT_HOSTS"
```

`--confirm-changeset` displays the proposed CloudFormation changes and waits for approval. Review IAM, Lambda, layer, Function URL, VPC, replacement, and deletion actions before approving. Using a different stack name while retaining the explicit Lambda function name can cause a name collision; update the existing intended stack instead.

## Retrieve and test the endpoint (read-only invocation)

```bash
MCP_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='MCPEndpointUrl'].OutputValue" \
  --output text)

FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionArn'].OutputValue" \
  --output text)

printf 'MCP endpoint: %s\nFunction ARN: %s\n' "$MCP_ENDPOINT" "$FUNCTION_ARN"
```

The endpoint must end in `/mcp`. Test IAM/SigV4 initialization with an approved caller before changing DevOps Agent permissions. Invocation creates logs and may incur cost but should not modify database or AWS resources.

## Authorize the AWS DevOps Agent caller (mutating IAM)

Identify the exact caller role. It needs both actions, scoped to the function:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunctionUrl",
      "Resource": "<function-arn>",
      "Condition": {"StringEquals": {"lambda:FunctionUrlAuthType": "AWS_IAM"}}
    },
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "<function-arn>",
      "Condition": {"Bool": {"lambda:InvokedViaFunctionUrl": "true"}}
    }
  ]
}
```

Cross-account callers also require corresponding resource-based permissions on the Lambda function. Scope them to the approved caller account/role; never use a public principal.

AWS reference: [Control access to Lambda function URLs](https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html)

## Register with AWS DevOps Agent (mutating configuration)

1. Confirm the registration workflow supports AWS IAM/SigV4.
2. In **Services**, open MCP server registration and register `MCP_ENDPOINT`.
3. Use a descriptive name such as `PostgreSQL DBA Diagnostics`.
4. Complete the approved authentication setup with the authorized caller.
5. Confirm discovery returns exactly the 10 tools documented above.
6. Select only those tools and keep `ExplainQueryEnabled=false`; all active paths in this demo registration are **Read only**, and reports are on-screen Markdown tool results.
7. Associate the registered server with the intended non-production Agent Space.
8. Confirm that the intended agents can see all 10 tools.

Stop if discovery returns a different count or unexpected tool name.

The companion skill is not packaged in the Lambda stack and is not installed by MCP registration. Install it separately from [`../../skills/postgresql-dba-mcp/`](../../skills/postgresql-dba-mcp/) through an approved AWS DevOps Agent skill workflow; do not place the skill and server in one directory.

## End-to-end verification

Run negative checks before positive diagnostics:

1. A caller without Function URL permissions receives HTTP 403.
2. A non-allowlisted endpoint is rejected before secret retrieval or connection.
3. A non-allowlisted database is rejected.
4. A non-allowlisted RDS instance identifier is rejected.
5. A different secret ARN is rejected.
6. With the default `ExplainQueryEnabled=false`, `explain_query` returns its disabled error before parsing or connecting.
7. The `html` and `html_download` report formats are rejected as invalid (health accepts only `markdown`/`quick`; pre-upgrade accepts only `markdown`); the server performs no S3 write or URL creation on any code path.
8. In a separately reviewed deployment that enables EXPLAIN, verify it still rejects multiple statements, data-changing CTEs, `SELECT INTO`, row-locking clauses, every function call, and any statement whose parsed tree cannot be fully inspected.

Then verify:

1. `tools/list` returns exactly 10 tools.
2. `list_health_queries` returns exactly 55 query IDs across 11 categories.
3. `list_rds_instances` returns only configured instance identifiers and identifies the current Aurora writer/reader roles without exposing non-allowlisted members.
4. `get_instance_config`, `get_instance_metrics`, `get_parameter_group`, `get_log_files`, and the non-publication modes of `check_upgrade_readiness` return read-only metadata for approved resources. Confirm Aurora metrics include `BufferCacheHitRatio`; confirm RDS PostgreSQL guidance directs cache-ratio analysis to query 6.3.
5. `execute_health_query` query 1.1 succeeds against an approved endpoint/database.
6. `run_full_health_check` returns a complete 26/26 Markdown tool result shown on screen in the Output panel; explicit `quick` returns the five-query check; the `html` format is rejected.
7. `explain_query` returns `ERROR: explain_query is disabled in this deployment.` without parsing or connecting.
8. `check_upgrade_readiness` returns on-screen Markdown control-plane pre-upgrade checks; the `html` format is rejected; the server performs no S3 write or URL creation.

Direct Python data-plane tests can be run only against an approved non-production target using the environment documented at the top of `tests/e2e_test.py`.

## Troubleshooting

| Symptom | Likely cause and action |
| --- | --- |
| Function URL HTTP 403 | Verify both invocation actions and any required cross-account resource policy |
| MCP initialization works but AWS tools time out | Verify all four stack-owned interface endpoints are `available`, private DNS is enabled, endpoint-group ingress permits TCP 443 from the Lambda security group, and Lambda-group egress permits TCP 443 to endpoint ENIs |
| Lambda startup reports an allowlist error | Supply explicit instance, database, and endpoint values; wildcards are rejected |
| Secret validation error | Confirm the secret is in the same Region and contains exactly the two non-empty string keys `username` and `password`. Standard RDS-managed primary-user secrets include additional keys and are intentionally rejected. |
| TLS verification error | Confirm an RDS/Aurora DNS endpoint and valid AWS-issued database certificate |
| Database timeout | Check routes, security groups, NACLs, DNS, endpoint availability, and database availability; a disallowed endpoint returns an immediate validation error instead of timing out |
| Query permission error | Grant only the monitoring/object privileges required for that diagnostic |
| Queries 6.1 or 6.2 fail | Confirm `pg_stat_statements` is enabled and installed; queries 6.3 and 6.4 do not require that extension |
| Tool count mismatch | Confirm deployed code revision, refresh discovery, and stop registration until resolved |
| `search_user_tools` reports no tools | Confirm the MCP Capability Provider is enabled and associated with the Agent Space/Chat agent, keep `ExplainQueryEnabled=false`, save the 10-tool read-only selection, reconnect the provider, and start a new chat. |
| Complete Markdown not visible in primary chat | Expand the `run_full_health_check` tool's **Output** panel. AWS DevOps Agent may render the validated 26-section result there and add a managed summary in the primary chat; custom skills cannot reliably override that final-response format. |
| Same-chat rerun is deduplicated | Start a new chat for an independent snapshot. The managed chat layer may treat a repeated request as already answered instead of invoking the tool again. |

Inspect `/aws/lambda/postgresql-dba-mcp-<stage>` without sharing secret values or sensitive connection metadata.

## Remaining limitations

- This sample has not completed production security or operational-readiness approval.
- Direct Function URL registration depends on an AWS DevOps Agent workflow that supports AWS IAM/SigV4.
- Major-version readiness results are limited heuristics, not an authoritative compatibility decision.
- Exact package versions are pinned, but dependency updates still require vulnerability and license review.
- Performance queries 6.1 and 6.2 require separate `pg_stat_statements` configuration.
- Full validation requires a real non-production database and Agent Space.

## Disclaimer

This is sample diagnostic code, not professional database or upgrade advice. Use change control, least-privilege credentials, non-production validation, and independent security review before production use.
