---
name: devops-agent-cost-insights
description: Report what the AWS DevOps Agent itself costs to run, and where that cost comes from, per Agent Space and per role on demand in chat or on a schedule through a custom agent. Use this skill when a user asks to measure, break down, attribute, explain, or forecast DevOps Agent spend, or the cost of the downstream AWS API calls. Covers direct agent time by activity, Support plan credit offset, downstream API cost, and tool usage.
metadata:
  author: tqquresh, inesttia
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Scheduled tasks"
  aws-devops-agent-skills.aws-services: "CloudWatch, CloudTrail, AIDevOps"
  aws-devops-agent-skills.technical-domains: "Cost Optimization, Operations"
---

## Overview

This skill provides the **methodology** for gathering and calculating AWS DevOps Agent cost data. It intentionally does NOT prescribe a fixed output format. The consuming agent (chat, custom agent, etc.) decides its own presentation (plain text, multi-space tables, single-space visual dashboard with charts, etc.) based on its own prompt/output spec. Follow the steps below to gather and compute correct numbers; format them however the calling context requires.

### Execution visibility

The consuming agent's output contract controls visibility. When it requires silent, final-only execution:

- Perform skill/reference reads, planning, tool calls, pagination, distillation, calculations, retries, and Step 7 validation without assistant-authored progress messages.
- Keep checklist state, intermediate values, query IDs, raw records, arithmetic, and rejected records internal.
- Do not announce file reads or tool calls, react to results, or narrate what happens next.
- Return only the consuming agent's single final response after its artifact operation. A compact validation result table is allowed only when its final template explicitly requires one.

> **This skill must add exactly $0.00 to the bill.** Never `StartQuery`, `StartQueryExecution`, or `GetMetricData` — and never any other operation the **zero-cost rule** names below. Each is a paid API, so issuing one bills the account this report is about. If a figure is only reachable through a paid call, it is unavailable; say so. This is the **zero-cost rule**, restated at Step 1 and attested in Step 7.
>
> **"Read-only" is not the safety test.** `GetMetricData` reads only your own metrics and is billed per metric anyway. Before using any call not already named in the steps below, classify it per *Operation classification* in Step 3; an operation you cannot confirm as free is unclassified, not free.

