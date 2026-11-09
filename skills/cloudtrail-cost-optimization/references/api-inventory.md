# Trail & Event Data Store Inventory APIs

Reference for the exact read-only API calls used to inventory trails and CloudTrail
Lake event data stores. Load this during Step 2 (Inventory) when you need the precise
API names and what each returns.

All calls are read-only (`Describe*`, `Get*`, `List*`).

```
cloudtrail.DescribeTrails (includeShadowTrails=true)   # all trails visible in the Region,
                                                        # including multi-Region shadow copies
cloudtrail.GetTrailStatus                               # is the trail logging? IsLogging
cloudtrail.GetTrail                                     # per-trail config
cloudtrail.GetEventSelectors                            # basic + advanced event selectors,
                                                        # read/write type, KMS/RDS exclusions,
                                                        # data event resource scope
cloudtrail.ListTrails                                   # enumerate across Regions
cloudtrail.ListEventDataStores / GetEventDataStore      # CloudTrail Lake stores: pricing
                                                        # option, retention period, multi-region,
                                                        # org enablement, event category
```

For organization scope, use `organizations.DescribeOrganization` and
`organizations.ListAccounts` to understand how many member accounts an Organizations
trail replicates into.

## What to capture per trail

Name, ARN, `IsMultiRegionTrail`, `IsOrganizationTrail`, `IsLogging`, home Region,
S3 destination bucket, whether it logs management events (and read/write type),
whether it logs data events (and their scope), and any KMS/RDS Data API exclusion.
