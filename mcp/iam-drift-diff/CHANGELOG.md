# Changelog
## [1.0.1] - 2026-11-16
### Fixed (security review)
- Roles under `/service-role/` are now fully fingerprinted and diffed. 1.0.0 treated that path as AWS-reserved and skipped their trust, attached, inline and boundary fields, so changes to them showed as "no drift". Only `/aws-service-role/` (service-linked roles) is recorded by presence only. Snapshot `schema` is now 2; the first diff after upgrading reports each `/service-role/` role once as `fingerprint_scope_changed` (direction `info`).
- Baseline pointer reads fail closed. 1.0.0 treated any read error (AccessDenied, throttling, 5xx) as "no baseline", so a scheduled run could compare only the latest two snapshots, then record past unreported changes, and capture could prune the reported pair. Now only "not found" means no baseline; other errors return a retryable error with nothing written or pruned. An invalid pointer makes the diff compare against the oldest retained snapshot (`baseline_source: baseline_pointer_invalid`) and capture skip pruning.
- `iam_snapshot_list` reports `baseline_error` instead of failing when the pointer is unreadable or invalid.
- A baseline pointer that names snapshots no longer in the bucket now also makes the diff compare against the oldest retained snapshot (`previous_baseline_missing`), instead of the latest two.
- Every S3 call passes `ExpectedBucketOwner`, and the execution role's S3 statement requires `aws:ResourceAccount` to be the deploying account.
- A malformed `x-amzn-request-context` header no longer makes a tool that already did its work return an error; the audit line is still written, with empty caller fields.
- Trust `high_risk` now tracks the condition keys guarding each principal (`principal_conditions_lost`), flags new unconditioned `Federated` principals (`unguarded_federated_principals_added`) and removed trust `Deny` statements (`deny_statements_removed`).
- Policy-body diffs render `NotAction` / `NotResource` explicitly (`NOT[...]`) and report `denies_added` / `denies_removed`; a removed `Deny` is direction `up`, an added one `down`.
- A grant that gains a condition is reported in `grants_conditioned` (direction `down`), and one that loses a condition in `grants_unconditioned` (`up`), instead of as a grant removed plus a grant added (`mixed`).
- Drift prompt: one authoritative recommendation rule, and the run must end with the full report even after updating an existing artifact.
- `coverage.denied_calls` carries the AWS error code only; full error text goes to the function log.
- Refused calls (account not allowlisted) and unexpected errors now write an audit line.
- The function logs to its own log group `/iam-drift-diff/<stage>` with `LogRetentionDays` (default 365). New output `FunctionLogGroupName`. The old `/aws/lambda/iam-drift-diff-mcp-<stage>` group is no longer written and can be deleted after review.
- Tests: execution-role scope assertion on `template.yaml`; account gate refuses in every tool.
- Deploy docs and `samconfig.toml` now pass `CAPABILITY_NAMED_IAM` (required because the invoke role has a fixed name).
- README: new "Maintenance and dependency updates" section (what is pinned where, how to regenerate the hash lock, suggested update cadence).
- Lambda Web Adapter layer 24 (adapter 0.9.0) to 30 (adapter 1.1.0). `AWS_LWA_READINESS_CHECK_MIN_UNHEALTHY_STATUS` (removed in 1.0) replaced by `AWS_LWA_READINESS_CHECK_HEALTHY_STATUS: 100-499`, the equivalent.
- `dnspython` 2.9.1 to 2.9.2 in the layer lock (CVE-2026-128089 / GHSA-vvf4-9x63-8xvv, zone-file WKS parsing; not reachable from this server). Only that pin changed.
- CloudWatch alarms on function errors, throttles and duration over 240 s, with an optional `AlarmTopicArn` parameter for SNS notifications. README: new "Operations: alarms and incident response" section (what each alarm means, kill switch, misuse investigation, how to report a security issue).

## [1.0.0] - 2026-11-02
### Pre-release hardening (security)
- Snapshot ids must be real, non-future UTC capture times. Foreign or forged keys in the bucket are ignored, ids passed to tools are validated before they reach S3, and each stored snapshot carries and checks its own id.
- Bucket policy now denies object writes and deletes to every principal except the server's execution role.
- KMS key policy now denies data-key use except through S3 in the owning account.
- Default `iam_snapshot_diff` compares against the snapshot the last recorded report used and returns `intervening_snapshots`, so a capture made right after an IAM change cannot hide it. Only `record_baseline: true` (the scheduled run) moves the baseline, so ad-hoc diffs have no side effects. Pruning never deletes the recorded pair.
- Captures inside `MinCaptureIntervalSeconds` (default 300) return the latest snapshot with `throttled: true` and write nothing. `SnapshotRetain` minimum is 4.
- Invoke role's `lambda:InvokeFunction` is limited to Function URL calls (`RestrictInvokeToFunctionUrl`, default `true`).
- One structured audit log line per tool call (tool, request id, caller, snapshot ids; no policy content).
- `iam_snapshot_list` limit is clamped to 1..50.
- Dependencies hash-locked: `layers/dependencies/requirements.txt` pins every transitive package with SHA-256 hashes (versions unchanged), and the layer build uses `--require-hashes`.
- S3 server access logging for the snapshot bucket, delivered to a dedicated SSE-S3, versioned, TLS-only access-log bucket with 90-day expiry.
### Pre-release changes
- `tools/sigv4_client.py` works with the stateless server and accepts explicit ids for `diff`.
- README: new "Security model" section with accepted risks and teardown steps.
### Added
- Initial release of the `iam-drift-diff` MCP server for AWS DevOps Agent.
- Four read-only tools: `iam_snapshot_capture`, `iam_snapshot_diff`, `iam_snapshot_list`, `iam_snapshot_get_entity`.
- Exhaustive paginated capture of `GetAccountAuthorizationDetails`, normalized into order-independent fingerprints.
- Exact set-difference with per-principal detail: added/removed principals, attached and inline policy changes with exact grants added/removed, trust-policy changes with a `high_risk` flag, and a neutral direction hint.
- Machine-readable completeness flags (`coverage.complete`, `comparison_complete`) so an incomplete capture can never be reported as "no drift".
- SAM template: Lambda (Web Adapter) with an `AWS_IAM` Function URL, a private KMS-encrypted versioned S3 snapshot bucket, and a SigV4 invoke role trusted only by the DevOps Agent service principal.
- Stateless Streamable HTTP so it runs correctly behind Lambda.
- Unit tests for the diff engine.
