# Check events and changes at the onset

A change that lines up with the onset is the leading hypothesis; confirm it with metrics.

## ElastiCache events

```
use_aws(service_name="elasticache", operation_name="describe_events",
        parameters={"SourceType": "replication-group", "SourceIdentifier": "<id>",
                    "StartTime": "<onset - 2h>", "EndTime": "<now>"})
```

Use `serverless-cache` or `cache-cluster` as the source type when that applies.
`DescribeEvents` returns up to 14 days of events, as message text. Look for messages
about a failover, a node replacement, a reboot, scaling, a snapshot or a parameter
change. Their SNS names are:

- `ElastiCache:FailoverComplete`
- `ElastiCache:CacheNodeReplaceStarted` and `ElastiCache:CacheNodeReplaceComplete`
- `ElastiCache:CacheNodesRebooted`
- `ElastiCache:ReplicationGroupScalingComplete` and `ElastiCache:ReplicationGroupScalingFailed`
- `ElastiCache:SnapshotComplete`
- `ElastiCache:CacheClusterParametersChanged`

On serverless, look for the "Cache limit approaching" notification for a slot near its
32 GiB limit.

## CloudTrail

Look up CloudTrail for `ModifyReplicationGroup`, `ModifyCacheParameterGroup`,
`ModifyServerlessCache`, `TestFailover` and security group changes in the window.
