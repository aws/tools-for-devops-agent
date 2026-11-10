# AWS Systems Manager Runbook Discovery

Find an Automation runbook that addresses an operational problem, confirm that it is available
where the problem is, and report what it would change. This chapter recommends runbooks. It never
starts one.

## When to use

- An investigation or mitigation reaches a step where a known fix might already exist as a
  runbook ("is there a runbook for this?").
- A user asks which runbook to use for a symptom, a resource type or a compliance finding.
- A user asks whether their account already has a runbook of its own for a task.

To start, monitor, stop or approve an execution, hand off to
[references/automation/execution.md](references/automation/execution.md). To review a runbook's content
for security problems, hand off to
[references/automation/hardening.md](references/automation/hardening.md).

## Workflow

Copy this checklist and work through it in order:

- [ ] Step 1: Describe the problem (symptom, resource type, identifier, account and Region)
- [ ] Step 2: Search the AWS-owned catalog and shortlist at most three runbooks
- [ ] Step 3: Confirm each shortlisted runbook with `describe-document` in the target Region
- [ ] Step 4: If nothing fits, search the account's own runbooks
- [ ] Step 5: Check the report, then present it

## Step 1: Describe the problem

Before searching, write down:

| Field | Example |
|---|---|
| Symptom, in operator terms | "SSH to the instance times out", "bucket is publicly readable" |
| Resource type | `AWS::EC2::Instance`, `AWS::S3::Bucket` |
| Resource identifier | the instance ID, bucket name, cluster name |
| Account and Region | where the affected resource is |
| Environment | production or not, if known |

If the Region is unknown, find it from the resource before continuing. Runbook availability and
versions differ by Region.

## Step 2: Search the AWS-owned catalog

1. Open [references/automation/catalog/runbook-catalog.md](references/automation/catalog/runbook-catalog.md). Pick the category whose
   symptom matches. If you only know the resource type, open
   [references/automation/catalog/runbooks-by-resource-type.md](references/automation/catalog/runbooks-by-resource-type.md) instead.
