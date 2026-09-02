# Changelog

All notable changes to this skill are documented here. New entries go at the top.

## [1.0.0] - 2026-09-01

Initial release for AWS DevOps Agent.

### Review scope
- Read-only SLA-readiness and availability review of Amazon FSx for Windows File
  Server file systems across seven dimensions: deployment type (Single-AZ vs
  Multi-AZ), Active Directory health, throughput capacity sizing, storage capacity
  headroom, backups, maintenance window, and CloudWatch alarm coverage.
- **SLA Readiness rating** (High / Medium / Low / Indeterminate) with per-dimension
  findings and remediation, grounded in AWS documentation thresholds (the 20%
  free-storage guidance, the read + 2 × write throughput sizing formula, the Multi-AZ
  recommendation from Security Hub control FSx.5, and the Misconfigured / Active
  Directory reachability model). Rating precedence: any Critical → Low; else any
  Warning or unverifiable dimension → Medium; else High.
- Automatic single-file-system vs multi-file-system (fleet) routing by input count,
  including batched review with manifest tracking and resume for 21+ file systems.

### Active Directory / Misconfigured handling
- `MISCONFIGURED` lifecycle is a 🔴 Critical availability finding (AD unreachable).
- Targeted AD root-cause matching: the finding matches the reported failure detail
  against known lifecycle codes and quotes a specific fix —
  `ACTIVE_DIRECTORY_INVALID_CREDENTIALS` (rotated/expired service-account password,
  plus the Protected Users / NTLM caveat),
  `ACTIVE_DIRECTORY_INSUFFICIENT_PERMISSIONS` (OU delegation), and
  `ACTIVE_DIRECTORY_COMP_ACC_REUSE_BLOCKED_BY_POLICY` (KB5020276 netjoin hardening →
  "Allow computer account re-use" GPO).
- `MISCONFIGURED_UNAVAILABLE` (quarantined) recognized as the most severe AD state —
  data currently inaccessible after prolonged AD failure.
- Names the read-only `AWSSupport-ValidateFSxWindowsADConfig` runbook as a follow-up
  diagnostic (never executes it).

### Trend / usage-pattern analysis
- Usage-pattern (trend) analysis on the throughput and storage dimensions, built on
  daily-aggregate CloudWatch metrics (`Period=86400`) over a configurable lookback
  (default 30 days; 14 / 21 / 30 / 60 accepted).
- **Peak-aware throughput sizing:** evaluates provisioned capacity against measured
  **peak** demand (read + 2 × write at the daily peak), not just the window average,
  catching weekday-morning throttling that an average hides. Peak figures are labeled
  approximate (derived from daily `Maximum`).
- **Weekday/weekend usage profile** classification, used as evidence for the
  throughput cost note.
- **Storage growth projection** to the 20%-full floor; a projection of ≤ 4 weeks is
  surfaced as at least a Warning even when current free % is healthy.
- New file systems (< ~14 days of history) report `insufficient-data` and skip
  projections rather than extrapolating.

### Cost optimization (advisory; never lowers the SLA rating)
- Heavily over-provisioned throughput or storage flagged as 💰 right-sizing
  opportunities.
- **Idle-file-system** signal (near-zero data I/O and operations across the window) —
  the strongest cost signal, surfaced first as a decommission candidate; supersedes
  the over-provisioned-throughput note.
- Throughput cost note carries a caveat when the recommended tier is at or below
  32 MBps: FSx emits throughput-utilization metrics only at ≥ 32 MBps, so the 8/16
  MBps tiers cannot be validated from CloudWatch and require customer-side observation.

### Availability nuances
- **Multi-AZ client-side failover caveat:** Linux/macOS clients and DNS-caching
  runtimes (.NET on Linux, Lambda) do not auto-fail-over like Windows SMB clients;
  third-party DNS (e.g. Infoblox) needs two A records (one per file-system IP); a
  throughput-capacity update is a safe way to test failover.
- **Single-AZ maintenance wording** is honest that the AWS "typically under ~20
  minutes" figure is best-effort, not a guarantee; the whole window is treated as
  potentially unavailable.
- **Storage-optimization sequencing:** a storage increase triggers a background
  optimization phase that can pin `FileServerDiskThroughputUtilization` near 100%, so
  throughput should be raised before storage (notes the 4-modifications-per-24h
  limit); an in-progress `STORAGE_OPTIMIZATION` action is surfaced as an ℹ️ info note
  so elevated throughput metrics are read as transient.

### Safety & operations
- Self-contained data collection via read-only control-plane API calls and CloudWatch
  metric reads (`use_aws`); no AWS profile or credentials requested from the user. The
  skill never reads file/share data over SMB and never performs a write, update,
  create, or delete.
- Fully covered by the `AIDevOpsAgentAccessPolicy` managed policy — no additional IAM.
- Pre-flight permissions/tooling handling reports unverifiable checks instead of
  inferring configuration, capping the rating at Medium.
- Deployment-type remediation correctly states Single-AZ cannot be converted to
  Multi-AZ in place (create-new-and-migrate).
- Final Delivery Contract: the report is emitted as a persisted artifact (when the
  runtime supports it) and returned verbatim, preventing the host agent from
  summarizing or reformatting it.
- README documents out-of-scope FSx for Windows support themes (shadow copies/VSS, SMB
  over WAN, file-search indexing, NTFS/SYSTEM ACLs, GPOs not applying to FSx nodes,
  anti-malware) so the skill does not over-promise.

### Notes
- The frontmatter `description` is 965 characters, within the AWS DevOps Agent upload
  validator's 1024-character limit.
