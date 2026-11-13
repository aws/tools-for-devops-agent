# Evidence Sources Reference

Detailed lookup reference for each business-context category. Kept out of
`SKILL.md` to stay under the recommended 500-line guideline.

## 1. Dependent services and criticality

| Evidence source | How to query | Notes |
|---|---|---|
| Resource tags | `rds:ListTagsForResource` on the cluster/instance ARN, or `tag:GetResources` filtered by tag key | Look for `DependentServices`, `Owner`, `Criticality`, `OnCallTeam` |
| Customer dependency map | Operator-supplied CMDB export / architecture doc / JSON config | Treat as authoritative for the session; don't assume it's current |
| Connection evidence | Performance Insights `pi:DescribeDimensionKeys` grouped by `db.host`, `db.user`, or `db.application`; VPC Flow Logs; security group references | Weakest signal: shows *what connects*, not *criticality* |

## 2. Cost of downtime

| Evidence source | How to query | Notes |
|---|---|---|
| Tags | `RevenuePerMinute`, `SLAThresholdMinutes`, `SLAPenaltyUsd` on the resource or its app tag group | Preferred — auditable and resource-specific |
| Operator-stated figure | Direct input in the conversation | Session-scoped only, do not persist |
| None found | — | Report technical impact only; state explicitly that a $ estimate needs a revenue-per-minute input |

## 3. Compliance and reporting exposure

| Framework | Reporting window | Starts when |
|---|---|---|
| PCI-DSS | Immediate notification to the acquirer/processor | A compromise of cardholder data is suspected or confirmed |
| GDPR | Without undue delay, and where feasible within 72 hours, to the supervisory authority | The controller becomes aware of a personal data breach. A loss of availability of personal data can itself be a breach. |
| HIPAA | Individuals: without unreasonable delay, no later than 60 days. HHS: within 60 days if 500 or more people are affected, otherwise within 60 days after the end of the calendar year | A breach of unsecured PHI is discovered |

Only apply a framework if the resource carries a matching `DataClassification`
or `Compliance` tag, or the operator states it applies. Write each window as
conditional ("if assessed as a breach, for the compliance owner to decide").
Never state whether a reporting deadline has started or doesn't apply.

## 4. Recent-change correlation

| Evidence source | How to query | Notes |
|---|---|---|
| AWS Config | `config:GetResourceConfigHistory` for the cluster/parameter group | Default lookback: 14 days. Not in `AIDevOpsAgentAccessPolicy`; on AccessDenied, use CloudTrail and say Config history wasn't readable |
| CloudTrail | `cloudtrail:LookupEvents` for `ModifyDBClusterParameterGroup`, `ModifyDBCluster`, `ModifyDBInstance`, `FailoverDBCluster`, engine upgrades | Rank by proximity to incident start |
| Customer change system | Pipeline history, change tickets (if named by the operator) | Use if referenced; don't assume access |
