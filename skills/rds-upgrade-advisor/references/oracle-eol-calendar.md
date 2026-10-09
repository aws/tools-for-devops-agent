# Oracle Database (RDS) Support-Date Calendar

Authoritative support dates, cross-referenced from AWS documentation and Oracle
support lifecycle (verified 2026-10-06). Oracle is RDS-only (no Aurora). RDS for
Oracle does NOT use RDS Extended Support; instead RDS tracks Oracle's own
Premier/Extended Support lifecycle and performs mandatory ("forced") upgrades as
a version nears its end-of-support date.

Version-major parsing: RDS reports Oracle `EngineVersion` like
`19.0.0.0.ru-2024-01.rur-2024-01.r1`; the major is the leading release number
(`19`, `21`, `26`). Common majors: 19c (long-term support), 21c (innovation),
26ai (latest, Enterprise Edition only). Engine identifiers: `oracle-ee`
(Enterprise), `oracle-se2` (Standard Edition 2), plus BYOL/LI
(`oracle-ee-cdb`, `oracle-se2-cdb` for the CDB architecture).

## RDS for Oracle (by major release)
Sources:
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Overview.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Major.html

| Major | Oracle Premier Support end | Oracle Extended Support end | RDS end of support (approx) | Recommended target |
|-------|----------------------------|-----------------------------|-----------------------------|--------------------|
| 12.1  | ended                      | 2022-07-31                  | 2022-07-31 (deprecated)     | 19c                |
| 12.2  | ended                      | 2022-03-31                  | 2022-03-31 (deprecated)     | 19c                |
| 18c   | ended                      | n/a                         | deprecated                  | 19c                |
| 19c   | 2024-04-30                 | 2027-04-30                  | 2027-04-30                  | 19c (stay) / 21c   |
| 21c   | 2024-04-30 (innovation)    | n/a (no Extended)           | per RDS release notes       | 26ai               |
| 26ai  | per Oracle lifecycle       | per Oracle lifecycle        | (latest)                    | (latest)           |

Re-verify exact RDS dates in the "Support dates for major releases of RDS for
Oracle" section of the overview doc — RDS may extend beyond Oracle's dates.

## Supported major upgrade paths
Source: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Major.html

| Current               | Supported upgrade targets |
|-----------------------|----------------------------|
| 12.1.0.2              | 12.2.0.1, 19c              |
| 12.2.0.1              | 19c                        |
| 18c                   | 19c                        |
| 19c (CDB)             | 21c, 26ai                  |
| 21c (CDB)             | 26ai                       |

Confirm with `aws rds describe-db-engine-versions --engine oracle-ee
--engine-version <v> --query "DBEngineVersions[*].ValidUpgradeTarget[*].EngineVersion"`.

## Notes
- A major upgrade must target a Release Update (RU) released in the SAME month or
  later than the source RU. Major downgrades are not supported.
- 19c is the long-term-support release and the usual landing target.
- Option groups and licensing (BYOL vs License Included) matter on every Oracle
  upgrade — a target-version option group must be prepared first (see the
  strategy skill). 26ai is Enterprise Edition only.
