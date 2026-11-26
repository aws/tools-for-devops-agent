# MariaDB (RDS) Support-Date Calendar

Authoritative support dates, cross-referenced from AWS documentation
(verified 2026-10-06). MariaDB is RDS-only (there is no Aurora MariaDB).

RDS for MariaDB does NOT offer RDS Extended Support (unlike RDS MySQL and
RDS PostgreSQL). A major version is available at least until community end of
life; after RDS end of standard support, remaining instances are automatically
upgraded to a supported version. So for MariaDB, end of standard support IS the
hard migration deadline — there is no paid extension.

Version-major parsing: MariaDB majors are two-part (`10.5`, `10.6`, `10.11`,
`11.4`, `11.8`, `12.3`). The RDS `EngineVersion` is `<major>.<minor>` (e.g.
`10.6.14` -> major `10.6`). Note `10.11` sorts after `10.6` (minor 11 > 6).

## RDS for MariaDB
Source: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MariaDB.Concepts.VersionMgmt.html

| Major  | Community EOL | RDS end of standard support | Extended Support | Recommended target |
|--------|---------------|-----------------------------|------------------|--------------------|
| 10.3   | 2023-05-25    | 2023-05-25 (deprecated)     | none             | 10.11              |
| 10.4   | 2024-06-18    | 2024-06-18 (deprecated)     | none             | 10.11              |
| 10.5   | 2025-06-24    | 2026-08-31                  | none             | 10.11              |
| 10.6   | 2026-07-06    | 2026-12-31                  | none             | 11.4               |
| 10.11  | 2028-02-16    | 2028-02                     | none             | 11.4               |
| 11.4   | 2029-05       | 2029-05                     | none             | (latest LTS)       |
| 11.8   | 2028-06       | 2028-06                     | none             | 11.4 (LTS) / 12.3  |
| 12.3   | 2029-06       | 2029-06                     | none             | (latest)           |

## Notes
- No RDS Extended Support for MariaDB — after end of standard support, RDS force-
  upgrades remaining instances during a maintenance window. Plan ahead.
- 10.11 and 11.4 are long-term-support (LTS) community releases and are the
  usual upgrade targets.
- Dates with only month+year in the AWS source are approximate. Re-verify
  against the source near a boundary.
