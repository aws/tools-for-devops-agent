# Restart, stop, start, resize or replace an EC2 instance or Auto Scaling group

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWS-ASGEnterStandby` | mutating-reversible | AWS::EC2::Instance | Change the Standby state of an EC2 instance in an autoscaling group | `InstanceId` |  |
| `AWS-ASGExitStandby` | mutating-reversible | AWS::EC2::Instance | Change the Standby state of an EC2 instance in an autoscaling group | `InstanceId` |  |
| `AWS-CreateManagedLinuxInstance` | mutating-reversible | AWS::EC2::Instance | Creates a Linux Managed Instance | `AmiId`, `KeyPairName` |  |
| `AWS-CreateManagedLinuxInstanceWithApproval` | mutating-reversible | AWS::EC2::Instance | Creates a Linux Managed Instance with approval | `AmiId`, `Approvers`, `KeyPairName`, `SNSTopicArn` | approval step |
| `AWS-CreateManagedWindowsInstance` | mutating-reversible | AWS::EC2::Instance | Creates a Windows Managed Instance | `KeyPairName` |  |
| `AWS-CreateManagedWindowsInstanceWithApproval` | mutating-reversible | AWS::EC2::Instance | Creates a Windows Managed Instance with approval | `Approvers`, `KeyPairName`, `SNSTopicArn` | approval step |
| `AWS-ResizeInstance` | mutating-reversible | AWS::EC2::Instance | Resize an EC2 instance | `InstanceId`, `InstanceType` | failure branch |
| `AWS-RestartEC2Instance` | mutating-reversible | AWS::EC2::Instance | Restart EC2 instances(s) | `InstanceId` |  |
| `AWS-RestartEC2InstanceWithApproval` | mutating-reversible | AWS::EC2::Instance | Restart EC2 instances(s) with approval | `Approvers`, `InstanceId`, `SNSTopicArn` | approval step |
| `AWS-StartEC2Instance` | mutating-reversible | AWS::EC2::Instance | Start EC2 instances(s) | `InstanceId` |  |
| `AWS-StartEC2InstanceWithApproval` | mutating-reversible | AWS::EC2::Instance | Start EC2 instances(s) with approval | `Approvers`, `InstanceId`, `SNSTopicArn` | approval step |
| `AWS-StopEC2Instance` | mutating-reversible | AWS::EC2::Instance | Stop EC2 instances(s) | `InstanceId` | 1× onFailure:Continue |
| `AWS-StopEC2InstanceWithApproval` | mutating-reversible | AWS::EC2::Instance | Stop EC2 instances(s) with approval | `Approvers`, `InstanceId`, `SNSTopicArn` | approval step |
| `AWSQuickSetupType-Scheduler-ApplyInstanceState` | mutating-reversible | — | Finds EC2 instances with specified tags and starts or stops them based on the InstanceState parameter, but only when the change calendar state matches the ExpectedCalendarState. | `ChangeCalendarName`, `ExpectedCalendarState`, `InstanceState`, `TagKey`, `TagValue` |  |
| `AWSQuickSetupType-Scheduler-ChangeCalendarState` | mutating-reversible | — | Starts the State Manager Associations immediately and only one time. | `AssociationIDs` |  |
| `AWSResilienceHub-RebootEc2InstanceSOP_2020-05-20` | mutating-reversible | — | Reboot an Amazon EC2 instance. | `EC2InstanceIdentifier` |  |
| `AWSResilienceHub-ScaleOutAsgSOP_2020-07-01` | mutating-reversible | — | Scale out an Amazon EC2 Auto Scaling group increasing the number of Amazon EC2 instances. | `AutoScalingGroupName` |  |
| `AWSResilienceHub-ScaleUpEc2SOP_2020-05-20` | mutating-reversible | — | Scale up an Amazon EC2 instance to a larger version of the same instance type. For example, instead of m5.xlarge, the Amazon EC2 instance will utilize m5.2xlarge. | `EC2InstanceIdentifier` |  |
| `AWSSupport-CheckXenToNitroMigrationRequirements` | mutating-reversible | AWS::EC2::Instance | Checks for the pre-requisites to migrate a Xen based EC2 Linux instance to EC2 Nitro platform by performing the following checks | `InstanceId` | 4× onFailure:Continue, deletes files in guest |
| `AWS-TerminateEC2Instance` | destructive | AWS::EC2::Instance | Terminate EC2 instances(s) | `InstanceId` |  |
| `AWS-TerminateEC2InstanceWithApproval` | destructive | AWS::EC2::Instance | Terminate EC2 instances(s) with approval | `Approvers`, `InstanceId`, `SNSTopicArn` | approval step |
| `AWSResilienceHub-ScaleUpAsgSOP_2020-07-01` | destructive | — | Modify an Amazon EC2 ASG's instances to utilize a larger version of the same instance type. For example, instead of m5.xlarge, Amazon EC2 ASG instances will utilize m5.2xlarge. | `AutoScalingGroupName` |  |
| `AWSSupport-CopyEC2Instance` | destructive | AWS::EC2::Instance | Provides an automated solution for the procedure outlined in the Knowledge Center article How do I move my EC2 instance to another subnet, Availability Zone, or VPC?. The automation branches depending on the values you specify for the Region and SubnetId parameters. | `InstanceId` | failure branch, 1× onFailure:Continue |
| `AWSSupport-MigrateXenToNitroLinux` | destructive | AWS::EC2::Instance | Clones, prepares, and migrates the target EC2 Linux instance currently running on EC2 Xen platform, to run on EC2 Nitro platform. This automation runbook provides two different Operation Types as input parameter: Clone&Migrate and FullMigration. | `Acknowledgement`, `ApproverIAM`, `OperationType`, `SNSTopicArn`, `TargetInstanceId` | approval step, failure branch, 2× onFailure:Continue, runs child automations |
