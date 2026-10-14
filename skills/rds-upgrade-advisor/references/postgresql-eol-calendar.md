# PostgreSQL / Aurora PostgreSQL Support-Date Calendar

Authoritative support dates, cross-referenced from AWS documentation
(verified 2026-10-06). RDS for PostgreSQL and Aurora PostgreSQL are tracked
separately; both derive end-of-standard-support from the PostgreSQL community
EOL (community supports a major for ~5 years), then offer up to 3 years of paid
RDS Extended Support.

Version-major parsing: PostgreSQL majors are a SINGLE integer from v10 onward
(10, 11, 12, 13, 14, 15, 16, 17, 18). Pre-10 used two-part majors (9.6). The
RDS `EngineVersion` is `<major>.<minor>` (e.g. `16.4` -> major `16`; `9.6.22`
-> major `9.6`). Aurora PostgreSQL `EngineVersion` is the same `<major>.<minor>`
shape from 13+ (e.g. `16.4`); legacy Aurora used an internal major (3=PG11,
4=PG12) but reports the community `major.minor` for 11.13+.

## RDS for PostgreSQL
Source: https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-release-calendar.html

| Major | Community EOL | RDS end of standard support | RDS end of Extended Support | Recommended target |
|-------|---------------|-----------------------------|-----------------------------|--------------------|
| 9.6   | 2021-11-11    | 2022-04-30 (deprecated)     | n/a                         | 14                 |
| 10    | 2022-11-10    | 2023-04-30 (deprecated)     | n/a                         | 14                 |
| 11    | 2023-11-09    | 2024-02-29                  | 2027-03-31                  | 15                 |
| 12    | 2024-11-14    | 2025-02-28                  | 2028-02-29                  | 16                 |
| 13    | 2025-11       | 2026-02-28                  | 2029-02-28                  | 16                 |
| 14    | 2026-11-12    | 2027-02-28                  | 2030-02-28                  | 16                 |
| 15    | 2027-11       | 2028-02-29                  | 2031-02-28                  | 16                 |
| 16    | 2028-11       | 2029-02-28                  | 2032-02-29                  | 17                 |
| 17    | 2029-11       | 2030-02-28                  | 2033-02-28                  | (latest)           |
| 18    | 2030-11       | 2031-02-28                  | 2034-02-28                  | (latest)           |

## Aurora PostgreSQL
Source: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/aurorapostgresql-release-calendar.html

Aurora end-of-standard-support dates track the community EOL and are close to —
but not always identical to — the RDS-for-PostgreSQL dates. Confirm the exact
Aurora date in the source when a database is near a boundary.

| Major (community) | Aurora end of standard support | Aurora end of Extended Support | Recommended target |
|-------------------|--------------------------------|--------------------------------|--------------------|
| 11                | 2024-02-29                     | 2027-03-31                     | 15                 |
| 12                | 2025-02-28                     | 2028-02-29                     | 16                 |
| 13                | 2026-02-28                     | 2029-02-28                     | 16                 |
| 14                | 2027-02-28                     | 2030-02-28                     | 16                 |
| 15                | 2028-02-29                     | 2031-02-28                     | 16                 |
| 16                | 2029-02-28                     | 2032-02-29                     | 17                 |
| 17                | 2030-02-28                     | 2033-02-28                     | (latest)           |

## Notes
- Extended Support is paid and begins the day after end of standard support;
  RDS auto-enrolls PostgreSQL instances past standard support unless disabled
  via `EngineLifecycleSupport`. Minimum minor for PG 11 Extended Support:
  RDS 11.22 / Aurora 11.9 or 11.21.
- Minor versions can reach end of standard support BEFORE their major (see the
  minor table in the source). This calendar tracks the MAJOR line; a database on
  an old minor of a still-supported major should still be flagged to patch.
- Dates with only month+year in the AWS source are approximate; this table uses
  the community-standard end-of-February cutover where AWS has not yet published
  an exact day. Re-verify against the source near a boundary.
- Treat end of standard support (not Extended Support) as the migration
  milestone for production systems.
