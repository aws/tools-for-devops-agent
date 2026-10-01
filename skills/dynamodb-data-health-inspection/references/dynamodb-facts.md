# DynamoDB Facts

Load-bearing mechanics for the four dimensions this skill assesses. **Read this before
explaining how any DynamoDB limit, API, or background process behaves.**

Every fact below is cited to AWS documentation, and every "**Do not say**" is a claim
observed in validation — a real answer that got the finding right and then described the
mechanism wrongly. These are not hypothetical traps.

The rule this file exists to serve: a correct finding with a fabricated mechanism is still a
harmful answer. If you need a mechanism fact that is not here and not in another reference,
say you are not certain and name the check that would settle it.

---

## Item size and the 400 KB limit

**The limit is 400 KB, counting attribute *names* plus values, per item.**
→ [Constraints](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html)

**A write that would exceed 400 KB is rejected in full**, with
`ValidationException: Item size has exceeded the maximum allowed size`. DynamoDB stores the
item or it does not; there is no partial write and no truncation.

> **Do not say:** that an item is in a "partially written", "partially writable", or
> "fragile" state, or that a failed oversized write left damaged data behind. Nothing was
> written.

**An item larger than 400 KB therefore cannot exist in a table.** If an item is stored, it
was within the limit when written.

> **Do not say:** that an existing item is "already oversized" or "grandfathered" above
> 400 KB. The correct description of the situation customers hit is an item **at or near** the
> limit, where further growth is rejected.

**Reads never fail because of item size.** `GetItem`, `Query`, and `Scan` do not reject a
stored item for being too large — it could not have been stored if it were.

> **Do not say:** that `GetItem` rejects oversized items, or that reads "degrade" or "fail"
> due to item size. Large items cost more read capacity and reduce items-per-page; they do
> not cause read errors.

**Number sizing is efficient**, roughly one byte per two significant digits plus one. Lists
and maps add about 3 bytes per element, and maps also count each key name.

> **Do not say:** that Numbers carry surprising or outsized storage overhead. If a client's
> own size estimate disagrees with DynamoDB's, the usual causes are attribute names, nested
> element overhead, and counting characters instead of UTF-8 bytes.

**For tables that have LSIs**, the 400 KB limit covers the item's data in the table **plus**
its corresponding entries (key values and projected attributes) in **all** LSIs combined — so
the headroom for the base item is lower than 400 KB.
→ [Constraints — Item size for tables with Local Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html)

## Global secondary indexes

**GSI updates are asynchronous and eventually consistent.** A write to the base table is
propagated to its GSIs after the fact — normally within a fraction of a second, longer under
failure conditions.
→ [Using Global Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html)

> **Do not say:** that DynamoDB propagates writes to GSIs *synchronously*, or as part of the
> same write. The backpressure effect is real — see below — but the mechanism is not
> synchronous propagation.

**Strongly consistent reads are not supported on a GSI.** Querying a GSI with
`ConsistentRead: true` returns a `ValidationException`. LSIs *do* support them.

