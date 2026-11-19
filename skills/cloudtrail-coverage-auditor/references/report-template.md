# Report Template for CloudTrail Coverage Auditor

Load this file at Step 9 of SKILL.md, immediately before rendering. Render every
`##` heading below in this order, even when a section is empty; an empty section
says why (no findings, no event data stores, nothing denied). Replace every
`<placeholder>` and never leave one in the output.

The rendered report is the final message to the user. It is not an internal
artifact to summarise afterwards. If a subagent or Context Gatherer rendered
it, the parent relays it unchanged and adds nothing after it: no introduction
before the title, no "short version", no "suggestions to go deeper", no note to
the parent, and no closing offer after the report to modify configuration,
open a support case, draft API calls, re-run from another account or extend the
report. Every recommendation is an operator action inside Next Steps. The
message ends with the Not Assessed table. The section order puts the Bottom
line, the Resource Coverage table and Next Steps (the organization trail ARN
command) on the first screen so a relaying parent keeps them. The report
contains no note addressed to the parent or to any reader other than the user;
the relay rule lives in SKILL.md, not in the output. The rating word
(`Healthy`, `Attention`, `AtRisk`, `Indeterminate`), the five state words (`Covered`,
`CoveredByOrgTrail-Unverified`, `Uncovered`, `Unknown`, `NotApplicable`), the
data source label (`READ FROM APIs`, `SUPPLIED DATA`) and the 20 Check Matrix
IDs are fixed vocabulary; a synonym is a defect.

## Report

