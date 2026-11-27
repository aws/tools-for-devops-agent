# AWS evidence and supplementary checks

Load in Step 3. The AWS-E reads collect evidence for the CIS controls and for the AWS-n checks below. The AWS-n checks cover controls that the frameworks in the crosswalk need and the CIS benchmark does not grade. AWS-1 to AWS-3 follow Security Hub EKS controls EKS.8, EKS.2, and EKS.9.

## Evidence reads

Run each with `use_aws` in the cluster's region. Every action is read-only and covered by the `AIDevOpsAgentAccessPolicy` managed policy.

| # | Read | Keep |
|---|---|---|
| AWS-E1 | `eks describe-cluster --name <cluster>`, `eks list-access-entries`, `eks list-pod-identity-associations` | `version`, `platformVersion`, `logging.clusterLogging`, `encryptionConfig`, `resourcesVpcConfig` (endpoint flags, `publicAccessCidrs`, subnets), `accessConfig.authenticationMode`, `upgradePolicy.supportType`, access entry principal ARNs, Pod Identity associations |
| AWS-E2 | `eks list-nodegroups`, `eks describe-nodegroup` per group, `ec2 describe-subnets` for their subnets, `ec2 describe-instances` filtered by tag `kubernetes.io/cluster/<cluster>` | node group version, AMI type, release version, launch template, subnets with `MapPublicIpOnLaunch`, instance public IPs |
| AWS-E3 | `eks describe-cluster-versions --cluster-versions <version>` | `versionStatus` (`STANDARD_SUPPORT`, `EXTENDED_SUPPORT`, or `UNSUPPORTED`), `endOfStandardSupportDate`, `endOfExtendedSupportDate` |
| AWS-E4 | `iam list-attached-role-policies` and `iam list-role-policies` for each node role | policy names; for inline policies, `iam get-role-policy` to find ECR write actions |
| AWS-E5 | `inspector2 list-coverage` filtered to `AWS_ECR_REPOSITORY` and `AWS_ECR_CONTAINER_IMAGE`, `inspector2 list-findings` filtered to `CRITICAL` and `HIGH` ECR image findings. Follow `nextToken` until it is empty, or filter by the repository names of the running images so one page is enough | scan status per repository; finding count, CVE ID, package, and image digest for images running in the cluster |
| AWS-E6 | `guardduty list-detectors`, `guardduty get-detector` | status of features `EKS_AUDIT_LOGS` and `RUNTIME_MONITORING` (with `EKS_ADDON_MANAGEMENT`) |
| AWS-E7 | `eks list-addons`, `eks describe-addon` for `vpc-cni` | add-on versions, `configurationValues` |
| AWS-E8 | `elbv2 describe-load-balancers`, `elbv2 describe-tags`, `elbv2 describe-listeners` | load balancers tagged `elbv2.k8s.aws/cluster=<cluster>` or `kubernetes.io/cluster/<cluster>`, their scheme, and listener protocols and default actions |
| AWS-E9 | `logs describe-log-groups --log-group-name-prefix /aws/eks/<cluster>/cluster` | `retentionInDays` |
| AWS-E10 | `cloudtrail describe-trails`, `cloudtrail get-trail-status` | whether a multi-Region trail is logging |
| AWS-E11 | `ec2 describe-launch-template-versions` for node group launch templates, `ec2 describe-volumes` for node instance volumes | `Encrypted` on root and data volumes; IMDS `HttpTokens` and `HttpPutResponseHopLimit` |
| AWS-E12 | `backup list-protected-resources` and `backup list-backup-plans` | whether EKS (`resourceType=EKS`) or the cluster's EBS volumes are protected |

If a read is denied, record the error and mark every check that depends on it `Not assessed`.

## Supplementary checks

| ID | Check | Evidence | Pass rule |
|---|---|---|---|
| AWS-1 | Audit logging enabled (Security Hub EKS.8) | AWS-E1 | PASS if the `audit` log type is enabled. |
| AWS-2 | Cluster on a standard-support Kubernetes version (Security Hub EKS.2) | AWS-E1, AWS-E3 | PASS if `versionStatus` is `STANDARD_SUPPORT`. FAIL if it is in extended support or past end of support, with the date from AWS-E3. Read the support status at runtime; never use a remembered version list. |
| AWS-3 | Node groups on a standard-support Kubernetes version (Security Hub EKS.9) | AWS-E2, AWS-E3 | FAIL lists node groups whose version is in extended support or unsupported. |
| AWS-4 | Threat detection for EKS | AWS-E6 | PASS if GuardDuty is enabled with `EKS_AUDIT_LOGS` and `RUNTIME_MONITORING` covering EKS. FAIL if GuardDuty is off. `Manual review` if only one feature is on. |
| AWS-5 | Account activity logging | AWS-E10 | PASS if a multi-Region CloudTrail trail is logging. |
| AWS-6 | Vulnerability posture of running images | AWS-E5, K6 | FAIL if Inspector has `CRITICAL` or `HIGH` findings for images running in this cluster. List up to 10 with CVE ID and package exactly as Inspector reports them. PASS if scanning covers the running images and no such findings exist. `Not assessed` if scanning is off, or if no running non-system image comes from this account's ECR (name the registries instead). State that AWS-hosted add-on images are not covered by customer Inspector findings. |
| AWS-7 | Node volume encryption | AWS-E11 | PASS if every node root and data volume is encrypted. FAIL lists unencrypted volumes. |
| AWS-8 | Node IMDSv2 enforced | AWS-E11 | PASS if node launch templates or instances set `HttpTokens=required`. FAIL lists node groups that allow IMDSv1. |
| AWS-9 | Backup of cluster state or persistent volumes | AWS-E12 | PASS if AWS Backup protects the cluster or its EBS volumes, or a Velero Deployment runs in the cluster. Otherwise `Manual review` asking how the cluster and its data are restored. |

## Version and support facts

Never hardcode Kubernetes version numbers, support end dates, or the oldest supported version. Read them from AWS-E3 each run and quote the date it returns.
