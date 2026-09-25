# DevOps Agent Cost Insights Skill

A skill that gives the AWS DevOps Agent the judgment to account for its own running cost. It shows the agent time each Agent Space consumed, the Support plan credits, and the downstream AWS API cost the agent generated while working, each figure gathered through read-only APIs that add nothing to your bill.

Attach it to an Agent Space and ask in chat, or pair it with the [cost dashboard custom agent](../../custom-agents/devops-agent-cost-dashboard/README.md) for a scheduled, charted report.

> **Figures are estimates, not billing data.** They are reconstructed from CloudWatch metrics, CloudTrail events, and query execution history, priced at published list rates. AWS Billing and AWS Cost Explorer remain the authoritative record of what you were charged. This output must not be used as the basis for invoicing, chargeback, or contractual commitments.

---

## Capabilities

| | What it tells you | Where the number comes from |
|---|---|---|
| **Direct usage** | Agent-seconds consumed by investigations, evaluations, on-demand chat, and release readiness reviews, priced per second | CloudWatch `AWS/AIDevOps` metrics, per Agent Space, per day |
| **Credits** | How much of that direct cost your Support plan already covers | Your plan's documented credit rate against last month's Support charge |
| **Downstream** | What the agent's own AWS API calls cost: Logs Insights scans, Athena queries, and other billable operations | Each service's query history, joined to CloudTrail for identity |
| **Tool usage** | Every tool the agent invoked, including Azure and third-party MCP tools that never appear on an AWS bill | The agent's journal records |

Questions it handles well:

- *What did this Agent Space cost over the last 7 days?*
- *Which Agent Spaces and roles account for most of our spend?*
- *Is any Agent Space scanning far more log data than its peers, so we can narrow its log groups?*
- *How does the agent's own runtime compare with the downstream AWS cost it generates?*
- *Which tools does the agent use most in this Agent Space?*
- *What did investigation `abc123` cost in downstream API calls and tool activity?*

The skill prescribes **how the numbers are calculated**, not how they look. In chat you receive a plain answer; through the custom agent you receive a fixed dashboard layout. Same method either way.

### Example output

A chat run produces a plain-language breakdown along these lines (figures illustrative):

```text
DevOps Agent cost · Agent Space "payments-prod" (us-east-1)
Period: 2026-09-01 to 2026-09-08

Direct usage (space-scoped)
  Investigations      3.20 hrs     $95.62
  Evaluations         0.80 hrs     $23.90
  On-demand (chat)    0.40 hrs     $11.95
  Direct cost (before credits)     $131.47

Credits
  Support plan: Enterprise Support (75%)     reference only
  Net direct cost: unavailable at this scope

Downstream (role-scoped)
  Logs Insights   12 queries · 3.10 GB      $0.02
  Athena           2 executions · 0.90 TB   $4.50
  GetMetricData    4 calls · metrics unknown  not priced (needs data events)
  Priced downstream total                    $4.52  (lower bound)

Tool usage (role-scoped)
  AWS 41 · Azure/3P 6 · Platform 18

Paid calls this run: 0
```

The custom agent renders the same figures as a charted dashboard plus a fixed summary.

---

## What running it costs

The skill adds **no prohibited paid operations** to your account. That is a narrow guarantee, not a claim that the report is free:

- **Agent runtime is billed.** A full run consumes a few minutes of agent time at the standard agent-second rate. Because usage metrics land after a publication delay, that time shows up in a *later* report's on-demand line, never the one it produced.
- **CloudWatch API requests are charged past the free tier.** The calls the skill does make — `GetMetricStatistics`, `DescribeQueries`, `ListMetrics` — count toward CloudWatch's API request allowance, which is free for the first million per month and charged beyond it. One run is well below that; a daily schedule across many Agent Spaces is worth checking.
- **CloudTrail data events, if you enable them,** add a recording charge for as long as they stay on. See step 2 below.

A weekly schedule keeps the run's own footprint small relative to the figures it reports.

---

## Inputs

