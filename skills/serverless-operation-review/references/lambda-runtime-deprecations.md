# Lambda Runtime Deprecation Reference

Source: [Lambda runtimes — supported and deprecated](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)

**Verified against AWS documentation on 2026-09-10.** AWS states these forecast dates are "provided
for planning purposes and are subject to change." Re-check the source page before reporting a future
date as fact. If a runtime identifier is not in either table below, do not guess — report the runtime
as "deprecation date unverified" and link the source page.

## Severity model for runtime currency

Compare the function's `Runtime` identifier against the tables, then compare the deprecation date to
today.

| Condition | Severity | Rationale |
|---|---|---|
| Deprecation date is in the past | CRITICAL | AWS may no longer apply security patches, and the function is not eligible for technical support |
| Deprecation date within 180 days | HIGH | This is the point at which AWS begins notifying customers by email, Health Dashboard, and Trusted Advisor |
| Deprecation date within 365 days | MEDIUM | Plan the upgrade into a normal release cycle |
| Runtime is on Amazon Linux 2 (OS reached end of life 2026-06-30) but not yet past its own deprecation date | HIGH | Only critical and selected important AL2 security issues are patched; AWS recommends moving to an AL2023-based runtime "as soon as possible" |
| Runtime is a public preview runtime (`nodejs26.x`, `python3.15`) | HIGH | Preview runtimes are not covered by the Lambda SLA or technical support and must not be used for production workloads |
| Deprecation date more than 365 days out on a supported OS | INFO | No action |
| Container image (`PackageType: Image`) | INFO plus note | Deprecation notifications are not available for container-image functions; the customer owns rebuilding from the latest base image |

Also report, at MEDIUM, any function whose runtime is supported but whose **published versions**
still use a deprecated runtime — Trusted Advisor lists both `$LATEST` and published versions, and an
alias can still route traffic to an old version.

## Supported runtimes

| Name | Identifier | OS | Deprecation date | Block create | Block update |
|---|---|---|---|---|---|
| Node.js 26 (preview) | `nodejs26.x` | AL2023 | Not scheduled | Not scheduled | Not scheduled |
| Node.js 24 | `nodejs24.x` | AL2023 | Apr 30, 2028 | Jun 1, 2028 | Jul 1, 2028 |
| Node.js 22 | `nodejs22.x` | AL2023 | Apr 30, 2027 | Jun 1, 2027 | Jul 1, 2027 |
| Python 3.15 (preview) | `python3.15` | AL2023 | Not scheduled | Not scheduled | Not scheduled |
| Python 3.14 | `python3.14` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Python 3.13 | `python3.13` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Python 3.12 | `python3.12` | AL2023 | Oct 31, 2028 | Nov 30, 2028 | Jan 10, 2029 |
| Python 3.11 | `python3.11` | **AL2** | Jun 30, 2027 | Jul 31, 2027 | Aug 31, 2027 |
| Python 3.10 | `python3.10` | **AL2** | Oct 31, 2026 | Feb 1, 2027 | Mar 3, 2027 |
| Java 25 | `java25` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Java 21 | `java21` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Java 17 | `java17.al2023` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Java 11 | `java11.al2023` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Java 8 | `java8.al2023` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |
| Java 17 | `java17` | **AL2** | Jun 30, 2027 | Jul 31, 2027 | Aug 31, 2027 |
| Java 11 | `java11` | **AL2** | Jun 30, 2027 | Jul 31, 2027 | Aug 31, 2027 |
| Java 8 | `java8.al2` | **AL2** | Jun 30, 2027 | Jul 31, 2027 | Aug 31, 2027 |
| .NET 10 | `dotnet10` | AL2023 | Nov 14, 2028 | Dec 14, 2028 | Jan 15, 2029 |
| .NET 9 (container only) | `dotnet9` | AL2023 | Nov 10, 2026 | Not scheduled | Not scheduled |
| .NET 8 | `dotnet8` | AL2023 | Nov 10, 2026 | Feb 1, 2027 | Mar 3, 2027 |
| Ruby 4.0 | `ruby4.0` | AL2023 | Mar 31, 2029 | Apr 30, 2029 | May 31, 2029 |
| Ruby 3.4 | `ruby3.4` | AL2023 | Mar 31, 2028 | Apr 30, 2028 | May 31, 2028 |
| Ruby 3.3 | `ruby3.3` | AL2023 | Mar 31, 2027 | Apr 30, 2027 | May 31, 2027 |
| OS-only | `provided.al2023` | AL2023 | Jun 30, 2029 | Jul 31, 2029 | Aug 31, 2029 |

## Deprecated runtimes (end of support reached)

Any function on one of these is a **CRITICAL** finding.

