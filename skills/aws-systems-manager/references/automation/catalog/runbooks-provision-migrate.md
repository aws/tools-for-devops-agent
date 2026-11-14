# Provision, migrate or replatform workloads (tutorial / setup runbooks)

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSMigration-VerifyTags` | read-only | — | Verify a list of tags on a given instance | `InstanceId`, `TagsToVerify` |  |
| `AWSMigrationHub-MGNRehostAutomation` | read-only | — | SSM Automation document to automate rehost migration of source servers using MGN Connector | `ActionType`, `WaveARN` |  |
| `AWS-CreateWorkspace` | mutating-reversible | AWS::WorkSpaces::Workspace | Create Amazon Workspace. By default, only one WorkSpace per user per directory is allowed. | `BundleId`, `DirectoryId`, `UserName` |  |
| `AWS-InstallDistributorPackageOnAzure` | mutating-reversible | — | Install or uninstall an SSM Distributor package on an Azure VM using OIDC federation via a CloudConnector. Fetches the package manifest from SSM, downloads the ZIP, and runs install/uninstall scripts on the VM via Azure Managed RunCommand. | `AzureVmResourceId`, `CloudConnector` |  |
| `AWS-SetupJupyter` | mutating-reversible | AWS::EC2::Instance | Configures Jupyter notebook on the targeted Amazon Linux instances according to AWS recommendations. For more info refer to: https://docs.aws.amazon.com/dlami/latest/devguide/setup-jupyter-config.html | `JupyterPasswordSSMKey` |  |
| `AWSDocs-ClassicLoadBalancerSSMDocument` | mutating-reversible | — | Tutorial: Create a Classic Load Balancer === This Automation document sets up a Classic Load Balancer for an EC2 instance. It Automates the Create a Classic Load Balancer Tutorial. | — | failure branch |
| `AWSDocs-InstallALAMPServer-AL` | mutating-reversible | — | Tutorial: Install a LAMP Web Server with the Amazon Linux AMI === | — | failure branch |
| `AWSDocs-InstallALAMPServer-AL2` | mutating-reversible | — | Tutorial: Install a LAMP Web Server on Amazon Linux 2 === | — | failure branch |
| `AWSDocs-S3StaticWebsite` | mutating-reversible | — | Tutorial: Configuring a static website on S3 === | — | failure branch |
| `AWSDocs-S3StaticWebsiteCustomDomain` | mutating-reversible | — | Tutorial: Configuring a static website using a custom domain registered with Route 53 === | `RootDomainName` | failure branch |
| `AWSDocs-ScaleLoadBalanced` | mutating-reversible | — | Tutorial: Set up a scaled and load-balanced application === | `SubnetId` | failure branch, 3× onFailure:Continue |
| `AWSMigration-CreateLoadBalanceAutoScaleGroup` | mutating-reversible | — | Creates an AMI from an existing EC2 instance, and then sets up an internet-facing load balancer with an autoscale group to launch EC2 instances from that AMI. The autoscale group will scale up and down based on the CPU levels of each EC2 instance within it | `HealthCheckPath`, `InstanceId`, `KeyName`, `SubnetA`, `SubnetB`, `VpcId` | failure branch |
| `AWSMigration-VerifySqlAWSSubscription` | mutating-reversible | — | Verifies that your instance has the right usage operation per your Microsoft SQL Server edition. This document is only supported for Windows machines. | `InstanceId` |  |
| `AWS-CreateDSManagementInstance` | destructive | AWS::EC2::Instance | Creates an AWS Directory Service Windows Management instance. This document will create an Amazon EC2 instance running the Microsoft Windows Server 2019 base AMI. | — | failure branch, 17× onFailure:Continue |
| `AWSDocs-Configure-SSL-TLS-AL` | destructive | — | Tutorial: Configuring SSL/TLS with Amazon Linux === | — | failure branch, runs child automations |
| `AWSDocs-Configure-SSL-TLS-AL2` | destructive | — | Tutorial: Configuring SSL/TLS with Amazon Linux 2 === | — | failure branch, runs child automations |
| `AWSDocs-HostingAWordPressBlog-AL` | destructive | — | Tutorial: Hosting a WordPress Blog with Amazon Linux === | — | failure branch, runs child automations |
| `AWSDocs-HostingAWordPressBlog-AL2` | destructive | — | Tutorial: Hosting a WordPress Blog with Amazon Linux 2 === | — | failure branch, runs child automations |
| `AWSRefactorSpaces-CreateResources` | destructive | — | Accelerates refactoring by creating a Migration Hub Refactor Spaces environment and routing to an EC2 instance. Required permissions: https://docs.aws.amazon.com/migrationhub-refactor-spaces/latest/userguide/security-iam-awsmanpol.html#SSMAutomationPolicy | `ApplicationName`, `InstanceId`, `Port`, `Protocol`, `ServiceName`, `UriPath` | failure branch |
| `AWSSupport-CloneXenEC2InstanceAndMigrateToNitro` | destructive | AWS::EC2::Instance | Clones, prepares and migrates the cloned Amazon EC2 Linux instance, currently running on Amazon EC2 Xen platform, to run on Amazon EC2 Nitro platform. This automation is divided into three different branches, details of which are as follows | `Acknowledgement`, `ApproverIAM`, `SNSTopicArn`, `TargetInstanceId` | approval step, failure branch, 3× onFailure:Continue, deletes files in guest |
