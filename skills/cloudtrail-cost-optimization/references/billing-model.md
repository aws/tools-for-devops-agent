# CloudTrail Billing Model

Reference for how CloudTrail charges accrue. Load this when you need the exact
pricing rules behind a finding — especially when deciding whether a trail copy is
free or paid, or when explaining a charge to the user.

Sources:
- [Managing CloudTrail trail costs](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-trail-manage-costs.html)
- [CloudTrail pricing](https://aws.amazon.com/cloudtrail/pricing/)

## What is billed

| Charge | Billed | Free allowance |
|--------|--------|----------------|
| Management events | Per event delivered to a trail, beyond the first copy per Region | First copy per Region is **free** |
| Data events | Per event delivered — **every** copy is billed, including the first | None |
| Network activity events | Per event delivered | None |
| CloudTrail Lake ingestion | Per GB ingested (pricing depends on the event data store's pricing option) | None |
| CloudTrail Lake storage | Per GB-month beyond the included retention | Varies by pricing option |
| S3 storage of log files | Standard S3 storage on the destination bucket | None |

## Key consequences

- A **second copy** of the same management events in a Region always costs money.
  A multi-Region trail already covers every Region, so any additional single-Region
  trail capturing the same management events is a paid duplicate.
- An **Organizations trail** is replicated into every member account. A member
  account that also runs its own trail for the same management events pays for a
  second copy.
- **Data events are never free** — narrowing their scope with advanced event
  selectors is almost always a direct saving.
- **KMS and RDS Data API events** can dominate management-event volume (e.g.
  SSE-KMS on busy S3 buckets), and can be excluded via event selectors.
