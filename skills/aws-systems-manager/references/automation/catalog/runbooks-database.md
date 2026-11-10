# Database unavailable, failover, restore or connection problem (RDS, Aurora, DynamoDB, DocumentDB, Redshift, SQL Server)

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSSupport-TroubleshootDMSTableErrors` | read-only | — | Is designed to automate the troubleshooting process for table errors in AWS Database Migration Service (AWS DMS). These errors occur when tables fail to migrate from the source endpoint to the target endpoint during Database Migration Tasks or Serverless Replications created in AWS DMS service. | `DMSArn` |  |
| `AWS-EnableDynamoDbAutoscaling` | mutating-reversible | — | Enable Application Autoscaling for an existing DynamoDB Table which is configured for provisioned capacity in order to maintain availability using the RegisterScalableTarget and PutScalingPolicy APIs. | `MaxReadCapacity`, `MaxWriteCapacity`, `MinReadCapacity`, `MinWriteCapacity`, `ReadScaleInCooldown`, `ReadScaleOutCooldown`, `TableName`, `TargetReadCapacityUtilization`, `TargetWriteCapacityUtilization`, `WriteScaleInCooldown`, `WriteScaleOutCooldown` |  |
| `AWS-RebootRdsInstance` | mutating-reversible | AWS::RDS::DBInstance | Reboot RDS Instance | `InstanceId` | failure branch |
| `AWS-StartRdsInstance` | mutating-reversible | AWS::RDS::DBInstance | Start RDS instance | `InstanceId` | failure branch |
| `AWS-StartStopAuroraCluster` | mutating-reversible | AWS::RDS::DBCluster | Starts or stops an Amazon Aurora DB cluster. | `ClusterName` |  |
| `AWS-StopRdsInstance` | mutating-reversible | AWS::RDS::DBInstance | Stop RDS instance | `InstanceId` | failure branch |
| `AWSResilienceHub-BacktrackRdsSOP_2020-04-01` | mutating-reversible | — | SOP to backtrack an RDS Aurora cluster. | `BacktrackTo`, `DbClusterIdentifier` |  |
| `AWSResilienceHub-CopyDynamoDBTablePropertiesUtil_2020-04-01` | mutating-reversible | — | Restore To Point In Time SOP | `DynamoDBTableSourceName`, `DynamoDBTableTargetName` |  |
| `AWSResilienceHub-CreateNewDocumentDBInstanceSOP_2020-09-21` | mutating-reversible | — | Used to create a new instance in a specified AZ/Region | `DBClusterIdentifier` |  |
| `AWSResilienceHub-PromoteDocumentDBReadReplicaSOP_2020-09-21` | mutating-reversible | — | Used to switch database to a read replica | `DBClusterIdentifier`, `DBInstanceReplicaIdentifier` |  |
| `AWSResilienceHub-ScaleUpDocumentDBClusterSOP_2020-09-21` | mutating-reversible | — | Scale up Amazon Document DB cluster. | `DBClusterIdentifier` |  |
| `AWSSQLServer-DBCC` | mutating-reversible | AWS::EC2::Instance | Performs database integrity checks (DBCC) on the specified SQL Server database. | `Database`, `InstanceId`, `SecretsMangerCredential`, `ThirdPartySoftwareConsent` | deletes files in guest |
| `AWSSQLServer-Index` | mutating-reversible | AWS::EC2::Instance | Performs SQL Server index maintenance operations on a specified database. | `Database`, `InstanceId`, `SecretsMangerCredential`, `ThirdPartySoftwareConsent` | deletes files in guest |
| `AWSResilienceHub-PromoteRdsReadReplicaSOP_2020-04-01` | destructive | — | SOP to recover an instance by promoting a replica to master in case of failure in the master instance. | `DbInstanceIdentifier` |  |
| `AWSResilienceHub-ScaleDownDocumentDBClusterSOP_2020-09-21` | destructive | — | Scale down Amazon Document DB cluster. | `DBClusterIdentifier` |  |
