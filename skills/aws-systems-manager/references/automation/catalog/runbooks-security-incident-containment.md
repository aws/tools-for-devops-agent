# Compromised instance, IAM principal or bucket: isolate / contain

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSApp2Container-ReplatformApplications` | read-only | AWS::EC2:Instance | Analyze and extract .NET and Java applications running on migrated servers. Uses the provided Role to store artifacts and report in the Amazon S3 bucket. | `InstanceId`, `OutputLocation` | failure branch |
| `AWSSupport-ContainS3Resource` | read-only | — | Is designed to perform a containment of an Amazon Simple Storage Service (Amazon S3) bucket or object in response to a suspected or confirmed security issue. This runbook implements a containment process that helps isolate the target S3 resource while preserving its contents for further investigation. | `Action`, `BucketName` | failure branch |
| `AWSSupport-TroubleshootECSContainerInstance` | read-only | AWS::EC2::Instance | Helps troubleshooting an Amazon Elastic Compute Cloud (Amazon EC2) instance that fails to register with an Amazon Elastic Container Service (Amazon ECS) cluster. | `ClusterName`, `InstanceId` |  |
| `AWSSupport-ContainEC2Instance` | mutating-reversible | AWS::EC2::Instance | Is designed to perform a network containment of an Amazon Elastic Compute Cloud (Amazon EC2) instance in response to a suspected or confirmed security issue. This runbook implements a containment process that helps isolate the instance from network activity while leaving it running. | `Action`, `InstanceId` | failure branch, 1× onFailure:Continue |
| `AWS-QuarantineEC2Instance` | destructive | — | Automation document to isolate EC2 instance which are suspected of being compromised. | `InstanceId` |  |
| `AWSSupport-ContainIAMPrincipal` | destructive | — | Is designed to contain an AWS Identity and Access Management (IAM) user, role, or Identity Center user in response to a suspected or confirmed security issue related to the target IAM principal. This runbook implements a containment process that helps isolate the target IAM principal from performing actions within your AWS environment. | `Action`, `PrincipalName`, `PrincipalType` | failure branch |
