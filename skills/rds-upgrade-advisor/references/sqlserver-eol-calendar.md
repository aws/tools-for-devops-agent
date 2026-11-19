# Microsoft SQL Server (RDS) Support-Date Calendar

Authoritative support dates, cross-referenced from AWS documentation
(verified 2026-10-06). SQL Server is RDS-only (no Aurora). SQL Server does NOT
use RDS Extended Support; RDS maintains a major version until Microsoft's
Extended End of Support (EOS) date, which is the migration deadline. After EOS,
remaining instances are scheduled for automatic migration to a newer version.

Version-major parsing: RDS reports SQL Server `EngineVersion` as an internal
build number keyed by year-based major:
- `13.x` -> SQL Server **2016**
- `14.x` -> SQL Server **2017**
- `15.x` -> SQL Server **2019**
- `16.x` -> SQL Server **2022**
- `17.x` -> SQL Server **2025**
Engine identifiers: `sqlserver-ee` (Enterprise), `sqlserver-se` (Standard),
`sqlserver-ex` (Express), `sqlserver-web` (Web). Dates are the same across
editions; the edition affects licensing and upgrade-target availability, not EOS.

## RDS for SQL Server (by Microsoft major version)
Sources:
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/SQLServer.Concepts.General.VersionPolicy.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/SQLServer.Concepts.General.VersionSupport.html

| SQL Server major | RDS build major | Microsoft EOS = RDS end of support | Recommended target |
|------------------|-----------------|-------------------------------------|--------------------|
| 2014             | 13.x via upgrade| 2024-06-01 (RDS ended; deprecated)  | 2019               |
| 2016             | 13.x            | 2026-07-14                          | 2019 or 2022       |
| 2017             | 14.x            | 2027-10-12                          | 2022               |
| 2019             | 15.x            | 2030-01-08                          | 2022               |
| 2022             | 16.x            | 2033-01-11                          | 2025               |
| 2025             | 17.x            | 2036-01-06                          | (latest)           |

## Supported major upgrade paths
Source: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.SQLServer.Major.html

| Current | Supported upgrade targets |
|---------|----------------------------|
| 2016    | 2017, 2019, 2022, 2025     |
| 2017    | 2019, 2022, 2025           |
| 2019    | 2022, 2025                 |
| 2022    | 2025                       |

Confirm the exact valid target build with
`aws rds describe-db-engine-versions --engine sqlserver-se --engine-version <v>
--query "DBEngineVersions[*].ValidUpgradeTarget[*].EngineVersion"`.

## Notes
- No paid Extended Support tier — the Microsoft EOS date is the hard deadline.
- 2016 is the nearest cliff: creation of new 2016 instances is disabled as of
  2026-01-15; auto-migration to 2019 begins 2026-07-14.
- Edition cannot be changed during a major upgrade; Enterprise->Standard etc. is
  a separate migration.