2. Open the category file and read the description of every runbook in it. The files are:

   | Symptom | File |
   |---|---|
   | EC2 instance unreachable: SSH/RDP fails, status checks failing, lost key or password | [references/automation/catalog/runbooks-ec2-unreachable.md](references/automation/catalog/runbooks-ec2-unreachable.md) |
   | Instance not showing as managed in Systems Manager / Session Manager won't connect | [references/automation/catalog/runbooks-ssm-unmanaged-node.md](references/automation/catalog/runbooks-ssm-unmanaged-node.md) |
   | Compromised instance, IAM principal or bucket: isolate / contain | [references/automation/catalog/runbooks-security-incident-containment.md](references/automation/catalog/runbooks-security-incident-containment.md) |
   | Resource publicly exposed: public S3 bucket, open security group, public RDS/Redshift | [references/automation/catalog/runbooks-public-exposure.md](references/automation/catalog/runbooks-public-exposure.md) |
   | Resilience / chaos test: inject a fault to verify alarms and recovery (non-production) | [references/automation/catalog/runbooks-resilience-testing.md](references/automation/catalog/runbooks-resilience-testing.md) |
   | Clean up unused resources or reduce cost | [references/automation/catalog/runbooks-resource-cleanup-cost.md](references/automation/catalog/runbooks-resource-cleanup-cost.md) |
   | Config rule / Security Hub finding: enable logging, encryption, monitoring, deletion protection | [references/automation/catalog/runbooks-logging-encryption-compliance.md](references/automation/catalog/runbooks-logging-encryption-compliance.md) |
   | Disk full / EBS volume or EFS capacity, performance or attachment problem | [references/automation/catalog/runbooks-disk-storage.md](references/automation/catalog/runbooks-disk-storage.md) |
   | Restart, stop, start, resize or replace an EC2 instance or Auto Scaling group | [references/automation/catalog/runbooks-instance-lifecycle.md](references/automation/catalog/runbooks-instance-lifecycle.md) |
   | Patch, update or upgrade OS / agents / AMIs; patching failures | [references/automation/catalog/runbooks-patching-os.md](references/automation/catalog/runbooks-patching-os.md) |
   | Network connectivity / DNS / VPN / endpoint reachability failure | [references/automation/catalog/runbooks-network-connectivity.md](references/automation/catalog/runbooks-network-connectivity.md) |
   | Load balancer 5XX errors, unhealthy targets, health checks failing | [references/automation/catalog/runbooks-load-balancer-5xx.md](references/automation/catalog/runbooks-load-balancer-5xx.md) |
   | Back up, snapshot, restore or recover data / AMIs | [references/automation/catalog/runbooks-backup-restore.md](references/automation/catalog/runbooks-backup-restore.md) |
   | Access denied / IAM permission or credential problem | [references/automation/catalog/runbooks-iam-access.md](references/automation/catalog/runbooks-iam-access.md) |
   | Collect logs or diagnostics for a support case or deeper analysis | [references/automation/catalog/runbooks-log-collection-diagnostics.md](references/automation/catalog/runbooks-log-collection-diagnostics.md) |
   | Database unavailable, failover, restore or connection problem (RDS, Aurora, DynamoDB, DocumentDB, Redshift, SQL Server) | [references/automation/catalog/runbooks-database.md](references/automation/catalog/runbooks-database.md) |
   | EKS / ECS cluster, node, pod or task failure | [references/automation/catalog/runbooks-containers.md](references/automation/catalog/runbooks-containers.md) |
   | Lambda, API Gateway, SQS, SNS, Step Functions errors, throttling or misconfiguration | [references/automation/catalog/runbooks-serverless-api.md](references/automation/catalog/runbooks-serverless-api.md) |
   | Managed application/service troubleshooting (Beanstalk, CodeDeploy, CloudFormation, OpenSearch, MWAA, Connect, S3 events) | [references/automation/catalog/runbooks-app-troubleshooting.md](references/automation/catalog/runbooks-app-troubleshooting.md) |
   | Systems Manager / OpsCenter / Incident Manager / ITSM administration and integrations | [references/automation/catalog/runbooks-ops-management.md](references/automation/catalog/runbooks-ops-management.md) |
   | Provision, migrate or replatform workloads (tutorial / setup runbooks) | [references/automation/catalog/runbooks-provision-migrate.md](references/automation/catalog/runbooks-provision-migrate.md) |

   Each file lists its runbooks with tier, target type, description, required parameters and notes. Shortlist at most three
   whose description matches the symptom and whose target type matches the resource.
3. Prefer, in this order:
   - a runbook that diagnoses before it changes anything (`read-only` tier, usually
     `AWSSupport-Troubleshoot*` or `AWS-Diagnose*`), when the cause is not yet known
   - a runbook that targets the exact resource type over one that is generic
   - a `*WithApproval` variant over the same runbook without an approval step, when one exists
4. Never choose a runbook in the `resilience-testing` category to fix a problem. Those runbooks
   inject faults on purpose.

If no runbook in the catalog fits, go to Step 4.

## Step 3: Confirm the runbook in the target Region

The catalog is a snapshot. Before recommending a runbook, confirm it with a live call in the
Region where the resource is:

```bash
aws ssm describe-document --name <runbook-name> --region <region>
```

- If the call returns `InvalidDocument`, the runbook isn't available in that Region. Drop it and
  try the next one on the shortlist.
- Check that `Document.Status` is `Active`.
- Read `Document.Parameters` from the response. Use these, not the catalog, as the parameter list:
  versions differ between Regions and parameters can change between versions.
- Read `Document.Description` and confirm it still matches the symptom.

To see which steps the runbook runs, call
`aws ssm get-document --name <runbook-name> --region <region>` and read `mainSteps`.

## Step 4: Search the account's own runbooks

Use this step when the AWS-owned catalog has no runbook for the problem, or when the user asks
about their own runbooks. Search the Automation runbooks the account owns, with keywords taken
from the symptom and the resource type:

```bash
aws ssm list-documents --region <region> \
  --filters Key=DocumentType,Values=Automation Key=Owner,Values=Self Key=SearchKeyword,Values=<keyword>
```