**GSI writes consume the index's own provisioned write capacity, not the base table's.**
Under-provisioning a GSI slows its updates and ultimately **causes writes to the base table to
fail** — this is the backpressure that explains "the table throttles but its own consumed
capacity looks low".
→ [How to design GSIs](https://aws.amazon.com/blogs/database/how-to-design-amazon-dynamodb-global-secondary-indexes/)

> **Do not say:** that a GSI's capacity cannot exceed the base table's, or that GSI writes are
> billed against the table. A GSI can be provisioned higher than its base table, and often
> should be.

**GSIs inherit the capacity *mode* from the base table** (provisioned vs on-demand), not the
amount. In provisioned mode each index is provisioned separately.

**During index creation you can modify index provisioned throughput, and it does affect the
backfill.** What does *not* help is Application Auto Scaling: raising its minimum will not
reduce index creation time.
→ [Managing GSIs — Phases of index creation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.OnlineOps.html)

> **Do not say:** that there is no way to provision throughput for a backfill, or no
> relationship between provisioned index capacity and backfill duration. Provisioning a high
> index WCU for a large backfill and lowering it afterwards is a legitimate, documented
> approach.

## Time to live

**TTL deletes expired items within a few days of expiry, without consuming write
throughput.** It is best-effort and asynchronous.
→ [Using TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)

> **Do not say:** "48 hours", or any other specific SLA figure. Older documentation used
> 48 hours; current documentation says **a few days**, and there is no committed deletion
> deadline. Do not invent a number to make the explanation feel precise.

**Deletion uses the table's backend capacity, not your provisioned capacity**, and runs only
when there is spare capacity — which is why a busy or very large table clears a backlog more
slowly.
→ [Why aren't expired TTL items deleted](https://repost.aws/knowledge-center/dynamodb-expired-ttl-not-deleted)

> **Do not say:** that TTL deletions consume your write capacity, or that they can be
> monitored via `ConsumedWriteCapacityUnits`. They do not appear there. The metric that does
> report them is `TimeToLiveDeletedItemCount`.

**In Global Tables, the delete in the expiry region consumes no WCU, but the replicated delete
consumes capacity in every replica region** — a replicated write unit under provisioned
capacity, or a replicated write request unit on-demand.

**A TTL attribute is only acted on if it is a `Number` holding Unix epoch time in seconds.**
Any other type is silently ignored. A value more than five years in the past is also ignored.

**Expired-but-not-yet-deleted items still appear in `Query` and `Scan` results** and still
count toward `ItemCount` and storage. Filter them out in read paths.

## Item collections and LSIs

**The 10 GB item collection limit applies only to tables that have LSIs.** All items sharing a
partition key, across the base table and every LSI, count toward it. Exceeding it fails
further writes to *that partition key* with `ItemCollectionSizeLimitExceededException`, while
other keys keep working.

**LSIs cannot be added or removed after table creation, and their projections cannot be
changed.** Moving off an LSI means a replacement table — or a restore with an index override,
below.

**GSIs are different: they can be added to or removed from an existing table at any time**, via
`UpdateTable` with `GlobalSecondaryIndexUpdates`. The table stays available while the new index
builds; it is queryable once `IndexStatus` reaches `ACTIVE`.
→ [Managing GSIs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.OnlineOps.html)

> **Do not say:** that adding a GSI requires creating a new table, or that GSI projections and
> LSI projections have the same immutability. A GSI's *projection* cannot be altered in place —
> you create a replacement index and delete the old one — but the index itself is freely
> addable and removable. Only LSIs are locked to table creation.

**A restore *can* exclude indexes.** `RestoreTableFromBackup` and
`RestoreTableToPointInTime` both accept `LocalSecondaryIndexOverride` and
`GlobalSecondaryIndexOverride`, and the documentation states you may exclude some or all
indexes at restore time.
→ [RestoreTableFromBackup](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_RestoreTableFromBackup.html)

> **Do not say:** that a restore must reproduce the source table's indexes, or that dropping
> an LSI requires a hand-built migration. Restore-with-override is the simpler documented path.

**LSIs have no index-scoped CloudWatch metrics.** Their activity is reported under the base
table, because they share its partitions. This is why this skill never reports an LSI as
unused — the data to support that claim does not exist.

## Partition-level throughput

**Every physical partition is capped at 1,000 WCU/s and 3,000 RCU/s** (or a linear
combination). A table can hold large aggregate capacity and still throttle when traffic
concentrates on one partition.

**Table-level and partition-level throttling are different causes** and the distinction
matters: an under-provisioned table throttles on its own capacity long before any partition
reaches its ceiling. Do not describe traffic concentrated on one key as a "hot partition" when
the table's provisioned capacity is itself the binding limit — check which cause-specific
throttle metric fired.

## When you are not certain

Say so, and name what would settle it. Preferred forms:

- "I can't confirm that from what I've collected — `<metric or API>` would show it."
- "That behaviour I'd want to verify against the DynamoDB documentation before relying on it."

Both are better than a confident mechanism that turns out to be wrong. In validation, the most
common harmful answer was not a wrong conclusion — it was a right conclusion wrapped in an
invented explanation.
