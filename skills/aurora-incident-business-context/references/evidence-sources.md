# Evidence Sources Reference

Detailed lookup reference for each business-context category. Kept out of
`SKILL.md` to stay under the recommended 500-line guideline.

## 1. Dependent services and criticality

| Evidence source | How to query | Notes |
|---|---|---|
| Resource tags | `aws rds list-tags-for-resource --resource-name <arn>` or `resourcegroupstaggingapi:GetResources` | Look for `DependentServices`, `Owner`, `Criticality`, `OnCallTeam` |
| Customer dependency map | Operator-supplied CMDB export / architecture doc / JSON config | Treat as authoritative for the session; don't assume it's current |
| Network evidence | VPC Flow Logs, security group references, `SHOW PROCESSLIST` / Performance Insights top callers | Weakest signal — shows *what connects*, not *criticality* |

## 2. Cost of downtime

| Evidence source | How to query | Notes |
|---|---|---|
| Tags | `RevenuePerMinute`, `SLAThresholdMinutes`, `SLAPenaltyUsd` on the resource or its app tag group | Preferred — auditable and resource-specific |
| Operator-stated figure | Direct input in the conversation | Session-scoped only, do not persist |
| None found | — | Report technical impact only; state explicitly that a $ estimate needs a revenue-per-minute input |

## 3. Compliance and reporting exposure

| Framework | Typical mandatory reporting window | Trigger condition |
|---|---|---|
| PCI-DSS | Immediate notification to acquirer/processor | Suspected cardholder data exposure |
| SOC 2 Type II | Per the org's documented IR policy (commonly ≤60 min internal escalation) | Availability/security incident affecting in-scope systems |
| GDPR | 72 hours to supervisory authority | Personal-data breach |
| HIPAA | 60 days to HHS + affected individuals | Breach of unsecured PHI |

Only apply a framework if the resource carries a matching `DataClassification`
or `Compliance` tag, or the operator states it applies. Do not assume by
default.

## 4. Recent-change correlation

| Evidence source | How to query | Notes |
|---|---|---|
| AWS Config | `config:GetResourceConfigHistory` for the cluster/parameter group | Default lookback: 14 days |
| CloudTrail | `cloudtrail:LookupEvents` for `ModifyDBClusterParameterGroup`, `ModifyDBCluster`, `ModifyDBInstance`, `FailoverDBCluster`, engine upgrades | Rank by proximity to incident start |
| Customer change system | Pipeline history, change tickets (if named by the operator) | Use if referenced; don't assume access |

## Illustrative example (from the original demo prototype)

The Aurora MySQL Incident Investigation demo's original mock MCP server used
this synthetic data purely to make the demo self-contained and runnable
without real tags/config. It is **not** real data and must not be reused as
a default or fallback value by this skill:

```json
{
  "dependent_services": [
    {"name": "checkout-service", "criticality": "CRITICAL"},
    {"name": "order-history-api", "criticality": "HIGH"},
    {"name": "analytics-etl", "criticality": "MEDIUM"}
  ],
  "revenue_per_minute_usd": 5100,
  "sla_penalty_threshold_min": 20,
  "compliance_frameworks": ["PCI-DSS", "SOC 2 Type II", "GDPR"]
}
```