```markdown
# CloudTrail Coverage Audit: <accountId | account: not supplied>
Evaluated <YYYY-MM-DD HH:MM UTC>. Data source: <READ FROM APIs | SUPPLIED DATA>.

## Scope
| Item | Value |
|---|---|
| Account | <accountId from sts:GetCallerIdentity, or in SUPPLIED DATA mode the account id present in the supplied ARNs, else "not supplied"> (<standalone | member of organization <o-id> | management account of <o-id> | delegated administrator of <o-id> | not supplied>) |
| Regions swept | <list> |
| Regions not swept | <none | list, with the reason: user scope, or inventory denied> |
| Mode | <baseline | required list (<n> resources named)> |
| Resource types in scope | <S3 buckets, Lambda functions, DynamoDB tables | plus request only types> |
| Trails evaluated | <n> unique (<n> own, <n> organization), <n> event data stores |
| Organization trail selectors | <read with the full trail ARN | not readable from this account: the agent's AWS tool blocked the cross account ARN <trail ARN> (ToolingFailure) | no organization trail | not applicable> |
| Organization trail home Region | <none | <region> (default Region) | <region> (opt in Region, enabled in this account) | <region> (opt in Region, NOT enabled in this account: the trail receives no activity from this account) | <region> (opt in Region, this account's Region status could not be read)> |

## Coverage Rating
**<Healthy | Attention | AtRisk | Indeterminate>**: <one sentence naming the deciding rule, for example "no multi Region trail logs management events" or "6 baseline resources have no data event record and log file validation is off on one trail">.

Bottom line: <N> of <M> in scope resources have a data event record; <K> have none<; <U> could not be verified>; management events <are | are not> captured in every enabled Region; logs <are | are not> being delivered. <If the user asked a yes or no question, answer it here in their words.>

## Resource Coverage
<N> of <M> in scope resources are Covered. One row per in scope bucket, function and table.
| Region | Type | Resource | State | Covering trail or store | Selector note |
|---|---|---|---|---|---|
| <region> | <S3 bucket | Lambda function | DynamoDB table> | <name> | <Covered | Covered (write only) | Covered (read only) | Covered (prefix <p> only) | Covered (eventName <list>) | Covered (excludes service-initiated events) | CoveredByOrgTrail-Unverified | Uncovered | Unknown | NotApplicable> | <trail name | none | unreadable: <trail ARN>> | <all objects | prefix <p> only | write only | eventName <list> | eventType NotEquals AwsServiceEvent | userIdentity.arn NotStartsWith <value> | basic selector arn:aws:s3 | advanced StartsWith <arn> | also recorded by <trail> | not found in account | not supplied | ->
<One line when any table is in scope: "DynamoDB stream events are logged with the table's data events; stream presence is not read.">

## Next Steps
1. <Operator action for the highest finding, as an API or console change, with the trail or selector named.>
2. <...>
<When O1 fired: "Run `aws cloudtrail get-event-selectors --trail-name <trail ARN>` and `aws cloudtrail get-trail-status --name <trail ARN>` from the CLI (member account credentials work) or from management account <id> (or the delegated administrator) to confirm the organization trail's data event scope; that resolves the <U> CoveredByOrgTrail-Unverified rows.">
<Management account run: "This review covers resources in this account only. Organization trail data resources naming other accounts' ARNs are listed in Trail Inventory as covering resources outside this account; run the review in each member for a per account answer.">

## Trail Inventory
| Trail or store | Owner account | Regions | Management events | Data event types | Logging | Last delivery | Validation | Insights |
|---|---|---|---|---|---|---|---|---|
| <name> <(organization trail) | (event data store)> | <accountId> | <all | home-region> | <read and write | write only | read only | none> | <S3 objects (all buckets) | S3 objects (1 bucket) | Lambda | DynamoDB | none> | <yes | NO since <time>> | <time | error: <LatestDeliveryError>> | <on | off | n/a> | <on | off> |

## Findings
Ordered by severity. Each names the field and value it rests on and the operator change. Nothing here was executed.
| ID | Severity | Finding | Evidence | Operator change |
|---|---|---|---|---|
| <D1> | <CRITICAL | HIGH | MEDIUM | LOW | INFO> | <what, which resources, which trail> | <field = value> | <API or console action, one sentence, for example "add a data event selector for AWS::S3::Object on trail X, or an advanced selector with resources.ARN StartsWith arn:aws:s3:::bucket/"> |

## Check Matrix
| ID | Check | Result | Evidence |
|---|---|---|---|
| T1 | Multi Region management logging | <PASS | FAIL <severity> | AccessDenied | ToolingFailure | NotApplicable> | <trail and field> |
| T2 | Global service events | ... | ... |
| M1 | Management read and write | ... | ... |
| M2 | Management sources recorded | ... | ... |
| M3 | Service initiated events excluded (data selectors; management selectors on event data stores) | ... | ... |
| D1 | S3 object data events | <PASS | PASS (narrowed) | FAIL <severity> | ...> | ... |
| D2 | Lambda invoke data events | ... | ... |
| D3 | DynamoDB data events | ... | ... |
| D4 | Selector precision | ... | ... |
| I1 | Insights | ... | ... |
| L1 | Stopped trail has not removed coverage | ... | ... |
| L2 | No delivery error | ... | ... |
| L3 | Recent delivery | ... | ... |
| L4 | Log file validation | ... | ... |
| E1 | KMS encryption | ... | ... |
| E2 | Destination bucket posture | ... | ... |
| O1 | Organization trail selectors readable | ... | ... |
| O2 | Organization trail reaches this member (management events; opt in home Region) | ... | ... |
| N1 | Event history note | INFO | Event history: 90 days, management events only, one Region per search, separate from trails |
| N2 | Automated system attribution note | INFO | Service activity carries userIdentity.invokedBy; service linked role sessions show a sessionIssuer under aws-service-role/; eventType AwsServiceEvent marks service originated events |

## What Auditors Should Know
- Event history: <the 90 day, management only, one Region per search limit, and that trails or Lake are the durable record>.
- Automated systems: <how AWS service and service linked role activity is attributed in events, and whether any data event selector in this account excludes it (M3), naming the resources whose rows say "excludes service-initiated events">.
- Organization trail: <read from this account with the full ARN and what it contributes | not readable by the agent from this member account (its AWS tool blocks the cross account ARN; the CloudTrail API itself permits the call); confirm with the command in Next Steps from the CLI or management account <id>>.
- CloudTrail Lake: <stores counted as coverage sources, with retention | none>.
- Not covered by this review: CIS or Security Hub control scoring, log content, and cost. <When more than one trail records the same events: "N trails record <management events | data events for <resources>>; coverage is not affected. What the extra copies cost is answered by cloudtrail-cost-optimization.">


## Not Assessed
| Item | Call | Status |
|---|---|---|
| <trail, type, bucket or check> | <API> | <AccessDenied | ToolingFailure | Unknown | NotApplicable (reason)> |
<or "Nothing. Every call succeeded.">
```