Four things to cover every time:
1. **Discovery**: enumerate Agent Space(s) and DevOps Agent role(s) in scope (may be one space or all spaces in the account, depending on what's requested)
2. **Direct usage**: agent-seconds billed (investigations, evaluations, chat), per space
3. **Downstream**: AWS API costs from agent-initiated calls (Logs Insights, Athena, X-Ray, CloudWatch), attributed via CloudTrail, traceable by query ID / query execution ID
4. **Grouping**: if multiple spaces/roles are in scope, group cost by Agent Space ID and by DevOps Agent Role ARN; if scoped to a single space/role, a single summary suffices

---

## Workflow Checklist

Work through this checklist in order and do not skip a step. The steps are dependent, not independent: Step 1 fixes the `<START>`/`<END>` window that Steps 3 and 7 must reuse, and Step 7 validates the figures produced by Steps 1 through 6. Track checklist completion internally. Do not print step-by-step progress or skipped-step narration; surface only trust-impacting omissions in the consuming agent's single final response.

- [ ] Step 0: Discover the Agent Space(s) and DevOps Agent role(s) in scope. Skip only if scope is already fixed to one space/role
- [ ] Step 1: Resolve the reporting window from the request, then compute direct usage (agent-seconds) via CloudWatch `GetMetricStatistics`
- [ ] Step 2: Apply Support plan credits to get net direct cost
- [ ] Step 3: Attribute downstream cost using journal for call counts (primary), history APIs for exact bytes, and CloudTrail for cross-check, reusing the exact Step 1 window
- [ ] Step 4: Group by Agent Space ID and by Role ARN. Skip if scope is a single space/role
- [ ] Step 5: Extract tool usage from journal records and cross-reference against CloudTrail
- [ ] Step 6: Produce a per-investigation breakdown, only when requested
- [ ] Step 7: Validate every computed figure before reporting it

### Scope precedence

The consuming agent defines the scope. When it supplies an explicit `ROLE_ARN` and declares exact-role scope, that scope overrides this skill's multi-role discovery and role-coverage guidance:

- Treat `ROLE_ARN` as the complete allowlist of one role. Skip role discovery and never add historical, rotated, inferred, or similarly named roles.
- Require exact account and role identity. For CloudTrail, `userIdentity.sessionContext.sessionIssuer.arn` must equal `ROLE_ARN`. For an STS assumed-role identity, normalize only an ARN with the same account and exact configured role name to `ROLE_ARN`.
- Discard every other role immediately. Do not count, analyze, name, summarize, or mention excluded roles.
- Never widen exact-role scope because direct Agent Space usage exists on days with no matching downstream activity.
- Label direct usage as Agent Space-scoped because the `AgentSpaceUUID` metric cannot isolate one role. Label downstream and tool usage as exact-role-scoped. Do not present the combined result as the complete Agent Space total.

The multi-role discovery guidance below applies only when the consuming agent requests Agent Space-wide or account-wide scope.

### Definitions

These named rules are defined once here and referenced by name throughout. "Per the quantity source rule", "passes the attribution test", "per the Logs source rule", and "match the active role scope" mean exactly what is written below; the step does not restate them.

- **Active role scope:** the identity a record must match to count (see *Scope precedence*): the single configured `ROLE_ARN` in exact-role mode, or one of the Step 0 discovered role ARNs in multi-role mode.
- **Attribution test:** a record counts only when it matches BOTH the reporting window AND the active role scope; one alone is not enough. In exact-role mode, discard non-matching roles without analysis or mention. Failing this test is a leading source of run-to-run drift.
- **Logs source rule:** for CloudWatch Logs Insights, `describe_queries` is the sole source of query count, role attribution, scan bytes, and cost. Never substitute a CloudTrail `StartQuery` lookup; journal data is a cross-check only. If `describe_queries` is unavailable, report Logs Insights unavailable rather than substituting another source.
- **Identity-not-Username rule:** attribute on the parsed `userIdentity` / `sessionIssuer.arn`, never on a CloudTrail `Username` filter. DevOps Agent roles in one account share a single CloudTrail session name, so a `Username` count aggregates across roles and overstates the target. See *Cross-check: CloudTrail* for the mechanics.
- **CloudTrail-lower-bound rule:** CloudTrail Event History does not reliably return every matching event, so a CloudTrail-derived count is a lower bound, never an exact total. This is why the journal is primary.
- **Quantity source rule:** the Pricing API supplies a rate, never a quantity. Which quantity an operation needs follows from the **unit class** of its price dimension, not its service. A **count-class** unit (`Requests`, `Metrics`, `traces`) prices from the attributed call count, which Step 3 produces for every operation, so any per-call price dimension can be priced, including one from a service named nowhere in this skill; where a service tiers its requests, name the tier or do not price. A **data-class** unit (`GB`, `TB`) needs a byte figure, so it prices only from the sources Step 3 names, never from a call count. When the quantity is missing, report the call count with no dollars: these are all **paid** operations, so a row without dollars is a measurement gap, never a free call, and makes the Priced Downstream Total a **lower bound**. A confirmed `0` calls is exactly `$0.00`, not a gap. Each is countable when the audited agent issued it, forbidden when this run would (see *Zero-cost rule*).
- **Zero-cost rule:** this run must cost $0.00: no `StartQuery`, no `StartQueryExecution`, no `GetMetricData`, no log scanning. Use only the confirmed-free calls named in these steps. If a step appears to need a billable call, it finishes without that figure and reports the gap. Defined in the Overview, restated at the point of temptation in Step 1, and attested in Step 7. The rule binds by effect, not by name, across three evasion paths:
  - **Wrappers and aliases count.** The prohibition is on the paid operation, whatever name reaches it. Do not issue the canonical operations (`StartQuery`, `StartQueryExecution`, `GetMetricData`, `BatchGetTraces`) or any wrapper or tool form of them, including `start_query`, `query_cloudwatch_logs`, `get_metric_data`. Do not call `GetQueryResults` either: it is free, but it is the second half of a `StartQuery` pair and `describe_queries` already returns `bytesScanned`. An operation not named here is classified per *Operation classification* in Step 3 before it is called, and is unclassified rather than free if it cannot be confirmed free.
  - **`shell` is not an escape hatch.** A paid operation invoked through `shell` (for example `aws logs start-query`, `aws cloudwatch get-metric-data`, or an equivalent CLI or script) bills the account exactly as the tool form would. Do not use `shell`, `use_aws`, or any command runner to issue a scan or paid read this rule forbids by name.
  - **Delegation inherits the rule.** A delegated agent or subagent acts on the audited account's behalf, so a scan it issues is billed the same. Carry this rule into any delegated request explicitly, and never delegate an action you could not issue directly. Journal access does not normally require delegation: `get_investigation_journal_records` and `get_other_agentspace_journal_records` are called directly. When those tools are blocked this run, the Context Gatherer subagent is the fallback (see Step 3), and this rule travels with the delegated request.

---

## Step 0: Discover Spaces and Roles (skip if scope is already fixed to one space/role)

What this step resolves depends on the scope the consuming agent asked for (see *Scope precedence* above): the single space this run is scoped to, or every space in the account. Nothing in it is inferred.

**Always — resolve the space this run is running in, and its role.** This is the whole purpose of the step when the consuming agent supplied no identifiers.

- `get_agent_space` for the current space returns its `name` and `agentSpaceId`.
- `list_associations` for that space returns its AWS configuration. Take the role from `configuration.aws.assumableRoleArn`, with `accountId` and `accountType` alongside it. Pair on this field and nothing else.

For a single-space request that is the whole step. Everything below applies **only** when the consuming agent requested Agent Space-wide or account-wide scope.

**Account-wide or Agent Space-wide scope — enumerate the remaining spaces.**

- `list_agent_spaces` returns every Agent Space in the account, each with `name`, `agentSpaceId`, and `createdAt`. This is the authoritative inventory of *live* spaces.
- Call `list_associations` for each one and read `configuration.aws.assumableRoleArn` the same way.

> **Never pair a role to a space by creation timestamp.** Role and space creation times are not correlated: a space's role may be created long after the space, while an unrelated role is created moments before it. Nearest-timestamp pairing therefore produces confident but wrong pairings, attributing one space's downstream cost to another space's role. `configuration.aws.assumableRoleArn` is the only pairing source.

### Reconcile live spaces against the spaces in the metrics (account-wide scope only)

`list_agent_spaces` returns spaces that exist now. CloudWatch retains `AgentSpaceUUID` dimension values for spaces that have since been deleted, so the metric namespace routinely carries many more space IDs than the account has spaces. Collect the `AgentSpaceUUID` values Step 1 will read and split them:

- **Live** — present in `list_agent_spaces`. Name and role are both known.
- **Retired** — present in the metrics only. The billed usage is real and must be counted, but the space cannot be named and has no association from which to resolve a role.

Report retired spaces as one `retired spaces` line with their count. Never fold them into a named space, and never drop them. An account-wide total that omits them is a **lower bound**; one that includes them is complete for direct usage only, because their downstream activity has no resolvable role. State which of the two you produced — Step 2's credit gate depends on it.

### Anomalies to report separately (account-wide or Agent Space-wide scope only)

- **Cross-account roles.** A trust policy names the account permitted to use the role in `aws:SourceAccount`. When that value is not the audited account, the role serves another account's space: exclude it from totals and report it as a cross-account anomaly. Read `aws:SourceAccount` for this and nothing else — see the warning below before reading `aws:SourceArn`.
- **Orphan roles.** An agent role that no live space's `assumableRoleArn` points at is residue from a deleted space. List these separately, and never pair one to a live space to make the counts reconcile. Apply this only to the agent role type below; the web app role is never an `assumableRoleArn`, so testing it this way reports every one of them as an orphan.

> **A trust policy does not pair a role to a space.** On the agent role, `aws:SourceArn` is normally the wildcard `agentspace/*` (no space ID); where a specific `agentspace/<id>` appears it is usually a web app role, which must never be paired. `aws:SourceArn` therefore fails on the role that matters and succeeds on the wrong one.

**Role types are not interchangeable, and names are not a discovery mechanism.** One space commonly has several roles with unrelated suffixes:

- `DevOpsAgentRole-AgentSpace-<suffix>` — assumed by the agent to reach your resources. Cost attribution uses this one only, and only when `configuration.aws.assumableRoleArn` names it.
- `DevOpsAgentRole-WebappAdmin-<suffix>` — enables the off-console web app. Never a cost-attribution role.

Paths vary (`role/...` and `role/service-role/...`), other patterns exist, and the suffixes of one space's roles do not match each other. Use names only to find orphans.

---

## Step 1: Direct Usage (CloudWatch GetMetricStatistics)

**The reporting window is an input, not a fixed period.** Take `<START>`/`<END>` from the request — an explicit range, a named period ("last 7 days", "August"), or the consuming agent's configured default. This skill prescribes no window of its own; a custom agent that wants a standing trailing window pins it in its own configuration and passes it in. Resolve it to absolute UTC timestamps once, here, then reuse those exact values everywhere downstream: Steps 3 and 7 depend on one window for the whole report, and a report that mixes windows describes no real period. Where scope affects credit eligibility (Step 2) or exactness labels (Step 7), those rules read the window resolved here.

Read metrics with `GetMetricStatistics`, never `GetMetricData` (**zero-cost rule**).

### Discover the activity metrics, do not assume them

**Enumerate the namespace first; never work from a fixed list of activity types.** Billable activities are whatever `AWS/AIDevOps` currently publishes; a hardcoded list silently drops any activity added later and understates the total with no error.

```python
use_aws(
    service_name="cloudwatch", operation_name="list_metrics",
    aws_account_id="<ACCOUNT_ID>", aws_region="<REGION>",
    parameters={"Namespace": "AWS/AIDevOps",
                "Dimensions": [{"Name": "AgentSpaceUUID", "Value": "<AGENT_SPACE_ID>"}]}
)
```

Paginate until no `NextToken` remains. From the result, take **every metric whose name matches `Consumed*Time`** as a billable agent-time metric, and give each one a term in the sum below. Treat consumed-*time* metrics as billable seconds; a `Consumed*Requests` or `*Count` metric is a volume measure, not agent-seconds, so never multiply it by the agent-second rate — report it separately if useful.

Report the metric names you found. If enumeration returns a name this skill has not seen before, include it, price it at the agent-second rate, and say that it was discovered rather than expected. If `list_metrics` is denied, fall back to reading the names known at authoring time — `ConsumedInvestigationTime`, `ConsumedEvaluationTime`, `ConsumedOnDemandTime` — and label direct cost a **lower bound**, because an unenumerated namespace cannot be shown to be complete.

### Primary: CloudWatch GetMetricStatistics

The `AWS/AIDevOps` namespace metrics are NOT OTel-enriched, so PromQL/Prometheus queries return empty for these. Read them with `get_metric_statistics`, one call per discovered metric per Agent Space in scope:

```python
use_aws(
    service_name="cloudwatch",
    operation_name="get_metric_statistics",
    aws_account_id="<ACCOUNT_ID>",
    aws_region="<REGION>",
    parameters={
        "Namespace": "AWS/AIDevOps",
        "MetricName": "<each Consumed*Time metric returned by list_metrics>",
        "Dimensions": [{"Name": "AgentSpaceUUID", "Value": "<AGENT_SPACE_ID>"}],
        "StartTime": "<START>",
        "EndTime": "<END>",
        "Period": 86400,
        "Statistics": ["Sum"]
    }
)
```

> **AgentSpaceUUID dimension is required.** Without it, you receive account-level aggregates that can't distinguish between spaces.

Use `Period: 86400` (daily) so `Datapoints` can be broken out per day if the consuming agent needs a time-series/trend view, not just a single aggregate.

### Calculate direct cost (per space):

**Resolve the agent-second rate on this run; never carry one in from memory.** Try these in order and stop at the first that yields a rate, then report which one did:

1. **The Pricing API**, per *Resolving rates*, if the price list exposes a DevOps Agent service code. Preferred, because it is authoritative and region-scoped. Such a service code has never been confirmed to exist, so an empty result here is the expected outcome rather than a fault — fall through.
2. **[AWS DevOps Agent pricing](https://aws.amazon.com/devops-agent/pricing/).** The rate is published as a per-agent-second figure inside the worked pricing examples rather than in a rate table, so read it from an example and **verify it against that example's own arithmetic**: each example states its seconds and its total, so the rate must reproduce the total. A rate that fails the example it came from was misread — discard it and try another example.

If neither yields a rate, **report direct cost as `unavailable`, naming the reason.** Do not substitute a remembered figure. Direct cost is the largest number in this report, so a stale rate misstates the entire report rather than one line. Report the agent-seconds from Step 1 either way — those are measured, exact, and independent of any rate.

State the resolved rate and its source wherever direct cost appears. Then sum over **every** metric discovered above, so no activity is silently dropped:
```
billable_seconds = Σ( Sum(m) for each Consumed*Time metric m discovered )
direct_cost      = billable_seconds × agent_second_rate
```
The sum is over the discovered set, not a fixed list of activities: one term per metric `list_metrics` returned, whatever they turn out to be. A metric the deployment does not emit contributes `0`. Report the metrics that made up the sum, and name any that this skill did not anticipate.

**If a discovered activity bills on its own charge rather than the agent-second rate**, price that metric's seconds separately by resolving its rate per *Resolving rates*, and keep it as its own line rather than folding it into `billable_seconds`. Release-readiness review is the case to check for: a separate DevOps Agent charge has never been confirmed to exist in the price list.

> **If a separate-charge lookup fails, report that activity's hours with cost `unavailable`** — not `$0.00`, and not at the agent-second rate. An empty or denied lookup for a DevOps Agent charge is the expected outcome rather than a fault, since none has been confirmed to exist. Guessing either way misstates the total. A separately-charged activity left unpriced makes direct cost a **lower bound**, so label it.

---

## Step 2: Credits

DevOps Agent usage is offset by credits equal to a percentage of the account's monthly AWS Support charge, applied toward usage at the agent-second rate. Credits are issued by the 10th of each month, apply to that month's charges, and expire at month-end without rolling over. These percentages are **published on the [DevOps Agent pricing page](https://aws.amazon.com/devops-agent/pricing/)**, so the table below reflects public pricing, not an operator assumption. They have no Pricing API entry, so never try to resolve them from the price list; and because that page is script-rendered, a live fetch is unreliable, so the values are stated here directly. Only the account's own tier applies:

| Support plan | Credit | `CREDIT_RATE_DECIMAL` |
|---|---|---|
| Unified Operations | 100% | `1.00` |
| Enterprise Support | 75% | `0.75` |
| Business Support+ | 30% | `0.30` |
| Business, Developer, Basic | none | — |

The plan and charge are **deployment values, not skill values.** This skill ships none of them, and nothing in it infers them from bill line items or credit size. Read them from the operator's configuration if supplied — `SUPPORT_PLAN` and `PRIOR_MONTH_SUPPORT_CHARGE` — and treat either that is absent as `unknown`. An unknown plan yields no credit, which is safer than a wrong one. The credit rate is not a separate input: derive it from `SUPPORT_PLAN` using the tier table above. Both supplied values come from the Billing console: *Support plans*, and the `AWS Support` line on the previous month's bill, which must be the month immediately before the reported month.

Then apply the **scope gate** before subtracting anything.

**Credit subtraction is gated by scope.** Produce a subtracted `Net Direct Cost` only in a full-calendar-month, account-wide report in which the Step 0 reconciliation found no retired spaces inside the window. A retired space's usage is billed but cannot be attributed to a named space or role, so a window containing one has an incomplete inventory by definition and this branch does not apply. Account-wide scope cannot be established without Step 0: when Step 0 was skipped because scope was already fixed to one space or role, this branch does not apply and there is nothing to evaluate — report `Net Direct Cost` as `unavailable at this scope`. Otherwise:

```
monthly_credits = support_charge × credit_rate
net_direct_cost = max(0, direct_cost − monthly_credits)
```

The base is the Support charge of the calendar month immediately preceding the report month (that is the most recent complete charge when credits are issued on the 10th). Use `credit_rate` as the decimal from the tier table (e.g. `0.75` for Enterprise Support), not the percentage; multiplying by `75` overstates the credit hundredfold.

**At a narrower scope, do not subtract.** For exact-role, single-space, partial-month, rolling, weekly, or per-investigation reports, show the plan, rate, and monthly credit as account-level reference only, and report `Net Direct Cost` as `unavailable at this scope`. Scope precedence treats exact-role single-space as the common path, so this branch is the default rather than the exception.

Guardrails:
- Compute `monthly_credits` only when `SUPPORT_PLAN` is a crediting tier and `PRIOR_MONTH_SUPPORT_CHARGE` is set. The charge is taken to be that of the calendar month immediately before the reported month; supply the current month's figure, since a stale charge carried over from an earlier run computes a wrong credit.
- If the Support plan is unset, the plan is `unknown` and the rate is `unavailable`. Show direct cost and prompt: *"Provide your monthly AWS Support charge to calculate your credit offset."*
- Floor `net_direct_cost` at zero, and never print `$0.00` for an unknown credit. The entitlement computed here is not the applied amount — confirm it against the credit on the bill before relying on a net figure.

---

## Step 3: Downstream Cost Attribution (with query-level traceability)

Source authority depends on the category. Work down this order, and stop at the first source that owns the figure:

1. **Service history APIs.** `describe_queries` is exclusive for Logs count, role, bytes, and cost (the **Logs source rule**); Athena history supplies exact bytes.
2. **Journal records.** Primary tool-call inventory and cross-check. Never a replacement for `describe_queries` Logs totals.
3. **CloudTrail.** Two different uses. The Athena identity join reads `StartQueryExecution`, a **management** event CloudTrail records by default — no data events needed. Separately, `GetMetricData` and the X-Ray operations appear only as **data events**, which are off by default; that is where their quantity comes from, since they have no service history API of their own. When the data event is present, read the exact billable quantity from its `requestParameters`: `MetricDataQueries` for `GetMetricData` (the per-metric count that `GMD-Metrics` bills, not the call count) and `TraceIds` for `BatchGetTraces`. When it is absent, the journal supplies only the call count and the cost is `unavailable`, since the per-item quantity is not in the journal.

Never start with CloudTrail (**CloudTrail-lower-bound rule**).

### Journal Records

Read journal records across the window with `get_investigation_journal_records` and `get_other_agentspace_journal_records`, plus `get_tool_calls` for tool-level detail. From each `utilization` / tool-call record extract the operation issued, the IAM role or session context that issued it, and the timestamp.

Build the per-role, per-operation **call counts** from this data first. For Logs Insights `StartQuery`, keep the journal count only as a cross-check per the **Logs source rule** — the reported Logs query count, attribution, bytes, and cost come from `describe_queries`.

- Keep a record only when it **passes the attribution test** (see Definitions).
- Count billable operations only. Classify each one per *Operation classification* below before counting; each operation's byte or quantity figure comes from the source named in the **quantity source rule** (see Definitions). Free and metadata calls are out of scope and get no row.
- Price each operation from its quantity source **per the quantity source rule** (see Definitions). Report a call count with no dollars only for a row whose source yields nothing.
- An operation **Operation classification** does not classify is **unclassified, not free.** Give it its own row with its count so it stays visible rather than silently costing nothing.
- `GetMetricData` is countable when the audited agent issued it; this run still may not issue it (**zero-cost rule**).

> **If journal access is unavailable this run, say so explicitly.** For Logs Insights the **Logs source rule** still holds — journal absence does not authorize a CloudTrail `StartQuery` lookup. For Athena and the data-event rows, fall back to the documented service history and CloudTrail paths. Never report zero as though the journal confirmed it. "No journal access" and "no calls made" are different findings.
>
> **If the direct journal tools are blocked this run, the Context Gatherer subagent is the fallback** for reading journal/utilization records during an investigation. Carry the **zero-cost rule** into the delegated request, and never delegate an action you could not issue directly. If neither the direct tools nor delegation return records, report journal access unavailable, not zero.

### Cross-check: CloudTrail

Use the native `lookup_cloudtrail_events` tool for operations with no service history API of their own, such as X-Ray, and to sanity-check journal counts elsewhere. The tool applies `jmespath_filter` to a root array of event summaries. Identity fields are not top-level JMESPath fields; the detailed event is serialized JSON in `CloudTrailEvent`.

For exact-role scope, use one event name per call and filter the serialized event by the complete ARN before it reaches the report:

```text
lookup_cloudtrail_events(
    attribute_key="EventName",
    attribute_value="<EVENT_NAME>",
    aws_account_id="<ACCOUNT_ID>",
    aws_region="<REGION>",
    start_time="<START>",
    end_time="<END>",
    exclude_event_names=[],
    jmespath_filter="[?contains(CloudTrailEvent, '<ROLE_ARN>')].{Time: EventTime, Event: CloudTrailEvent}"
)
```

For multi-role scope only, use `[].{Time: EventTime, Event: CloudTrailEvent}` and post-filter parsed events against the discovered role ARN set. Never use `events[?userIdentity...]`: `events` is not the JMESPath root and `userIdentity` exists only inside the serialized `CloudTrailEvent` value.

Parse every returned `Event` JSON string before using it. Then verify the parsed `userIdentity.sessionContext.sessionIssuer.arn` against the active role scope; the `contains` filter is an early reduction, not the final identity check. A valid no-match result is `events: []`. The result `events: null` means the JMESPath shape or tool response failed, not zero activity. Retry once with the exact filter shape above; if it remains null, mark CloudTrail unavailable and do not report a zero.

**Use CloudTrail selectively.** Not for Logs Insights `StartQuery` (**Logs source rule**), and never as the Athena scan-size source (Athena history stays authoritative for bytes). Athena history does not expose the initiating principal, so `StartQueryExecution` CloudTrail events are required to map the active role scope to `responseElements.queryExecutionId`; join those IDs to Athena history before retrieving scan bytes.

Attribution follows the **Identity-not-Username rule**. Filter on the role; `userAgent` only corroborates:

| Signal | Value | How to Filter |
|--------|-------|----------------|
| `userIdentity.sessionContext.sessionIssuer.arn` (primary, inside parsed `CloudTrailEvent`) | `arn:aws:iam::<ACCOUNT>:role/DevOpsAgentRole-AgentSpace-<suffix>` | Parse `Event`, then compare `sessionIssuer.arn` to the active role scope |
| `userIdentity.sessionContext.sessionIssuer.arn` (per-space role, inside parsed `CloudTrailEvent`) | `arn:aws:iam::<ACCOUNT>:role/service-role/DevOpsAgentRole-AgentSpace-<suffix>` | In exact-role mode require equality with `ROLE_ARN`; in multi-role mode compare to the discovered ARN set |
| `userAgent` (corroborating, NOT a LookupEvents filter) | `aidevops.amazonaws.com` | Post-filter only. `userAgent` is NOT a valid `AttributeKey` for `LookupEvents`, **and every agent role shares this value, so it cannot separate roles** |

> **When the journal and a cross-check disagree** for the same role and operation, report the **journal count** as primary and note the discrepancy plainly, e.g. `journal 12 · CloudTrail 10 (journal primary)`. Do not silently pick the higher or lower figure, and do not average them.

> **If `lookup_cloudtrail_events` is blocked or unavailable this run, delegate to the Context Gatherer subagent**. Ask for the exact events you need: one event name, the reporting window, filtered to the active role scope. Carry the **zero-cost rule** into the delegated request explicitly, the delegate must not scan a log group or issue any paid read to obtain them. A delegated result is still bound by the **CloudTrail-lower-bound rule** and the **Identity-not-Username rule**: parse each event and verify `sessionIssuer.arn` yourself. This never applies to Logs Insights `StartQuery`, the **Logs source rule** keeps `describe_queries` exclusive and a delegated `StartQuery` lookup is not a substitute. If the delegate cannot return the events without scanning, report CloudTrail unavailable, never a zero.

### Exact Bytes: Service History APIs

The journal carries counts but generally not scan sizes. Attach exact bytes from each service's own history API:

> **Post-filter every enumeration to the billing window yourself.** Both history APIs return whatever exists at call-time, and that set grows every run, so without your own filter each run reports a different "GB scanned" and nothing is reproducible. Neither API scopes it for you: `describe_queries` has no time-range parameter at all, so filter on `createTime`; for `list_query_executions` filter on `Status.SubmissionDateTime`. Drop anything outside the window even though the API returned it. Reuse the exact `<START>`/`<END>` fixed in Step 1 so the whole report describes one period.

- **CloudWatch Logs Insights — `describe_queries` only, per the Logs source rule.** One free, paginated call returns identity and exact scan statistics per query. Do not use `get_query_results` or a metric-based estimate:

| Field | Use |
|---|---|
| `bytesScanned` | **exact** bytes scanned. This is the billable quantity, no estimate required |
| `userIdentity` | ARN of the principal that ran the query. Attribute on this (Identity-not-Username rule) |
| `createTime` | filter to the billing window |
| `logGroupName` | what the query scanned |
| `queryId`, `status`, `queryDuration` | traceability |

Include a query only when it **passes the attribution test** (see Definitions).

> **Multi-role mode only:** Match every role the space used in the window, not just its current one. `DevOpsAgentRole-AgentSpace-*` roles may rotate, so Agent Space-wide reports can span several suffixes. This does not apply in exact-role mode; never discover or include another suffix when `ROLE_ARN` is fixed.

> **Pagination is mandatory, and the default page size will silently truncate you.** `describe_queries` returns the most *recent* queries first. Take page one only and you receive a handful of the newest, which are likely this dashboard's own, while the older, genuine agent activity is dropped and the total comes out far too low.
>
> Always pass **`maxResults: 1000`** explicitly, then keep calling with `nextToken` until the response has none. Never rely on the unstated default.
>
> **Then run the coverage check, on every run:** take the oldest `createTime` across *all* returned queries (not just the matching ones) and compare it to `<START>`.
> - Oldest returned is **at or before** `<START>` → history covers the window, the total is complete.
> - Oldest returned is **after** `<START>` → history does not reach the start of your window. Queries before that point exist but were not returned. Report the figure as a **lower bound**, state the earliest date covered, and do not present it as exact.
> - `nextToken` still present when you stopped → you did not finish paginating. That is a defect to fix, not a caveat to note.
>
> Its only parameters are `logGroupName`, `status`, `queryLanguage`, `maxResults`, and `nextToken`. There is no time filter, so the window is yours to apply after collecting everything.

- **Athena — join CloudTrail identity to service-history bytes.** Athena history contains execution IDs and statistics but does not identify the initiating IAM principal. Build the attributed execution set before pricing:
  1. Retrieve `StartQueryExecution` events with the `lookup_cloudtrail_events` contract above for the exact reporting window. In exact-role mode, use the `contains(CloudTrailEvent, '<ROLE_ARN>')` root-array filter, parse each returned `Event`, and require `sessionIssuer.arn == ROLE_ARN`. In multi-role mode, use the unfiltered root-array projection and compare parsed events against the discovered role ARN set.
  2. From each successful matching event, extract `responseElements.queryExecutionId`. A failed call with no execution ID remains visible in journal/tool counts but has no query scan to price.
  3. Enumerate executions with `list_query_executions` for every relevant workgroup, paginate fully, and intersect the returned IDs with the attributed CloudTrail execution-ID set. Never include an execution based only on its timestamp or workgroup.
  4. Call `batch_get_query_execution` for the joined IDs, in batches of at most 50, and read `Statistics.DataScannedInBytes`. Confirm `Status.SubmissionDateTime` still falls inside the same reporting window before including it.
  5. Reconcile the journal `StartQueryExecution` count against the number of attributed CloudTrail events and joined Athena executions. Report discrepancies explicitly with the journal count primary, but price only executions whose role-to-ID join succeeded.

Record each joined query execution ID for internal validation, then price each execution on its `DataScannedInBytes` at the resolved Athena rate. Athena applies a per-query minimum billable scan, so pricing raw scanned bytes underestimates cost for queries below that minimum. The minimum is a billing rule with no Pricing API entry: read it from Athena's pricing documentation and apply it per execution if a report needs that precision.

- **One total, no carve-outs.** Count only queries that **pass the attribution test** (see Definitions); report one figure per billable category: the call count and the summed cost. Do not subdivide it by log group, query text, or which run issued it, and do not annotate it.

> **Never scan a CloudTrail log group with Logs Insights for attribution.** Use `lookup_events` instead. This is an operating constraint on how you gather data, not a topic for the report.

- Scan volume is **exact, not estimated**: `bytesScanned` from `describe_queries` for Logs Insights, `DataScannedInBytes` from `batch_get_query_execution` for Athena. If a field is genuinely absent for a query, report that query as scan-size-unknown and exclude it from the byte total with a note. Never invent an assumed average scan size, and never run anything to fill the gap.
- Query-ID-level detail is for internal verification (re-sum and sanity-check totals before reporting). Whether it's surfaced in the final output or rolled up to per-role/per-category sums is a presentation choice for the consuming agent; this skill does not mandate either way.

### Resolving rates

**Every rate comes from the AWS Pricing API on this run.** Never hardcode one, carry one over from an earlier report, or recall one from a pricing page. Resolve a rate only for a category whose quantity source yielded a quantity.

1. **Find the price dimension.** `pricing:DescribeServices` for the service, `pricing:GetAttributeValues` to learn whether `operation` or `usagetype` lists the call, then `pricing:GetProducts`. Price dimensions are often not named for the call that triggers them, so derive rather than assume.
2. **Read the rate.** `pricePerUnit.USD` from `terms.OnDemand` → `priceDimensions` at `beginRange: "0"`. The Pricing endpoint is always `us-east-1`; the **workload region** is separate, taken from the log group, workgroup, or trace.
3. **Convert into the returned `unit`, applying no divisor.** The rate is already scaled to one of that unit, whereas pricing pages quote aggregates like "per 1,000 metrics". The unit also decides which quantity is needed at all (see the **quantity source rule**).
4. **Name the price dimension behind each figure** — service code, field, value, `unit` — and where several products matched, which one you chose and why. An unnamed price dimension is not verified. A figure off by a round factor against the service's pricing documentation is a unit error, not a cost-effective call.

**An unresolved charge is not a free operation.** A denied or throttled lookup, no products, no usable `pricePerUnit`, or several products with no discriminator you can name all end the same way: report **not priced: rate unavailable** with the reason, keep the measured quantity, and never print `$0.00`, which is reserved for confirmed zero activity. Any aggregate omitting such a category is a **lower bound**, or unavailable if no defensible subtotal remains.

**Pricing documentation is not a rate source.** It confirms scale, names charges, and carries billing rules the API omits such as minimum billable quantities — but those pages are region-selectored and script-rendered, so a fetch usually returns prose rather than a rate card. Free-tier allowances are deducted nowhere in this report: every figure is gross usage cost.

### Operation classification

**A configuration read is free and gets no row.** `Describe`, `List`, and `Get` calls that return configuration rather than data — alarm definitions, tags, workgroups, saved queries, log-event reads — cost nothing and belong in no cost breakdown. No row, no count, no rate lookup. Without this, every metadata call the agent made would surface as an unclassified line and bury the figures that matter.

**Everything else the audited agent issued is countable, and anything you cannot confirm free is unclassified rather than free.** Give it a row with its count and attempt a price only through *Resolving rates*. What to price and what to count is the **quantity source rule**; what this run may not issue is the **zero-cost rule** (both in Definitions).

---

## Step 4: Grouping (only relevant if multiple spaces/roles are in scope)

If the consuming agent's scope covers more than one Agent Space or role, group the computed numbers two ways:
- **By Agent Space ID**: space ID, space name (if confirmed), query count, total data scanned, total cost.
- **By DevOps Agent Role ARN**: role ARN, space(s) using it, query count, total data scanned, total cost.

If scope is a single space/role (the common case), skip grouping and report that space/role's totals directly.

**This skill prescribes no output template.** Formatting is the consuming agent's decision; follow its format and do not layer this skill's own on top.

---

## Step 5: Tool Usage from Journal (ALL tools: AWS + Azure + 3P MCP)

**Reuse the journal records already read in Step 3.** Do not re-fetch them. Step 3 classified the billable AWS operations; this step classifies *every* tool call from the same records, including the 3P/MCP tools that no AWS API can see.

If journal access is blocked by tool policy this run, report tool usage as unavailable with that reason, never as a confirmed zero. CloudTrail is not a substitute here: it records AWS API calls, not tool invocations, and cannot see Azure, MCP, or platform tools.

From each `utilization` journal record, extract the `data.tools` array and classify:

| Tool Name | Category | Cost Implications |
|-----------|----------|---------------------|
| `use_aws` | AWS | Downstream AWS API costs (see Step 3) |
| `use_azure` | Azure/3P | Reader-role queries, no per-call cost |
| `use_datadog` / `use_newrelic` / `use_splunk` | 3P MCP | May count against 3P API/license limits |
| `shell` | Platform | May invoke `aws`/`az`/`kubectl` in the audited records; check CloudTrail. You issue none yourself (**zero-cost rule**) |
| `subagent` | Platform | Counts toward agent-seconds |
| `fs_read`, `datetime` | Platform | Free |

Journal captures every tool call including 3P/MCP; CloudTrail sees only AWS API calls. A gap between the two for `use_aws` indicates retries, failed calls, or delegation. Step 3's discrepancy rule applies here unchanged.

Counting a `shell` or paid operation from the audited records is legitimate; issuing one yourself is not (**zero-cost rule**).

---

## Step 6: Per-Investigation Breakdown (on request)

Filter CloudTrail + journal for a specific execution and specific space:
- Agent-seconds consumed → direct cost
- AWS API calls (CloudTrail) → downstream breakdown with query IDs
- All tool calls (journal) → 3P usage visibility
- Total cost for that run

---

## Step 7: Validate Before Reporting

Run this self-check against the figures produced by Steps 1 through 6. A failed check resolves one of two ways. If the failure is a correctable error (an arithmetic slip, a missed page, a window not reused), return to the step that produced the figure, fix it, and re-run that check once. If the check cannot pass because the data is genuinely missing (query history does not reach the window start, a rate lookup is denied, CloudTrail or journal access is blocked), report the figure with the label its rule requires, `unavailable` or a `lower bound` with the reason. Do not retry a check whose input cannot change, and do not withhold or zero a figure that a label can carry honestly. Report no figure as verified unless it was corrected or labeled. Each check confirms a named rule or a step output; it does not re-teach the rule, see *Definitions* for the authority. This validates the **correctness** of the figures only; formatting remains the consuming agent's decision.


- [ ] **Every priced category and rate was resolved this run, with its source named.** Confirm for each:
  - *Source.* Service code, field, value, and `unit` came from Pricing API calls this run, scoped to the workload region, no assumed scale or divisor, reported with the figure.
  - *Quantity.* It maps onto that `unit`, passed an order-of-magnitude check, and any several-product pick states its discriminator.
  - *Unresolved.* Reported unpriced with its call count, never `\$0.00`.
  - *Agent-second rate.* Resolved per Step 1 with source stated; if it will not resolve, direct cost is `unavailable`, not computed.

- [ ] **Totals re-sum.** Re-add the per-query and per-category costs independently and confirm they equal the reported total. If they disagree, the per-item detail is authoritative, not the running total. This check passes even when every per-item cost carries the same unit error, so it does not substitute for the unit assertion above.
- [ ] **One window throughout.** Confirm the exact `<START>`/`<END>` fixed in Step 1 was reused in Step 3. A report that mixes windows describes no real period and must be rebuilt.
- [ ] **Attribution test passed.** Confirm every included query passed the attribution test (window AND active role scope). In exact-role mode, confirm no other role was added to compensate for missing activity. Drop anything that matched only one condition.
- [ ] **Athena identity join is complete.** Confirm every priced Athena execution ID came from a successful `StartQueryExecution` CloudTrail event whose `sessionIssuer.arn` matched the active role scope, and that Athena history returned the same ID with a submission timestamp inside the window. Never price an execution inferred only from time or workgroup. Reconcile journal, CloudTrail, and joined-execution counts and report any discrepancy.
- [ ] **Zero-cost rule attested.** State the count of paid operations this run issued, counting every form the zero-cost rule covers: the canonical operations, their wrappers and tool aliases, the same operations invoked through `shell` or a command runner, and any issued by a delegated agent or subagent on this run's behalf. The count must be zero, and the report must say so explicitly. A non-zero count means this run added to the very bill it is reporting: disclose it plainly and say which call did it, by which path.
- [ ] **Enumeration was complete, not just page one.** State how many queries `describe_queries` returned in total and the oldest `createTime` among them. If `nextToken` was still set when you stopped, the count is wrong — finish paginating. If the oldest returned query is newer than the window start, say so and label the figure a lower bound.
- [ ] **Logs source rule honored.** Confirm every Logs Insights call count, role attribution, scan volume, and cost came from `describe_queries`, that no CloudTrail `StartQuery` lookup was issued, and that Logs was reported unavailable (not substituted) if `describe_queries` was unavailable.
---

## Environment Notes

This skill ships with **no account, Region, Agent Space, or role identifiers.** Resolve them at run time from the installation it is running in, and verify each one before any AWS data call.

| Value | How to resolve it | Verified when |
|---|---|---|
| `ACCOUNT_ID` | `list_associations` for the calling Agent Space | the association returns an `accountId` |
| `AGENT_SPACE_ID` | `get_agent_space` for the current space | `agentSpaceId` is returned and matches the space the request is scoped to |
| `ROLE_ARN` | `list_associations` → `configuration.aws.assumableRoleArn` | the ARN's account equals the resolved `ACCOUNT_ID` |
| workload Region | the Agent Space's deployment Region, resolved from the space | `get_agent_space` / `list_associations` returns the Region the space runs in |
