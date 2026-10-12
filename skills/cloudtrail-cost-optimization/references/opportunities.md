# Cost Optimization Opportunity Catalog

Detailed reference for the seven opportunity checks. Load this during Step 4
(Analyze) when evaluating each trail and event data store. Assign each finding a
severity (CRITICAL, HIGH, MEDIUM, LOW, INFO) and, wherever a usage or cost signal
exists, an estimated monthly saving.

## 4.1 Duplicate management-event trails (highest-impact, most common)
Ref: [Troubleshoot CloudTrail cost and usage increases](https://repost.aws/knowledge-center/remove-duplicate-cloudtrail-events)

- More than one trail delivering **management events** in the same Region → every
  copy after the first is billable. Keep one trail (ideally the org or multi-Region
  trail) logging management events and turn management event logging **off** on the
  duplicates → **HIGH** (frequently the single largest CloudTrail line item; org-wide
  de-duplication can cut CloudTrail spend substantially).
- A **multi-Region trail plus an additional single-Region trail** capturing the same
  management events → the single-Region trail is a paid duplicate → **HIGH**.
- A **member account trail** duplicating the management events already captured by an
  **Organizations trail** → **HIGH**.
- Report which trail to keep (prefer the broadest-scope, org/multi-Region, actively
  logging trail) and which to convert to data-events-only or disable.

> **Interaction rule — dedup changes what the surviving trail is.** Once you
> de-duplicate down to a single management-event trail, that trail's management events
> become the **free first copy** for the Region (see §4.3 and Known Quirks). This has
> two consequences you MUST reflect when the dedup finding and a
> §4.2/§4.3 filtering finding both apply to the same account:
> 1. **Do not also recommend excluding KMS/RDS or dropping Read events on the
>    surviving sole trail.** After dedup there is no paid copy left to trim — the
>    filtering saves ~$0 on management events, and it would leave **no trail anywhere**
>    capturing those events, which is a coverage/audit gap, not an optimization.
> 2. Exclusion and Read-only trimming (§4.2, §4.3) are only valid on a **paid copy you
>    are deliberately keeping** (e.g. a second trail retained for a distinct
>    consumer). If you are not keeping a second copy, the §4.1 dedup captures the
>    entire management-event saving on its own — do not double-count a filtering
>    saving on top of it.
>
> When both a dedup finding and a filtering finding surface, pick **one** path and say
> so explicitly: either (a) keep a single free authoritative trail and drop the
> filtering findings as inapplicable, or (b) keep a paid second copy for a stated
> reason and apply filtering to that paid copy only. Never present (a) and the
> filtering findings as an additive stack of savings.

## 4.2 Read management events that aren't needed
Ref: [Optimize CloudTrail costs and maintain compliance](https://repost.aws/knowledge-center/optimize-cloudtrail-compliance)

- A **paid** (non-free-copy) trail logging **Read** management events when the use
  case only needs Write events → drop Read events → **MEDIUM**. (The free first copy
  can safely log both; this applies to the duplicate/paid copies.)

## 4.3 High-volume noise events
Ref: [Controlling CloudTrail costs using KMS event filtering](https://aws.amazon.com/blogs/aws-cost-management/launch-controlling-aws-cloudtrail-costs-using-aws-kms-event-filtering/)

- A **paid** trail (a second-or-later copy of management events in the Region) not
  excluding **AWS KMS** events on accounts with heavy SSE-KMS usage (busy S3, EBS,
  Secrets Manager) → KMS events can dominate volume → exclude via event selectors →
  **MEDIUM**.
- A **paid** trail not excluding **RDS Data API** events on accounts using the Data
  API heavily → exclude → **MEDIUM**.
- **Precondition — a paid copy must actually exist and be kept.** Management-event
  filtering only saves money on a *billable* copy. The **first copy of management
  events per Region is free**, so excluding KMS/RDS from the single authoritative
  trail saves **nothing** on management events. Never recommend KMS/RDS exclusion on:
  - the single authoritative trail, or
  - a trail that will *become* the single authoritative trail after a §4.1 dedup.

  Excluding events there does not reduce cost and **removes those events from the only
  place that captures them** — a security/audit coverage gap. If the account has just
  one management-event trail, this finding does **not** apply; report it as
  inapplicable rather than as a saving. Only surface it when the customer is
  deliberately keeping a paid second copy, and then scope the exclusion to that paid
  copy alone, leaving the authoritative trail complete.

## 4.4 Overly broad data event logging
Ref: [Filtering data events with advanced event selectors](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/filtering-data-events.html)

- Data events logged for **all** S3 buckets / Lambda functions / DynamoDB tables
  when only a subset is security-relevant → every data event delivery is billed →
  narrow with advanced event selectors (by `resources.ARN`, `eventName`, or
  `readOnly`) → **HIGH** when data event volume is large.
- The **same data events delivered by multiple trails** → each delivery is billed
  separately (no free copy for data events) → consolidate → **HIGH**.

## 4.5 CloudTrail Lake spend
Ref: [Managing CloudTrail Lake costs](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake-manage-costs.html)

- An event data store's **pricing option** mismatched to its query pattern
  (one-time-query data ingested on the higher-priced flexible-retention option, or a
  frequently queried store on a suboptimal option) → **MEDIUM**.
- **Retention** far longer than the compliance requirement → storage waste →
  **MEDIUM**.
- A Lake store capturing the **same events already captured by a trail** with no
  distinct query need → duplicate ingestion → **MEDIUM**.

## 4.6 S3 destination hygiene
Ref: [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

- The trail's destination S3 bucket has **no lifecycle policy** transitioning old
  logs to cheaper tiers (S3 Glacier/Deep Archive) or expiring them → storage grows
  unbounded → **LOW**.

## 4.7 Idle / stopped trails
- A trail with `IsLogging=false` still configured → confirm it is intentional; if
  abandoned, delete to reduce management overhead → **INFO** (no direct charge while
  stopped, but signals drift).
