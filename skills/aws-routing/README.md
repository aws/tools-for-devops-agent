# aws-routing skill

An AWS routing subject matter expert skill for path selection, BGP traffic engineering, and route
evaluation across AWS networking services (Cloud WAN, Direct Connect, Transit Gateway, VPC, VPN).
It provides **read-only** analysis, recommendations, and troubleshooting grounded in public AWS
documentation and field-proven patterns.

## What it does

- Explains and applies the route-evaluation order for Cloud WAN CNEs, DXGW path selection, TGW route
  tables, and VPC route tables.
- Advises on BGP traffic engineering: LP communities (`7224:7100/7200/7300`), AS-path prepending
  (within-region only), MED, and longest-prefix-match.
- Analyzes DX + VPN redundancy, active/active vs active/passive, and failover behavior.
- Flags non-deterministic path selection and recommends deterministic alternatives.
- Produces read-only validation commands (`describe-*`, `get-*`, `list-*`).

## Prerequisites

- No write permissions required — the skill is read-only.
- To run the suggested validation commands, the operator needs read-only access to the relevant
  networking APIs (e.g., `ec2:Describe*`, `directconnect:Describe*`, `networkmanager:Get*`).

## How to use it

Ask routing questions in natural language, for example:
- "Why is my Cloud WAN traffic for an aggregate prefix leaving the local region instead of using the
  local Direct Connect?"
- "How do I make a Transit Gateway prefer one Direct Connect location over another?"
- "Is my DX + VPN design active/active or active/passive, and will failover be deterministic?"

The skill will trace the path, apply the evaluation logic, cite the relevant AWS documentation, and
suggest read-only commands to validate.

## Structure

```
aws-routing/
├── SKILL.md            # Activation metadata + instructions
├── references/         # Detailed routing mechanics and patterns
├── README.md           # This file
├── CHANGELOG.md        # Version history
└── evals/              # Functional and trigger tests
```

## Disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Validate all routing guidance in a non-production environment first. Recommendations are
> based on public AWS documentation and field experience and may change as AWS services evolve.
