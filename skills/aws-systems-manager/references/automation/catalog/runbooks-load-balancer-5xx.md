# Load balancer 5XX errors, unhealthy targets, health checks failing

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

| Runbook | Tier | Target type | What it does | Required parameters | Notes |
|---|---|---|---|---|---|
| `AWSSupport-TroubleshootALB5XXErrors` | read-only | — | Provides comprehensive diagnosis and troubleshooting for Application Load Balancer (ALB) HTTP 5XX errors by analyzing CloudWatch metrics and access logs to identify root causes and provide actionable recommendations. | `ALBArn`, `IssueEndTime`, `IssueStartTime` | 7× onFailure:Continue |
| `AWSSupport-TroubleshootELBHealthChecks` | read-only | — | Helps troubleshoot AWS Elastic Load Balancing (ELB) health check issues by analyzing its related Amazon CloudWatch metrics, verifying network connectivity, and executing diagnostic commands on its target instances. | `ExecutionMode`, `LoadBalancerOrTargetGroupName` | 6× onFailure:Continue |
| `AWS-EnableCLBConnectionDraining` | mutating-reversible | — | Enable connection draining on a Classic Load Balancer (CLB) to the specified timeout value using the ModifyLoadBalancerAttributes API. | `LoadBalancerName` |  |
| `AWS-UpdateALBDesyncMitigationMode` | mutating-reversible | — | Update the desync mitigation mode on an Application Load Balancer (ALB) to the specified mitigation mode using ModifyLoadBalancerAttributes API. The desync mitigation mode determines how the load balancer handles requests that might pose a security risk to your application. | `DesyncMitigationMode`, `LoadBalancerArn` |  |
| `AWS-UpdateCLBDesyncMitigationMode` | mutating-reversible | — | Update the desync mitigation mode on a Classic Load Balancer (CLB) to the specified mitigation mode using ModifyLoadBalancerAttributes API. The desync mitigation mode determines how the load balancer handles requests that might pose a security risk to your application. | `DesyncMitigationMode`, `LoadBalancerName` |  |
| `AWSSupport-TroubleshootAWSECSHealthChecks` | mutating-reversible | — | The TroubleshootAWSECSHealthChecks automation runbook helps diagnose and troubleshoot issues where Amazon Elastic Container Service (Amazon ECS) tasks running on Amazon Elastic Compute Cloud (Amazon EC2) instances or AWS Fargate fail Application Load Balancer (ALB) health checks. | `ECSClusterName`, `ECSServiceName` | failure branch |