## Required list mode differences

- Scope `Mode` says `required list` with the count.
- Resource Coverage lists only the required resources; a name that does not
  resolve in the inventory is a row with state `Unknown` and selector note `not
  found in account`, never dropped.
- D1 to D3 are CRITICAL when any required resource is `Uncovered`; the rating is
  then `AtRisk`.
- Bottom line states whether the requirement is met: "Requirement <is | is
  not> met: <N> of <M> required resources have a data event record."

## Supplied data (no account access) differences

- Data source label is `SUPPLIED DATA`; Scope says which API outputs were
  supplied.
- The title and the Scope `Account` row use the account id present in the
  supplied ARNs (a trail ARN, a resource ARN, a `userIdentity.arn` value); when
  none is present they say `account: not supplied`. An account id is never
  invented or taken from an example.
- Every section still renders. A resource row whose coverage cannot be decided
  from the supplied data is `Unknown` with the reason ("selectors not
  supplied", "trail status not supplied"); a check whose inputs were not
  supplied is `NotApplicable` with "not supplied". Resources not listed in the
  prompt are not invented; Resource Coverage then says "0 of 0, none supplied".
- Regions not stated are "as supplied"; no Region sweep is claimed.

## Pre render validation

1. The resource counts in Coverage Rating, Bottom line and Resource Coverage
   are identical.
2. The Check Matrix has exactly 20 rows, T1 through N2, in order, ID alone in
   the first column, and N1 and N2 are present with their notes.
3. Every `Uncovered` row was reached only after every readable source was
   evaluated; every denied or cancelled call is in Not Assessed and produced
   `Unknown` or `CoveredByOrgTrail-Unverified`, not `Uncovered`.
4. Every organization trail row says whether it was read with the full ARN.
5. No sentence offers to create, modify, start, stop or delete anything, to
   open a support case, to draft `UpdateTrail` or `PutEventSelectors` calls,
   to re-run from another account, or to extend the report; no "want me to",
   "I can update", "shall I enable", "I can try again", "happy to add"; no
   menu or `ask_user` option that would enable, start or modify anything.
6. The rating word appears once and is one of the four.
7. The message starts with the title line and ends with the last Not Assessed
   row (or "Nothing. Every call succeeded."); nothing follows it.
8. A subagent's report is relayed unchanged by the parent, which adds nothing
   before or after it. The sections appear in the order of this template:
   Scope, Coverage Rating, Resource Coverage, Next Steps, Trail Inventory,
   Findings, Check Matrix, What Auditors Should Know, Not Assessed.
9. The data source label is present and matches how the data was obtained.
10. No internal tool names, employee aliases, Agent Space ids, or account ids
    other than the one under review and its management account.
11. No dollar figure, saving estimate, or the words "redundant", "paid copy"
    or "wasteful" about any trail or store. A second copy is stated as a count
    and handed to `cloudtrail-cost-optimization`.
12. Every organization trail whose selectors were not read has its full ARN
    and the CLI command in Next Steps.
13. No instruction to a parent agent or other text addressed to anyone but the
    user appears anywhere in the report; line 1 is the title.
14. Every `Covered` row whose selector carries a narrowing keeps the label in
    the state cell, and D1 to D3 show `PASS (narrowed)` rather than `PASS` when
    any row of that type is narrowed.
15. In `SUPPLIED DATA` mode the account id in the title is one that appears in
    the supplied data, or the title says `account: not supplied`.
