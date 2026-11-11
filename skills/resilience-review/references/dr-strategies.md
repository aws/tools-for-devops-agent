# DR strategies: choosing one

Detail for the strategy table in SKILL.md Step 4.

## The four strategies

From the AWS Well-Architected Framework, Reliability pillar, REL13-BP02. They are
listed in increasing order of cost and complexity, and decreasing RPO and RTO.

| Strategy | RPO | RTO | Recovery Region holds |
|---|---|---|---|
| Backup and restore | hours | 24 hours or less | backups of data and applications; infrastructure is redeployed with IaC at recovery time |
| Pilot light | minutes | tens of minutes | a copy of core infrastructure; data replicated and backed up there; databases and object storage on; app servers and serverless compute not deployed |
| Warm standby | seconds | minutes | a scaled-down but fully working copy, always on; scaled up at recovery |
| Multi-site active/active | near zero | potentially zero | the full workload, serving traffic in several Regions |

Notes from the same source:

- Point-in-time recovery (continuous backups) can lower backup-and-restore RPO to
  as little as about 5 minutes in some cases.
- Pilot light cannot process requests until you take action (start servers,
  deploy non-core infrastructure, scale up). Warm standby can handle traffic at
  reduced capacity right away. When warm standby is fully scaled it is called hot
  standby. The DR whitepaper files hot standby under multi-site: an active/passive
  setup where the recovery Region holds the full workload but takes no traffic
  until failover. Use it when a sheet or team asks for five labels.
- Active/active must avoid or handle conflicting writes to the same record in two
  Regions.
- Choosing a strategy is a trade-off between downtime, data loss and cost. Avoid a
  strategy that is stricter than the workload needs.

## How to map targets to a strategy

1. Take the strictest RPO and RTO in the tier.
2. Pick the first row in the table that meets both.
3. If the RPO fits a cheaper row than the RTO (or the other way round), the
   stricter one decides.
4. Different tiers can use different strategies. A rebuildable cache can stay on
   backup and restore (or nothing) while the database uses pilot light.

Worked example: RPO 15 minutes and RTO 1 hour for customer and order data. Backup
and restore is too slow on RTO for most databases. Pilot light (RPO minutes, RTO
tens of minutes) meets both. Warm standby also meets them but costs more, so it is
not the answer unless there is another reason.

## Building the tiers

Make a small table per workload: tier, data stores, RPO, RTO. For each workload,
ask (REL13-BP01):

1. What is the longest it can be down before the business impact is unacceptable?
2. What kind of impact: financial, reputational, operational, regulatory?
3. How much data can be lost before the impact is unacceptable?
4. Can lost data be recreated from other sources (derived data)?
5. What are the recovery targets of the things this workload depends on? It cannot
   recover faster than they do.
6. What depends on this workload? Upstream needs can make its targets stricter.

## Rebuildable data

A store is rebuildable when its contents can be recreated from a source of truth:
caches filled from a database, search indexes, materialized views. For these:

- Protecting against data loss is usually not needed.
- What matters is that the application keeps working on an empty or cold store
  and that the store can be recreated in the recovery Region in time.

Confirm with the user before treating a store as rebuildable. Session stores,
counters and rankings kept only in a cache are sometimes the only copy.

## Bad data needs its own protection

Replication does not help against bad data (SKILL.md Step 1). Point-in-time
recovery helps against Region loss only if copies exist outside the Region. Copies
in a separate account are what protect against a compromised account or
ransomware.

## Choosing the recovery Region

If the user has not picked a recovery Region, propose one and say why. Check:

1. **Data residency.** Laws, contracts or internal policy may require the copy to
   stay in a country or in the EU. Ask if you do not know. Check which country each
   candidate Region is in: not every Region in Europe is in the EU (for example
   Europe (London) and Europe (Zurich)).
2. **Latency to users.** A Region close to the users keeps the application usable
   after failover.
3. **Service and feature availability.** Every service and feature the workload
   uses must exist there, including the DR features themselves (for example
   ElastiCache Global Datastore Regions, RDS cross-Region automated backup Region
   pairs from `rds:DescribeSourceRegions`). Verify with the AWS regional
   availability information; do not assume.
4. **Quotas and capacity.** Service quotas in the recovery Region are separate from
   the primary Region. Point to the `service-quota-check` skill.
5. **Independence.** The recovery Region should not share the failure you are
   planning for.
6. **Cost.** Prices differ between Regions; name the difference only if you checked.

Only state facts about a Region (launches, services, partnerships) that you have
verified in this session.

## Sources

- AWS Well-Architected Framework, REL13-BP01 Define recovery objectives:
  https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_planning_for_recovery_objective_defined_recovery.html
- AWS Well-Architected Framework, REL13-BP02 Use defined recovery strategies:
  https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_planning_for_recovery_disaster_recovery.html
- Disaster Recovery of Workloads on AWS, Disaster recovery options in the cloud:
  https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html
- AWS Prescriptive Guidance, Resilience analysis framework:
  https://docs.aws.amazon.com/prescriptive-guidance/latest/resilience-analysis-framework/overview.html