The skill takes its inputs in two groups, and hardcodes none of them.

**Resolved at run time (you supply nothing).** The skill reads these from the installation it runs in and verifies each before any AWS data call:

| Value | Resolved from |
|---|---|
| Account ID | `list_associations` for the calling Agent Space |
| Agent Space ID | `get_agent_space` |
| Role ARN | `list_associations`, field `configuration.aws.assumableRoleArn` |
| Workload Region | the Agent Space's deployment Region |

**You supply.** Provide these in the request for a standalone chat run, or in the consuming agent's configuration for a scheduled run:

| Value | What to set it to | Where to find it |
|---|---|---|
| Reporting window | An explicit range or a named period such as "last 7 days" or "August". A consuming agent can default it. | Your choice |
| `SUPPORT_PLAN` | Your plan name, e.g. `Enterprise Support` | Billing console, Support plans |
| `PRIOR_MONTH_SUPPORT_CHARGE` | Last month's `AWS Support` charge, e.g. `4000` | Previous month's bill |

The two Support credit values are optional: omitting them shows direct cost with no credit offset. Even when supplied, credit subtraction applies only in an account-wide, full-calendar-month report; at a narrower scope the plan and rate show as reference and net cost reads `unavailable at this scope`.

---

## Getting started

You can run this skill three ways. Pick the entry point that fits how your team already works; the calculation method is identical.

- **Standalone (chat).** Attach the skill to an Agent Space and ask a cost question directly. You supply the reporting window and, optionally, `SUPPORT_PLAN` and `PRIOR_MONTH_SUPPORT_CHARGE` in the request itself (see *Inputs*).
- **Scheduled (custom agent).** Pair the skill with the included [cost dashboard custom agent](../../custom-agents/devops-agent-cost-dashboard/README.md), which pins one role, fixes a trailing window, runs silently, and produces the same charted dashboard on each run or on a schedule. You supply the inputs once in the agent's Config table instead of per request.
- **From an agent you already use.** A DevOps agent that supports skills can call this one by name. Install the skill, then reference it from that agent's instructions the way the cost dashboard agent does.

Whichever entry point you pick, the one-time setup below is the same. Work through the numbered steps in order once, then use the skill through your chosen path.

**1. Grant the agent's role read access** to CloudWatch metrics (`GetMetricStatistics`, `ListMetrics`), CloudWatch Logs query history (`DescribeQueries`), Athena query history (`ListWorkGroups`, `ListQueryExecutions`, `BatchGetQueryExecution`), CloudTrail event lookup (`LookupEvents`), and the AWS Pricing API (`DescribeServices`, `GetAttributeValues`, `GetProducts`).

All three Pricing API actions are required, not just `GetProducts`. The skill ships no table of price dimensions: it derives each one at run time by listing services, then listing the candidate `operation` and `usagetype` values for the matching service, and only then fetching the product. Granting `GetProducts` alone still leaves downstream categories reported as *not priced: rate unavailable*, because the skill cannot derive the price dimension without `DescribeServices` and `GetAttributeValues`.

**2. Enable CloudTrail data events for CloudWatch and X-Ray.** The Athena identity join reads `StartQueryExecution`, a management event that CloudTrail records by default within its 90-day Event History. `GetMetricData` (CloudWatch) and `BatchGetTraces` (X-Ray) are different: they reach CloudTrail only as data events, which are off by default. Enable data events for these services so CloudTrail captures that activity and the report can attribute and corroborate it for the configured role. Data events add a recording charge, so scope the selectors to the resources you measure and keep the reporting window inside the retention you configure.

**3. Add the skill.** It is a single `SKILL.md` with no reference files, so any install path works: paste it into the skill form, import the directory through the GitHub integration (which re-syncs with one click), or upload a zip containing `SKILL.md` alone. Exclude `evals/` from any zip — it is far over the 100-file and 6 MB limits.

```bash
cd devops-agent-cost-insights
zip ../devops-agent-cost-insights.zip SKILL.md
```

