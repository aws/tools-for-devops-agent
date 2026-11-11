# Changelog

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
