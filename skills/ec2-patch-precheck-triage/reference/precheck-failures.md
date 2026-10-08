# Prerequisite-check failures (CheckPatchingPrerequisites)

The `AWSManagedServices-CheckPatchingPrerequisites` automation reports `"Precheck": "Failed"` with
one or more unhealthy fields. **Order matters** — fix connectivity and repo health first because
dependent checks auto-resolve or are skipped otherwise.

## Triage order
1. **Multiple checks failed?** Fix **connectivity first** (S3 endpoint, IMDS/`Ec2MetadataServiceStatus`,
   `AwsCredentialsStatusCode`) — dependent checks often clear on their own.
2. **`UpdateServiceConfigurationStatus = Not Healthy`?** Fix **repositories/subscription FIRST** — the
   `PackageManagerDryRunResult` check is *skipped* while this is unhealthy.
3. **`VolumeSpaceCriteria = Not Meet` on Windows?** Check **WMI health first** — a corrupt WMI
   repository gives a false disk-space reading. `winmgmt /verifyrepository` → salvage → reset.
4. Otherwise, remediate the single failing check.

## Key checks & fixes (the consolidated prerequisite matrix)
- **Repo/subscription** (Linux): RHUI client update (PAYG) / `subscription-manager register` (BYOL) /
  `yum clean all && makecache`; (Ubuntu) `apt-get update`; (SLES) `registercloudguest`/`suseconnect`.
- **Credentials/IMDS:** clear stale SSM vault + restart agent; remove iptables DROP to 169.254.169.254;
  attach an instance profile; raise IMDSv2 hop limit to 2 for containerized workloads.
- **S3 endpoint:** verify the S3 gateway endpoint policy allows the `aws-ssm-<region>` /
  `patch-baseline-snapshot-<region>` / `amazon-ssm-<region>` buckets, route table prefix list, SG 443, NACLs.
- **Disk space:** targeted cleanup of the full mount (package cache, logs, old kernels; Windows temp +
  `SoftwareDistribution\Download`, `DISM /StartComponentCleanup`); expand EBS as a last resort (customer coord).
- **Package-manager integrity:** `rpm --rebuilddb` / `dpkg --configure -a` + `apt-get install -f`.
- **Volume tag count:** AWS Backup pre-patch snapshot fails at 45+ tags — remove safe customer tags (not `aws:`/`ams:`/`Name`).
- **Windows WU service Disabled / endpoints / firewall / DisableWUA:** set `wuauserv` to Manual+start;
  reset/set WinHTTP proxy; `mpssvc` Automatic+start; remove `DisableWindowsUpdateAccess` (GPO may revert).

## Verify
Re-run the prechecks — the previously failing field returns its healthy value. Escalate after two
failed remediation attempts on the same check, or when customer coordination (reboot, disk expansion,
GPO/domain change) is required.
