# Automation runbook catalog

Catalog of the 485 AWS-owned Automation runbooks, generated from their document content as published on 2026-11-04. Do not edit by hand.

Availability and the default version differ by Region. Before recommending or starting a runbook, call `ssm:DescribeDocument` with `--name <runbook>` in the target Region and read its parameters from the response. If the call fails, the runbook is not available there.

Pick the category that matches the symptom, then open its file. Tier is derived from the runbook's steps: `read-only` makes no changes, `mutating-reversible` changes resources in ways that can be undone, `destructive` deletes, revokes or terminates something it did not create.

| Symptom | File | Runbooks | Read-only | Mutating | Destructive |
|---|---|---|---|---|---|
| EC2 instance unreachable: SSH/RDP fails, status checks failing, lost key or password | [references/automation/catalog/runbooks-ec2-unreachable.md](references/automation/catalog/runbooks-ec2-unreachable.md) | 12 | 0 | 11 | 1 |
| Instance not showing as managed in Systems Manager / Session Manager won't connect | [references/automation/catalog/runbooks-ssm-unmanaged-node.md](references/automation/catalog/runbooks-ssm-unmanaged-node.md) | 18 | 2 | 15 | 1 |
| Compromised instance, IAM principal or bucket: isolate / contain | [references/automation/catalog/runbooks-security-incident-containment.md](references/automation/catalog/runbooks-security-incident-containment.md) | 6 | 3 | 1 | 2 |
| Resource publicly exposed: public S3 bucket, open security group, public RDS/Redshift | [references/automation/catalog/runbooks-public-exposure.md](references/automation/catalog/runbooks-public-exposure.md) | 17 | 0 | 9 | 8 |
| Resilience / chaos test: inject a fault to verify alarms and recovery (non-production) | [references/automation/catalog/runbooks-resilience-testing.md](references/automation/catalog/runbooks-resilience-testing.md) | 44 | 0 | 0 | 44 |
| Clean up unused resources or reduce cost | [references/automation/catalog/runbooks-resource-cleanup-cost.md](references/automation/catalog/runbooks-resource-cleanup-cost.md) | 36 | 0 | 9 | 27 |
| Config rule / Security Hub finding: enable logging, encryption, monitoring, deletion protection | [references/automation/catalog/runbooks-logging-encryption-compliance.md](references/automation/catalog/runbooks-logging-encryption-compliance.md) | 109 | 5 | 99 | 5 |
| Disk full / EBS volume or EFS capacity, performance or attachment problem | [references/automation/catalog/runbooks-disk-storage.md](references/automation/catalog/runbooks-disk-storage.md) | 8 | 1 | 7 | 0 |
| Restart, stop, start, resize or replace an EC2 instance or Auto Scaling group | [references/automation/catalog/runbooks-instance-lifecycle.md](references/automation/catalog/runbooks-instance-lifecycle.md) | 24 | 0 | 19 | 5 |
| Patch, update or upgrade OS / agents / AMIs; patching failures | [references/automation/catalog/runbooks-patching-os.md](references/automation/catalog/runbooks-patching-os.md) | 20 | 2 | 15 | 3 |
| Network connectivity / DNS / VPN / endpoint reachability failure | [references/automation/catalog/runbooks-network-connectivity.md](references/automation/catalog/runbooks-network-connectivity.md) | 21 | 9 | 12 | 0 |
| Load balancer 5XX errors, unhealthy targets, health checks failing | [references/automation/catalog/runbooks-load-balancer-5xx.md](references/automation/catalog/runbooks-load-balancer-5xx.md) | 6 | 2 | 4 | 0 |
| Back up, snapshot, restore or recover data / AMIs | [references/automation/catalog/runbooks-backup-restore.md](references/automation/catalog/runbooks-backup-restore.md) | 39 | 4 | 28 | 7 |
| Access denied / IAM permission or credential problem | [references/automation/catalog/runbooks-iam-access.md](references/automation/catalog/runbooks-iam-access.md) | 7 | 2 | 3 | 2 |
| Collect logs or diagnostics for a support case or deeper analysis | [references/automation/catalog/runbooks-log-collection-diagnostics.md](references/automation/catalog/runbooks-log-collection-diagnostics.md) | 4 | 1 | 3 | 0 |
| Database unavailable, failover, restore or connection problem (RDS, Aurora, DynamoDB, DocumentDB, Redshift, SQL Server) | [references/automation/catalog/runbooks-database.md](references/automation/catalog/runbooks-database.md) | 15 | 1 | 12 | 2 |
| EKS / ECS cluster, node, pod or task failure | [references/automation/catalog/runbooks-containers.md](references/automation/catalog/runbooks-containers.md) | 17 | 1 | 15 | 1 |
| Lambda, API Gateway, SQS, SNS, Step Functions errors, throttling or misconfiguration | [references/automation/catalog/runbooks-serverless-api.md](references/automation/catalog/runbooks-serverless-api.md) | 24 | 2 | 20 | 2 |
| Managed application/service troubleshooting (Beanstalk, CodeDeploy, CloudFormation, OpenSearch, MWAA, Connect, S3 events) | [references/automation/catalog/runbooks-app-troubleshooting.md](references/automation/catalog/runbooks-app-troubleshooting.md) | 14 | 5 | 6 | 3 |
| Systems Manager / OpsCenter / Incident Manager / ITSM administration and integrations | [references/automation/catalog/runbooks-ops-management.md](references/automation/catalog/runbooks-ops-management.md) | 24 | 7 | 15 | 2 |
| Provision, migrate or replatform workloads (tutorial / setup runbooks) | [references/automation/catalog/runbooks-provision-migrate.md](references/automation/catalog/runbooks-provision-migrate.md) | 20 | 2 | 11 | 7 |
