# CloudWatch Metric Lists (15-day window, `Period=21600` / 6h)

## Step 3b metrics

**RDS Instances** (dim `DBInstanceIdentifier`): DatabaseConnections (Max), FreeStorageSpace (Min), ReplicaLag (Max), MaximumUsedTransactionIDs (Maximum — PostgreSQL XID wraparound signal).
**Aurora Clusters** (dim `DBClusterIdentifier`): AuroraReplicaLag (Max), DatabaseConnections (Max), Deadlocks (Sum), EngineUptime (Min), MaximumUsedTransactionIDs (Maximum — Aurora PostgreSQL), TransactionAgeMaximum (Maximum — oldest active transaction age, Aurora MySQL 3.08+) and/or RollbackSegmentHistoryListLength (Maximum — InnoDB purge backlog, Aurora MySQL).

## Step 6a metrics

**RDS Instances** (dim `DBInstanceIdentifier`): CPUUtilization (Avg), FreeableMemory (Min), FreeStorageSpace (Min), ReadIOPS (Avg), WriteIOPS (Avg), ReadLatency (Avg), WriteLatency (Avg), DatabaseConnections (Max), SwapUsage (Avg), NetworkReceiveThroughput (Avg), NetworkTransmitThroughput (Avg).
**Aurora Clusters** (dim `DBClusterIdentifier`): CPUUtilization (Avg), FreeableMemory (Min), DatabaseConnections (Max), AuroraReplicaLag (Max), BufferCacheHitRatio (Avg), CommitLatency (Avg), ReadLatency (Avg), WriteLatency (Avg), VolumeReadIOPs (Sum), VolumeWriteIOPs (Sum), ServerlessDatabaseCapacity (Avg).

## Step 7b metrics

CPUUtilization (Avg), FreeableMemory (Min), DatabaseConnections (Max), ReadIOPS/WriteIOPS (Avg), VolumeBytesUsed (Avg), ServerlessDatabaseCapacity (Avg).
