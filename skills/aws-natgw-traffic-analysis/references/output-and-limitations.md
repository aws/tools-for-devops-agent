# Output Format and Limitations

## No dollar figures — ever

Report traffic volume in **GB and percentages only**. This skill does not calculate or present savings in dollars.

**Present:** "72,000 GB (~57% of addressable traffic) going to customer-owned IPs via NAT Gateway — could be internalized via private IPs over existing peering."

**Do not present:** "$X/year in potential savings."

Rationale: cost depends on the account's specific rate card, negotiated discounts, and the exact date window sampled. Even when the account's rates can be retrieved (for example from Cost Explorer), a rate from one service, region, or billing window applied to flow-log GB from another produces a confident wrong number — so this rule holds even when the user asks for dollars. A wrong dollar figure is worse than no dollar figure; give the formula and inputs, and the customer (or their own FinOps/TAM resource) applies their own pricing to the volume figures given here.

## Mandatory data-window disclaimer

Every output must state the sample window and a representativeness caveat, in this form:

> "Based on [X] days of flow log data ([start date] – [end date]). Annualized or extrapolated figures assume these days are representative. Weekday/weekend traffic patterns may vary 2-3×."

## Mandatory limitations block

Every output must include a "what we cannot determine" section. Minimum content:

```
Limitations
- Cannot identify the specific pod/instance/container generating traffic — NAT Gateway
  flow logs show the NAT Gateway's own IP as source, not the origin inside the VPC.
- Cannot determine which specific S3 bucket is being called — flow logs show
  destination IP, not bucket name.
- Cannot tie CopyObject/CopyPart activity to a specific VPC — usage-record data for
  these operations is typically account-level, not VPC-scoped.
- Only S3 and DynamoDB destinations are attributed to a service by the byte (managed
  prefix lists). Other AWS services are identified from a CloudTrail sample of API
  calls — call counts, not bytes — so Interface Endpoint recommendations for them are
  candidates whose payoff can't be quantified from flow logs.
- Flow log source: [log group / S3 location and table / user-supplied file], at the
  [ENI / subnet / VPC] level, filtered to the NAT Gateway ENI.
- Annualized or extrapolated figures assume the sampled window is representative.
- [Add any run-specific limitations — e.g., a specific API call that failed or
  returned no data]
```

Never omit this block, even when the analysis feels complete — the underlying data source (NAT Gateway flow logs) has these limitations structurally, regardless of how much of it you have.

## Verification status labeling

Label every finding with one of:

- **Verified** — a tool/API call succeeded and the fact is directly confirmed by its response.
- **Unverified** — a query could not be completed; state exactly what was attempted and what failed. Never silently omit an unverified item.
- **Assumption** — an inference drawn from available evidence, not direct proof. State the reasoning that led to the inference.

Never present an unverified finding as if it were confirmed. If more than one explanation for an observation is plausible, list all of them rather than silently picking one.

## Options, not silver bullets

For every addressable finding, present the available fix options as a comparison table with tradeoffs (cost, complexity, determinism, failover behavior) — never a single recommendation with no alternatives shown, since the "best" option depends on constraints (e.g., existing CRR, CopyObject usage, CIDR overlap) that vary per customer.

## Recommend non-production validation

Any fix that touches routing, endpoints, or DNS should be validated in a non-production environment before being applied to production traffic.
