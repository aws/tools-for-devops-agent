# Lambda, API Gateway, SQS, SNS, Step Functions errors, throttling or misconfiguration

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSSupport-TroubleshootAPIGatewayCustomDomainConfig` | read-only | — | Is designed to help you identify issues with your custom domain name configuration in Amazon API Gateway. The runbook analyzes the following configuration steps | `ApiId`, `DomainName` |  |
| `AWSSupport-TroubleshootLambdaS3Event` | read-only | — | Helps to troubleshoot issues with Amazon Simple Storage Service (Amazon S3) event notification configuration for AWS Lambda function. | `LambdaFunctionArn`, `S3BucketName` |  |
| `AWS-EnableCloudFormationStackSNSNotification` | mutating-reversible | — | Enables Amazon Simple Notification Service (SNS) using the UpdateStack API. A Standard SNS Topic can be integrated within a CloudFormation stack to notify stakeholders of any events or changes occurring with the stack. | `NotificationArn`, `StackName` |  |
| `AWS-PublishSNSNotification` | mutating-reversible | AWS::SNS::Topic | Publish SNS Notification | `Message`, `TopicArn` |  |
| `AWS-UpdateSQSPermissions` | mutating-reversible | — | Updates SQS queue encryption settings and resource-based policy permissions. If KMS encryption is enabled for a queue, the setting updates to use SQS-managed encryption. | `Principal`, `SQSQueueUrl` |  |
| `AWSDocs-LambdaWithS3SSMDocument` | mutating-reversible | — | Tutorial: Using Amazon Lambda with Amazon S3 === This Automation document sets up a Lambda function that is triggered when a new object is placed into S3. It Automates the Using Amazon Lambda with Amazon S3 Tutorial | — | failure branch |
| `AWSResilienceHub-ChangeHttpWsApiGwThrottlingSettingsSOP_2020-10-26` | mutating-reversible | — | Change throttling settings for HTTP or WebSocket types of API Gateway | `HttpWsApiGwId`, `HttpWsStageName`, `HttpWsThrottlingBurst`, `HttpWsThrottlingRate` |  |
| `AWSResilienceHub-ChangeLambdaConcurrencyLimitSOP_2020-10-26` | mutating-reversible | — | Change reserved concurrent executions limit of a Lambda function | `LambdaARN` |  |
| `AWSResilienceHub-ChangeLambdaExecutionTimeLimitSOP_2020-10-26` | mutating-reversible | — | Change execution time limit of a Lambda function | `LambdaARN`, `NewTimeoutValueSeconds` |  |
| `AWSResilienceHub-ChangeLambdaMemorySizeSOP_2020-10-26` | mutating-reversible | — | Change memory size of a Lambda function | `LambdaARN`, `NewMemorySizeValue` |  |
| `AWSResilienceHub-ChangeLambdaProvisionedConcurrencySOP_2020-10-26` | mutating-reversible | — | Change provisioned concurrency of a Lambda function | `LambdaARN`, `LambdaQualifier`, `ProvisionedConcurrentExecutions` |  |
| `AWSResilienceHub-ChangeRestApiGwQuotaLimitSOP_2020-10-26` | mutating-reversible | — | Change quota limit and period of the REST API Gateway | `ForceExecution`, `RestApiGwQuotaLimit`, `RestApiGwQuotaPeriod`, `RestApiGwUsagePlanId` |  |
| `AWSResilienceHub-ChangeRestApiGwThrottlingSettingsSOP_2020-10-26` | mutating-reversible | — | Change throttling settings of the REST API Gateway | `RestApiGwThrottlingBurst`, `RestApiGwThrottlingRate`, `RestApiGwUsagePlanId` |  |
| `AWSResilienceHub-EnableSNSTopicDLQSOP_2020-11-26` | mutating-reversible | — | Enable a dead-letter queue when it is not set up for a topic's subscription | `DeadLetterQueueArn`, `SubscriptionArn` |  |
| `AWSResilienceHub-MoveSQSMessagesBetweenQueuesSOP_2021-03-11` | mutating-reversible | — | Moves messages from one queue to another. Can be used to restore messages from Dead Letter queue back to main operation one or visa versa | `NumberOfMessagesToTransfer`, `SourceQueueUrl`, `TargetQueueUrl` |  |
| `AWSResilienceHub-SwitchLambdaVersionInAliasSOP_2020-10-26` | mutating-reversible | — | Switch alias of Lambda function to another version | `AliasName`, `LambdaARN`, `LambdaVersion` |  |
| `AWSResilienceHub-UpdateHttpWsApiGwVersionSOP_2020-10-26` | mutating-reversible | — | Update HTTP or WS API Gateway Stage deployment version | `HttpWsApiGwId`, `HttpWsStageName` |  |
| `AWSResilienceHub-UpdateRestApiGwVersionSOP_2020-10-26` | mutating-reversible | — | Update REST API Gateway Stage deployment version | `RestApiGwId`, `RestStageName` |  |
| `AWSSupport-RemediateLambdaS3Event` | mutating-reversible | — | Helps to troubleshoot and remediate Amazon Simple Storage Service (S3) event triggers for AWS Lambda. This document can troubleshoot and remediate the following scenarios: - "Unable to validate the following destination configurations" error. | `Action`, `LambdaFunctionArn`, `S3BucketName` | runs child automations |
| `AWSSupport-TroubleshootAPIGatewayHttpErrors` | mutating-reversible | — | Helps troubleshoot 5XX/4XX errors when invoking a deployed Amazon API Gateway REST API by: 1. Parsing access and/or execution logs 2. | `RestApiId`, `StageName` |  |
| `AWSSupport-TroubleshootAPIGatewayLambdaInvocation` | mutating-reversible | — | Helps you troubleshoot Amazon API Gateway integrations with AWS Lambda functions in HTTP and REST APIs, when used as an integration or as an authorizer. | `ApiId`, `HttpMethod`, `RouteIdOrResourceId`, `StageName` | failure branch |
| `AWSSupport-TroubleshootAWSBatchJob` | mutating-reversible | — | Helps you troubleshoot an AWS Batch Job that is stuck in RUNNABLE status. This automation checks the resources in the AWS Batch Compute Environments that are mapped to the job's queue by verifying the following prerequisites | `JobId` | failure branch, runs child automations |
| `AWSResilienceHub-PurgeSQSQueueSOP_2021-03-11` | destructive | — | Cleans up the given queue | `QueueUrl` |  |
| `AWSResilienceHub-ResubmitSNSTopicDeadLetterQueueSOP_2020-04-01` | destructive | — | Read Amazon SQS dead-letter queue and then re-submit the messages back to Amazon SNS. | `SubscriptionArn` |  |
