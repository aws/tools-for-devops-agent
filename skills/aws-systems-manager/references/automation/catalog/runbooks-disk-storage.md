# Disk full / EBS volume or EFS capacity, performance or attachment problem

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSSupport-AnalyzeEBSResourceUsage` | read-only | — | Analyze resource usage on Amazon Elastic Block Store (Amazon EBS). It analyzes volume usage and identifies abandoned volumes, images, and snapshots in a given AWS Region. | — | failure branch |
| `AWS-AttachEBSVolume` | mutating-reversible | AWS::EC2::Volume | Attach EBS Volume | `Device`, `InstanceId`, `VolumeId` |  |
| `AWS-DetachEBSVolume` | mutating-reversible | AWS::EC2::Volume | Detach EBS Volume | `VolumeId` |  |
| `AWS-ExtendEbsVolume` | mutating-reversible | AWS::EC2::Instance | Extends EBS Volume | `SizeGib`, `VolumeId` |  |
| `AWSResilienceHub-ChangeEFSProvisionedThroughputSOP_2020-10-26` | mutating-reversible | — | Change EFS file system's provisioned throughput | `FileSystemID`, `ProvisionedThroughput` |  |
| `AWSResilienceHub-IncreaseVolumeSizeEbsSOP_2020-05-26` | mutating-reversible | — | The following use cases are not supported by this SOP | `DeviceName`, `InstanceIdentifier`, `Partition`, `SizeGib` |  |
| `AWSSupport-CalculateEBSPerformanceMetrics` | mutating-reversible | — | Helps diagnose Amazon Elastic Block Store (Amazon EBS) performance issues by calculating and publishing performance metrics to an Amazon CloudWatch dashboard. The dashboard displays the estimated average IOPS and throughput for a target Amazon EBS volume or all the volumes attached to the target Amazon Elastic Compute Cloud (Amazon EC2) instance. | `EndTime`, `ResourceId`, `StartTime` |  |
| `AWSSupport-CheckAndMountEFS` | mutating-reversible | — | Verifies the prerequisites to mount your Amazon Elastic File System (Amazon EFS) file system and mounts the file system on the Amazon Elastic Compute Cloud (Amazon EC2) instance you specify. This runbook supports mounting your Amazon EFS file system with the DNS name, or using the mount target's IP address. | `EfsId`, `InstanceId`, `Region` |  |
