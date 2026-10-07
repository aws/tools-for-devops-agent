# AWS Config Billing Model

Reference for how AWS Config charges accrue. Load this when you need the exact
pricing components behind a finding, or when deciding whether continuous or daily
recording is cheaper for a given resource type.

Sources:
- [AWS Config pricing](https://aws.amazon.com/config/pricing/)
- [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

## What is billed

AWS Config billing has three primary components plus storage:

| Charge | Billed on |
|--------|-----------|
| Configuration items (CIs) | Each CI recorded — the dominant cost driver |
| Config rule evaluations | Each active rule evaluation |
| Conformance pack evaluations | Each conformance pack rule evaluation |
| S3 storage | Configuration history and snapshots stored in the delivery bucket |

## Recording frequency changes the CI price and cadence

| Mode | Price per CI | Cadence |
|------|-------------|---------|
| Continuous | ~$0.003 | Bills a CI for **every** change |
| Daily | ~$0.012 | Bills at most **one** CI per resource per day |

## Key consequence

For **high-churn** resources (many changes per day), continuous recording bills every
single change and often costs **more** in total than daily recording, even though
daily's per-CI price is higher. For low-churn resources, continuous is usually
cheaper. The right choice is per-resource-type and depends on change frequency — never
a blanket setting.