**4. Supply your Support plan.** Support credits have no Pricing API entry, so the skill applies the published tier percentages rather than resolving a rate on the run: Unified Operations 100%, Enterprise Support 75%, Business Support+ 30% of the prior month's `AWS Support` charge. Provide `SUPPORT_PLAN` and last month's `AWS Support` charge (`PRIOR_MONTH_SUPPORT_CHARGE`) if you want the credit computed; the skill derives the rate from the plan. Put them in the consuming agent's configuration for scheduled runs, or in the request itself for a one-off. Omitting them is valid, and the report then shows direct cost with no credit offset.

**5. Confirm it works.** Ask a cost question in chat ("What did this Agent Space cost over the last 7 days?") to confirm the skill triggers, or run the [custom agent](../../custom-agents/devops-agent-cost-dashboard/README.md) for a scheduled dashboard.

If any of the three Pricing API actions is denied, the skill still runs. It reports measured quantities for each downstream category and marks the dollar figure *not priced: rate unavailable*, whichever of the three actions is missing: a denied `DescribeServices` or `GetAttributeValues` stops price-dimension derivation before a rate is ever requested, and a denied `GetProducts` stops the rate lookup itself. Grant all three if you want priced downstream lines.

---

## How the usage and cost are calculated

The skill follows a fixed sequence, and each step depends on the one before it.

**One window, fixed once.** The reporting period is pinned at the start and reused for every source. Query history APIs return everything they have regardless of date, and that set grows with every run, so the skill filters each result to the same `[START, END)` window itself.

**Direct usage from CloudWatch, one metric at a time.** The activity metrics are discovered rather than assumed: `ListMetrics` enumerates the `AWS/AIDevOps` namespace, and every metric matching `Consumed*Time` is read with `GetMetricStatistics`, scoped to the Agent Space, at daily resolution. Each one gets a term in the sum and appears in the report, including any this skill did not anticipate, so a metric AWS adds later is picked up without a change here.

**Credits only where they apply.** Support credits are account-level and monthly: a percentage of the account's AWS Support charge (Unified Operations 100%, Enterprise Support 75%, Business Support+ 30%), issued by the 10th of the month and expiring at month-end. The plan, rate, and prior-month charge are deployment values you supply in the consuming agent's configuration or in the request itself; the skill ships none and infers none. It subtracts credits only when the report is account-wide, covers exactly one calendar month, the Step 0 reconciliation found no retired spaces inside the window, and the plan and prior-month charge are known and current. For a single space, a single role, a partial month, or a rolling window, it reports direct cost *before* credits and marks net cost *unavailable at this scope*, because allocating an account-wide credit to one space would understate that space's real cost.

**Downstream from the authoritative source.** Logs Insights history (`DescribeQueries`) is the sole authority for query count, identity, bytes scanned, and cost; it is paginated to exhaustion.

Each page is filtered to the role and the window before its bytes are summed, so nothing outside the reporting period reaches the total — the place an earlier version lost queries and drifted between runs.

Athena history supplies exact bytes, joined to CloudTrail `StartQueryExecution` events to learn *who* ran each query, since Athena history alone doesn't say. Journal records inventory every tool call and cross-check the counts. Where sources disagree, the report says so plainly rather than averaging or picking the higher figure.

**Validation before reporting.** A self-check re-sums every total, confirms the window was reused, confirms every included record matched both the window and the role, confirms pagination finished, and confirms nothing was estimated. A figure that fails a check is fixed or marked unavailable.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Direct usage is zero for a period you know was busy | Metrics arrive after a publication delay | Re-run after the delay, or widen the window by a day |
| A downstream category says *unavailable* | The source API errored, or access is denied | Check the agent role's read permissions for that service |
| Logs Insights cost is *not priced: rate unavailable* | `pricing:GetProducts` denied or throttled | Grant the permission |

---

## Next step

For a scheduled, charted dashboard scoped to one role with a fixed output format, see the [cost dashboard custom agent](../../custom-agents/devops-agent-cost-dashboard/README.md). It uses this skill for every calculation and adds configuration verification and a consistent report layout on top.

