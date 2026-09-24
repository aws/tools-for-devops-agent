# DevOps Agent Cost Dashboard

This custom agent runs the [`devops-agent-cost-insights` skill](../../skills/devops-agent-cost-insights/README.md) on a schedule, scoped to one IAM role, and emits a fixed dashboard plus a text summary. Where the skill is the method, this agent is the persona that runs it: it pins the configuration, fixes the reporting window, executes silently, and produces the same report layout on each run.

Use it when you want a recurring, charted cost report for a single DevOps Agent role rather than an ad-hoc chat answer.

> **Figures are estimates, not billing data.** They are reconstructed from CloudWatch metrics, CloudTrail events, and query execution history, priced at published list rates. AWS Billing and AWS Cost Explorer remain the authoritative record of what you were charged. This output must not be used as the basis for invoicing, chargeback, or contractual commitments.

---

## Architecture:

The scheduled cost dashboard agent applies the devops-agent-cost-insights skill, which reads CloudWatch metrics, the Pricing API, Logs Insights and Athena query history, CloudTrail, and journal records, then emits a charted dashboard artifact and a fixed text summary

---

## What it produces

Each run creates or refreshes a single artifact named "DevOps Agent Cost Dashboard" and then emits one text summary. Both cover the same trailing window:

- **Direct usage**, per day, priced per agent-second and scoped to the Agent Space
- **Credits**, shown as an account-level reference (see the scope note below)
- **Downstream** AWS API cost, attributed to the one configured role
- **Tool usage**, including Azure and third-party MCP tools that do not appear on an AWS bill
- **Validation notes**, including a zero-count attestation for each paid operation the run is forbidden to issue

The report keeps direct usage (space-scoped) and downstream (role-scoped) as separate figures.

---

## Generated output

Each run emits two things: a charted **dashboard artifact** and a fixed **cost summary**. The summary format is shown below with placeholders; each run fills them with the figures it computes, or marks a field unavailable with the reason.

**Dashboard artifact** ("DevOps Agent Cost Dashboard"), refreshed in place each run: a totals panel, direct usage cost per day, priced downstream cost by category, tool usage by category.

**Cost summary:**

```text
📊 DEVOPS AGENT COST SUMMARY
═══════════════════════════════════════════════════════════════
Billing Period:   <START ISO> → <END ISO>
Agent Space:      <SPACE_NAME> (<REGION>)
Account:          <ACCOUNT_ID>
Role Scope:       exact role only
Data Source:      GetMetricStatistics · AWS/AIDevOps

── DIRECT USAGE · space-scoped ────────────────────────────
Investigations:                 X.XX hrs              $XX.XX
Evaluations:                    X.XX hrs              $XX.XX
On-demand (Chat):               X.XX hrs              $XX.XX
Release Readiness:              X.XX hrs              $XX.XX
                                          ──────────────────
Direct Cost (before account-level credits):          $XX.XX

── CREDITS · account-level reference only ─────────────────
Support Plan:     <plan | unknown>
Credit Rate:      <XX% | unavailable>
Net Direct Cost:  unavailable at this scope

── DOWNSTREAM · exact-role scoped ─────────────────────────
Logs Insights:        X queries · X.XX GB             $XX.XX
Athena:             X executions · X.XX TB            $XX.XX
GetMetricData:          X calls · X metrics           $XX.XX
X-Ray retrieved:        X calls · X traces            $XX.XX
                                          ──────────────────
Priced Downstream Total:                              $XX.XX
                                  <exact | lower bound>

── TOOL USAGE · exact-role scoped ─────────────────────────
AWS tools:        XXX calls
Azure/3P MCP:      XX calls
Platform:          XXX calls

Scopes differ; no combined total is reported.
Paid calls:       0
═══════════════════════════════════════════════════════════════
```

---

## How it differs from asking the skill in chat

| | Skill in chat | This custom agent |
|---|---|---|
| Output | A plain answer | A fixed dashboard layout plus a fixed summary |
| Execution | Conversational | Silent: no narration, one final message |
| Cadence | On demand | On demand or on a schedule |

The calculations are identical. The agent adds configuration, a fixed window and a consistent layout.

---

## Setting it up

### 1. Install the skill first

This agent calls the `devops-agent-cost-insights` skill by name, so install the skill before creating the agent. Follow the [skill README](../../skills/devops-agent-cost-insights/README.md#getting-started).

### 2. Create the agent

Operator Web App → Agents → Create agent. You can supply the agent's instructions two ways:

- **Import from GitHub after cloning.** Clone this repository and import the agent through the GitHub integration, pointing it at this folder so `SYSTEM_PROMPT.md` is picked up as the instructions.
- **Paste the prompt directly.** Copy `SYSTEM_PROMPT.md` from this folder and paste it into the agent's instructions.

### 3. Fill in the Config table

The prompt opens with a Config table. This is the only place these values appear; the rest of the prompt refers to them by name. Replace each placeholder:

| Key | What to put | Where to find it |
|---|---|---|
| `ACCOUNT_ID` | The account being measured | The account the Agent Space runs in |
| `REGION` | The Agent Space deployment Region | `get_agent_space` / `list_associations` |
| `SPACE_NAME` | Display name for the report header | Your Agent Space |
| `SPACE_ID` | The `AgentSpaceUUID` | `get_agent_space` |
| `ROLE_NAME` | The role to measure, short name | The DevOps Agent role for this space |
| `ROLE_ARN` | The full ARN of that role | `list_associations` |
| `WINDOW_DAYS` | Reporting window length in days | Your choice; defaults to `15` |
| `SUPPORT_PLAN` | Your AWS Support plan, e.g. `Enterprise Support`. Leave blank to omit credits. | Billing console, Support plans |
| `PRIOR_MONTH_SUPPORT_CHARGE` | Last month's `AWS Support` charge, e.g. `5000`. Leave blank to omit credits. | Previous month's bill |

To change the reporting period later, edit `WINDOW_DAYS` alone. The window is a trailing range computed at run time: `<END>` is the run time and `<START>` is `WINDOW_DAYS` before it, so a scheduled run always covers the most recent window.

`SUPPORT_PLAN` and `PRIOR_MONTH_SUPPORT_CHARGE` are optional. When set, the agent derives the credit rate from the plan and shows the plan, rate, and monthly credit as account-level reference. This agent reports one role in one space, so the credit is never subtracted here and `Net Direct Cost` stays `unavailable at this scope`; leave both blank to omit the credit lines entirely.

### 4. Enable CloudTrail capture for the downstream breakdown

The Athena identity join reads `StartQueryExecution`, a management event CloudTrail records by default, so grant `cloudtrail:LookupEvents` and confirm no tool policy blocks it. Without it, the Athena line is reported unavailable, never zero. `GetMetricData` and the X-Ray operations reach CloudTrail only as data events, which are off by default and add a recording charge. Enable them if you want those rows priced: the data event carries both the call count and the billable quantity. Without them the rows report as unavailable.

### 5. Set the schedule

Attach the agent to a schedule for recurring reports, or run it on demand. A weekly cadence keeps the run's own agent time small relative to the figures it reports; a daily cadence on a lightly used space can become a meaningful fraction of what you are measuring. Match `WINDOW_DAYS` to the cadence you choose so consecutive reports tile the period rather than overlapping heavily.

---
