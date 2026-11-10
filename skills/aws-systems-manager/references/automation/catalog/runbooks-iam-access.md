# Access denied / IAM permission or credential problem

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSSupport-TroubleshootIAMAccessDeniedEvents` | read-only | — | Helps in troubleshooting AWS Identity and Access Management (IAM) access denied issues found in AWS CloudTrail. The runbook queries AWS CloudTrail for recent access denied events related to the specified IAM entity (user or role) and AWS service event source. | `EventSource`, `RequesterArn` |  |
| `AWSSupport-TroubleshootSAMLIssues` | read-only | — | Helps diagnose Security Assertion Markup Language (SAML) related issues by analyzing SAML response files stored in an Amazon S3 bucket. It performs comprehensive validation including schema verification, signature validation, audience restriction checking, and expiration time verification. | `InputFileS3URI` |  |
| `AWSQuickSetupType-SetupJITNAResources` | mutating-reversible | — | Server Access Management enables users to utilize a cross-account and cross-region approach to approve session manager usage within an organization, this runbook creates the roles, sharing, and logging permissions to enable this workflow. | — |  |
| `AWSSupport-GrantPermissionsToIAMUser` | mutating-reversible | — | Grants the specified permissions to a new or existing AWS Identity and Access Management (IAM) group and adds the existing AWS IAM user to it. Policies you can choose from are: BillingFullAccess, SupportFullAccess or both. | `IAMGroupName`, `IAMUserName`, `Permissions` |  |
| `AWSSupport-TroubleshootRDSIAMAuthentication` | mutating-reversible | — | Helps troubleshoot Identity Access Management (IAM) database authentication issues for Amazon Relational Database Service (RDS) DB instances or an Amazon Aurora DB clusters. The runbook verifies the DB configuration and provides recommendations that could help you fix the configuration required for RDS IAM-based authentication. | `DBInstanceIdentifier`, `RDSType` | 1× onFailure:Continue, runs child automations |
| `AWS-DeleteIAMInlinePolicy` | destructive | — | Deletes all inline policies attached to IAM identities (users, groups, or roles). | `IamArns` |  |
| `AWSQuickSetupType-PropagateJustInTimeNodeAccessPolicies` | destructive | — | Automation runbook handles cross-account and cross-region sharing of SSM Just In Time Access policies. This runbook can only be run from the Delegated Admin account in the home region used for SSM Just In Time Access | — |  |