---

## Setting a guardrail threshold

A budget cap is only as good as the number behind it. The [investigation cost guardrail skill](../investigation-cost-guardrail/README.md) estimates and caps investigation cost before the agent runs, but it needs a threshold to enforce. This skill supplies it: by showing what investigations and downstream calls have actually cost per Agent Space, you set that budget from observed spend and tighten it as usage changes.

## Known Limitations

- **Cross-account associations are not covered yet:** the skill attributes cost within the account it runs in. When a DevOps Agent role is associated across accounts, the cost of that cross-account association is not attributed or priced yet.
- **Direct cost cannot be split per investigation:** the daily Agent Space metric is shared by what ran that day, so a single investigation gets its attributable downstream and tool activity, but direct cost only when billed seconds exist for that execution.
- **Credits apply only at account-wide, full-calendar-month scope:** support credits are account-level and monthly, so a single-space, single-role, partial-month, or rolling report shows direct cost before credits and marks net cost unavailable at that scope. Credits are not prorated, so use the gross direct cost line for trend comparison.
- **A paid operation cannot be priced without a successful rate lookup:** there is no fallback rate, so a denied or missing `pricing:GetProducts` leaves that category reported as "not priced: rate unavailable", with the measured quantity still shown.
- **Some operations depend on CloudTrail data events:** `GetMetricData` (CloudWatch) and `BatchGetTraces` (X-Ray) reach CloudTrail only as data events, which are off by default and add a recording charge once enabled. With them on, the data event supplies both the call count and the billable quantity, so both can be priced. Without them, CloudTrail cannot see those calls and the skill relies on journal records for the counts, reported as unavailable rather than zero when neither source is present. The Athena identity join is different: `StartQueryExecution` is a management event CloudTrail records by default within its 90-day Event History, so keep the reporting window inside 90 days, grant `cloudtrail:LookupEvents`, and confirm no tool policy blocks it.
- **CloudTrail Event History is a lower bound:** Event History is not exhaustive and its role attribution needs parsing and verification. The skill uses it for identity joins and cross-checks, not as the count of record.
- **Query history has a horizon:** `describe_queries` returns the most recent queries first and does not reach back indefinitely. On a busy account, the older end of a long window can fall outside what it returns. The skill compares the oldest returned `createTime` to the window start and, when history does not reach that start, reports the count as a lower bound with the earliest date covered. Running on a weekly or biweekly cadence keeps each window inside available history.
- **Publication delay:** usage metrics and CloudTrail events are not instant. Very recent activity may be undercounted, and the run's own agent time lands in a later period.
- **Athena capacity reservations are priced as if they were per-byte:** a query running under a capacity reservation incurs no per-scan charge, but the skill does not detect reservations and prices every attributed execution from its scanned bytes. On a workgroup using reserved capacity the Athena line is therefore an overstatement. Compare against Cost Explorer before relying on it.
- **A separately-charged activity is usually reported without dollars:** if a discovered metric bills on its own charge rather than the agent-second rate, the skill resolves that charge and keeps it as its own line. Release-readiness review is the case to watch, and no separate DevOps Agent charge has been confirmed to exist in the price list, so the expected result today is hours reported with cost *unavailable*, which makes direct cost a labeled lower bound rather than a wrong number.
- **The agent-second rate is resolved, not stored:** the skill reads it from the price list if DevOps Agent appears there, otherwise from the published [pricing page](https://aws.amazon.com/devops-agent/pricing/), where it is verified against a worked example's own arithmetic. Every report names the rate and where it came from. If neither source resolves, direct cost is reported *unavailable* rather than computed from a remembered figure — so a run with no access to either produces agent-seconds without dollars.
- **Support credit percentages come from published pricing:** the tier percentages are published on the DevOps Agent pricing page and applied from the Step 2 tier table, not resolved by API. You still supply your plan and prior-month Support charge. Confirm the applied credit against your bill before relying on a report for anything financial.
