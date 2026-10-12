# GuardDuty Inventory & Usage Metric Collection

Reference for the read-only APIs used to inventory detectors and protection plans
(Step 2) and the per-plan usage/cost signals used to size opportunities (Step 3). Load
this when you need the precise API names, dimensions, and which signal to prefer.

All calls are read-only (`List*`, `Get*`, `Describe*`) plus CloudWatch reads.

## Step 2 — Inventory detectors and protection plans

```
guardduty.ListDetectors / GetDetector             # detector status, enabled features,
                                                   # data sources, per-plan config
guardduty.ListMembers / GetMemberDetectors        # org member coverage (deleg. admin)
guardduty.GetMasterAccount / ListOrganizationAdminAccounts
guardduty.GetFindingsStatistics                   # finding counts by type/severity
                                                   # (value signal — statistics only,
                                                   # not finding detail content)
```

**Capture per Region:** whether GuardDuty is enabled, which protection plans/features
are on, Runtime Monitoring agent coverage, and member-account coverage.

Delegated-administrator accounts additionally receive **aggregated** organization
usage metrics — use them for org-wide sizing.

## Step 3 — Collect per-plan usage metrics

Pull the `AWS/GuardDuty` usage metrics with `cloudwatch.GetMetricData`, using the
`DataSource` dimension (and `AccountId`) to break usage down by protection plan over
the analysis window. Also pull `AWS/GuardDuty/MalwareProtection` for S3 malware scans.

- Usage metrics are published **hourly** and can lag up to ~24 hours — use a
  multi-day window, not a single hour, for sizing.
- On a delegated-administrator account, the aggregated `DataSource` dimensions give
  org-wide totals per plan.
- **Cost Explorer** (`ce.GetCostAndUsage`, filtered to the `AmazonGuardDuty` service,
  grouped by `USAGE_TYPE` and/or `REGION`) is the most direct dollar signal — prefer
  it when available and reconcile it against the per-plan usage metrics.

Convert byte metrics to GB/TB when sizing (see billing-model.md unit conversions) to
match pricing units.