| Name | Identifier | OS | Deprecation date | Block create | Block update |
|---|---|---|---|---|---|
| OS-only | `provided.al2` | AL2 | Jul 31, 2026 | Feb 1, 2027 | Mar 3, 2027 |
| Node.js 20 | `nodejs20.x` | AL2023 | Apr 30, 2026 | Feb 1, 2027 | Mar 3, 2027 |
| Ruby 3.2 | `ruby3.2` | AL2 | Mar 31, 2026 | Feb 1, 2027 | Mar 3, 2027 |
| Python 3.9 | `python3.9` | AL2 | Dec 15, 2025 | Feb 1, 2027 | Mar 3, 2027 |
| Node.js 18 | `nodejs18.x` | AL2 | Sep 1, 2025 | Feb 1, 2027 | Mar 3, 2027 |
| .NET 6 | `dotnet6` | AL2 | Dec 20, 2024 | Feb 1, 2027 | Mar 3, 2027 |
| Python 3.8 | `python3.8` | AL2 | Oct 14, 2024 | Feb 1, 2027 | Mar 3, 2027 |
| Node.js 16 | `nodejs16.x` | AL2 | Jun 12, 2024 | Feb 1, 2027 | Mar 3, 2027 |
| .NET 7 (container only) | `dotnet7` | AL2 | May 14, 2024 | N/A | N/A |
| Java 8 | `java8` | AL1 | Jan 8, 2024 | Feb 8, 2024 | Mar 3, 2027 |
| Go 1.x | `go1.x` | AL1 | Jan 8, 2024 | Feb 8, 2024 | Mar 3, 2027 |
| OS-only | `provided` | AL1 | Jan 8, 2024 | Feb 8, 2024 | Mar 3, 2027 |
| Ruby 2.7 | `ruby2.7` | AL2 | Dec 7, 2023 | Jan 9, 2024 | Mar 3, 2027 |
| Node.js 14 | `nodejs14.x` | AL2 | Dec 4, 2023 | Jan 9, 2024 | Mar 3, 2027 |
| Python 3.7 | `python3.7` | AL1 | Dec 4, 2023 | Jan 9, 2024 | Mar 3, 2027 |
| .NET Core 3.1 | `dotnetcore3.1` | AL2 | Apr 3, 2023 | Apr 3, 2023 | May 3, 2023 |
| Node.js 12 | `nodejs12.x` | AL2 | Mar 31, 2023 | Mar 31, 2023 | Apr 30, 2023 |
| Python 3.6 | `python3.6` | AL1 | Jul 18, 2022 | Jul 18, 2022 | Aug 29, 2022 |
| .NET 5 (container only) | `dotnet5.0` | AL2 | May 10, 2022 | N/A | N/A |
| .NET Core 2.1 | `dotnetcore2.1` | AL1 | Jan 5, 2022 | Jan 5, 2022 | Apr 13, 2022 |
| Node.js 10 | `nodejs10.x` | AL2 | Jul 30, 2021 | Jul 30, 2021 | Feb 14, 2022 |
| Ruby 2.5 | `ruby2.5` | AL1 | Jul 30, 2021 | Jul 30, 2021 | Mar 31, 2022 |
| Python 2.7 | `python2.7` | AL1 | Jul 15, 2021 | Jul 15, 2021 | May 30, 2022 |
| Node.js 8.10 | `nodejs8.10` | AL1 | Mar 6, 2020 | Feb 4, 2020 | Mar 6, 2020 |
| Node.js 4.3 | `nodejs4.3` | AL1 | Mar 5, 2020 | Feb 3, 2020 | Mar 5, 2020 |
| Node.js 4.3 edge | `nodejs4.3-edge` | AL1 | Mar 5, 2020 | Mar 31, 2019 | Apr 30, 2019 |
| Node.js 6.10 | `nodejs6.10` | AL1 | Aug 12, 2019 | Jul 12, 2019 | Aug 12, 2019 |
| .NET Core 1.0 | `dotnetcore1.0` | AL1 | Jun 27, 2019 | Jun 30, 2019 | Jul 30, 2019 |
| .NET Core 2.0 | `dotnetcore2.0` | AL1 | May 30, 2019 | Apr 30, 2019 | May 30, 2019 |
| Node.js 0.10 | `nodejs` | AL1 | Aug 30, 2016 | Sep 30, 2016 | Oct 31, 2016 |

## Upgrade target guidance

| Current family | Recommended target |
|---|---|
| `nodejs14.x` / `nodejs16.x` / `nodejs18.x` / `nodejs20.x` | `nodejs22.x` or `nodejs24.x` |
| `python3.7` – `python3.11` | `python3.13` (or `python3.12` for a smaller jump) |
| `java8` / `java8.al2` / `java11` / `java17` (AL2) | `java21` or `java25`; if the Java version cannot change, use `java8.al2023` / `java11.al2023` / `java17.al2023` to move to the AL2023 schedule |
| `dotnet6` / `dotnet7` / `dotnet8` | `dotnet10` |
| `ruby2.5` / `ruby2.7` / `ruby3.2` / `ruby3.3` | `ruby3.4` or `ruby4.0` |
| `go1.x` | `provided.al2023` with the custom runtime |
| `provided` / `provided.al2` | `provided.al2023` |

AWS notes that for Java 21 or Java 25 upgrades,
[AWS Transform custom](https://docs.aws.amazon.com/transform/latest/userguide/custom.html) can assist.

Always recommend testing on the new runtime before production rollout, and using function
[versions](https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html) and
[aliases](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html) for a safe
deployment with rollback — noting that rollback to a deprecated runtime may be blocked once the
block-function-update date passes.

## Architecture note for the Graviton check

AWS states: "All supported Lambda runtimes support both x86_64 and arm64 architectures." So any
function on a supported runtime with `Architectures: ["x86_64"]` is a candidate for `arm64`.

Caveats to state in the finding rather than assume away:

- `PackageType: Image` functions need the container image rebuilt for `arm64`.
- Functions with native binaries, compiled extensions, or architecture-specific layers need those
  rebuilt too. Check `Layers` before recommending.
- Test in a non-production environment first; recommend an alias with weighted routing for the
  cutover.

## Retrieving affected functions at scale

For an account-wide deprecated-runtime sweep, AWS documents a dedicated procedure:
[Retrieve data about Lambda functions that use a deprecated runtime](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-list-deprecated.html).
The [Trusted Advisor deprecated runtimes check](https://docs.aws.amazon.com/awssupport/latest/user/security-checks.html#aws-lambda-functions-deprecated-runtimes)
covers both `$LATEST` and published versions and is the better source when the account has many
functions.