- Keep both filters: `DocumentType=Automation` limits the search to runbooks, and `Owner=Self`
  limits it to runbooks the account created.
- Try two or three keywords, one per call: the resource ("ec2", "bucket"), the action
  ("restart", "encrypt") and the symptom ("ssh", "disk").
- If the team tags its runbooks, also filter by tag with `Key=tag:<tag-key>,Values=<value>`.
- For every candidate, call `describe-document` and `get-document` as in Step 3. An account-owned
  runbook has no catalog entry, so work out its risk tier from its `mainSteps` using the table
  below.
- Don't search runbooks owned by other accounts. Nobody has reviewed them for this account, and
  running one gives code from another author the permissions of the role that runs it.

If neither search finds a runbook, say so and describe the manual fix instead.

## Step 5: Check the report

Before presenting the report, confirm each item:

- Every recommended runbook has a `describe-document` result from the target Region in this
  conversation, and the version you report is the one that call returned.
- The required parameters you list match `Document.Parameters` from that call, not the catalog.
- The tier matches the catalog entry, or, for an account-owned runbook, the calls in its
  `mainSteps`.
- No recommended runbook is a resilience test or is owned by another account.

Fix anything that doesn't hold before you answer.

## Gotchas

- The same runbook name can have a different default version, or not exist, in another Region.
- `SearchKeyword` matches part of the runbook name, case-insensitively, so search with short
  stems ("cert", "ssh") rather than full phrases.
- Runbooks named `*Test_*` in the `AWSResilienceHub-` family cause the failure they test.
- A runbook that runs a child runbook (`aws:executeAutomation`) can be more dangerous than its
  own steps suggest; its tier includes the child's.

## Risk tiers

Every runbook in the catalog has a tier, derived from the API calls and actions in its steps.

| Tier | Meaning | How to classify a runbook that isn't in the catalog |
|---|---|---|
| `read-only` | Reads and reports. Changes nothing. | Only `Describe*`, `Get*`, `List*` calls, `aws:assertAwsResourceProperty`, `aws:waitForAwsResourceProperty`, `aws:branch`, `aws:sleep` |
| `mutating-reversible` | Creates or modifies resources, or runs commands on an instance, in ways that can be undone | Any `Create*`, `Modify*`, `Put*`, `Update*`, `Start*`, `Stop*`, `Reboot*` call, `aws:runCommand`, `aws:executeScript` with such calls, deleting only resources the runbook itself created |
| `destructive` | Deletes, terminates, revokes or detaches something the runbook didn't create, or injects a fault on purpose | Any `Delete*`, `Terminate*`, `Revoke*`, `Remove*`, `Detach*`, `Deregister*` call on an existing resource, `aws:deleteStack`, `aws:deleteImage`, or a resilience test |

If a runbook runs a child runbook (`aws:executeAutomation`), its tier is the highest tier of
itself and its children.

## What to report

For each recommended runbook:

```
Runbook: <name>   (AWS-owned | account-owned)
Why it fits: <one sentence linking its description to the symptom>
Region check: describe-document in <region> returned Active, version <DocumentVersion>
Tier: <read-only | mutating-reversible | destructive> because <the calls that set the tier>
Required parameters: <name = value you would pass, or "needs input from the user">
Approval: <see below>
```

Approval, by tier:

- `read-only`: can be run as a diagnostic step.
- `mutating-reversible`: a person must approve the exact runbook, version, parameters and targets
  before it runs. Record the resource's current state first so the change can be reversed.
- `destructive`: recommend only. A person must run it themselves. For a resilience test, also
  confirm that the target isn't in production.

When a runbook will run against more than one resource, say that the execution should use rate
control (`MaxConcurrency`, `MaxErrors`) and an `AlarmConfiguration` that stops it when a health
alarm fires.

## Constraints

- Recommend only runbooks you confirmed with `describe-document` in the target Region.
- Don't hardcode or quote a version number from memory. Report the version the live call returned.
- Don't start an execution from this chapter.
- Don't recommend a runbook owned by another account.
- If the user's credentials can't call `ssm:DescribeDocument` or `ssm:ListDocuments`, say which
  permission is missing instead of recommending an unconfirmed runbook.
