# Security — Check Definitions

> **Read `overview.md` first.** It holds the Severity Model, Status Values, the Evidence
> Guardrails (observed-data-only), and the public AWS API / `AWS/FSx` metric reference that
> govern every check below. Load this pillar file when you run this pillar's checks.

> **Resolving the file system's security groups (SEC-01, SEC-02, SEC-08).** FSx for NetApp ONTAP
> attaches its security groups to the **elastic network interfaces (ENIs)** it creates — there is no
> security-group field on the file system itself. Resolve them from observed data: read
> `NetworkInterfaceIds` from `fsx describe-file-systems`, call `ec2 describe-network-interfaces
> --network-interface-ids <those IDs>`, and read each interface's `Groups[].GroupId`. Feed those group
> IDs to `ec2 describe-security-groups`. If `NetworkInterfaceIds` is absent or the ENI lookup fails, the
> security-group checks are **Not evaluated — security group could not be resolved**, never a guessed
> Pass.

## Security (8 checks)

### SEC-01 — Security groups allow required ports

- **Severity**: High
- **API**: `fsx describe-file-systems` (`NetworkInterfaceIds`) + `ec2 describe-network-interfaces` +
  `ec2 describe-security-groups` (resolve the FSx security groups via the ENIs — see the note above);
  `fsx describe-storage-virtual-machines` (`ActiveDirectoryConfiguration`) and `fsx describe-volumes`
  (`SecurityStyle`) to determine the protocols actually in use.
- **Logic**: Determine the **protocols actually in use before checking ports** — do not assume NFS.
  Infer protocol from observed data: a volume `SecurityStyle = NTFS` and/or an SVM with
  `ActiveDirectoryConfiguration` present indicates **SMB/CIFS** (port 445); `SecurityStyle = UNIX`
  indicates **NFS** (2049, plus portmapper 111, mountd 635, NLM/NSM lockd 4045–4046). Check only the
  ports for the protocol(s) the SVM/volumes actually use — an SMB-only SVM must **not** be told to open
  NFS ports, and vice-versa.
- **Status**: Pass — the ports required by the in-use protocol(s) are open from the client CIDRs. Fail —
  a required port for an in-use protocol is missing. Not evaluated — the protocol in use could not be
  determined, or the security group could not be resolved.
- **Recommendation (Fail)**: Open the ports for the protocol(s) actually in use (SMB 445 for CIFS; NFS
  2049/111/635/4045–4046 for NFS) from the client subnets — not a blanket NAS port set.
- **Fields**: `securityGroupId`, `protocolsInUse`, `portsOpen`, `portsMissing`, `status`, `severity`

### SEC-02 — Security groups not overly permissive

- **Severity**: Critical
- **API**: `fsx describe-file-systems` (`NetworkInterfaceIds`) + `ec2 describe-network-interfaces` +
  `ec2 describe-security-groups` (resolve the FSx security groups via the ENIs — see the note above)
- **Logic**: Flag any inbound rule allowing `0.0.0.0/0` (or `::/0`).
- **Status**: Pass — no open-world rules. Fail — a `0.0.0.0/0` inbound rule exists.
- **Recommendation (Fail)**: Restrict security-group rules to specific client subnets / CIDRs. Storage
  ports must never be open to the internet.
- **Fields**: `securityGroupId`, `openRules`, `status`, `severity`

### SEC-03 — Volume security style correct

- **Severity**: Medium
- **API**: `fsx describe-volumes` (`OntapConfiguration.SecurityStyle`)
- **Logic**: Report security style per volume (`UNIX` for NFS, `NTFS` for SMB/CIFS).
- **Status**: Info — report all styles; flag an obvious protocol/style mismatch.
- **Recommendation**: Use `UNIX` for NFS workloads and `NTFS` for CIFS workloads.
- **Fields**: `volumeId`, `securityStyle`, `status`, `severity`

### SEC-04 — No unintentional MIXED security style

- **Severity**: Medium
- **API**: `fsx describe-volumes` (`OntapConfiguration.SecurityStyle`)
- **Logic**: Flag volumes with `SecurityStyle = MIXED`.
- **Status**: Pass — no MIXED volumes. Warning — MIXED present.
- **Recommendation (Warning)**: `MIXED` security style requires documented justification; it complicates
  permission resolution and is a frequent source of access-denied errors.
- **Fields**: `volumeId`, `securityStyle`, `status`, `severity`

### SEC-05 — AD integration properly configured

- **Severity**: Medium
- **API**: `fsx describe-storage-virtual-machines` (`ActiveDirectoryConfiguration`)
- **Logic**: Report AD configuration and `Subtype` / `LifecycleStatus` for SVMs that serve SMB.
- **Status**: Pass — AD configured and healthy. Info — report config. Fail — SMB-serving SVM with no AD
  configuration.
- **Recommendation (Fail)**: Configure AD on SVMs serving SMB clients and verify reachability from the
  SVM LIFs.
- **Fields**: `svmId`, `activeDirectoryConfigured`, `lifecycleStatus`, `status`, `severity`

### SEC-06 — Route-table associations for Multi-AZ traffic

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`OntapConfiguration.RouteTableIds`) + `ec2 describe-route-tables`
- **Logic**: For Multi-AZ file systems, confirm the configured route tables carry routes for the
  floating-IP endpoint range to the file system.
- **Status**: Pass — route tables configured for the endpoint range. Info — report config for Single-AZ.
  Fail — Multi-AZ with missing/incorrect route-table associations.
- **Recommendation (Fail)**: Verify the correct route-table associations exist for client traffic to the
  Multi-AZ floating-IP endpoints.
- **Fields**: `fileSystemId`, `deploymentType`, `routeTableIds`, `status`, `severity`

### SEC-07 — Encryption at rest / KMS key

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`KmsKeyId`)
- **Logic**: FSx for NetApp ONTAP is **always encrypted at rest**; this check confirms the KMS key and
  reports whether it is a customer-managed key (CMK) or the AWS-managed FSx key. The finding is the
  absence of a **customer-managed** key where one is required, never "not encrypted".
- **Status**: Pass — a customer-managed KMS key is configured. Informational — encrypted with the
  AWS-managed FSx key (still encrypted). Report the `KmsKeyId`.
- **Recommendation (Medium, when CMK required)**: If your compliance posture requires a customer-managed
  key, note that the KMS key is set at creation and cannot be changed afterward — plan a new file system
  with the desired CMK and migrate.
- **Fields**: `fileSystemId`, `kmsKeyId`, `customerManaged` (bool), `status`, `severity`

### SEC-08 — Security-group egress analysis

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`NetworkInterfaceIds`) + `ec2 describe-network-interfaces` +
  `ec2 describe-security-groups` (`IpPermissionsEgress`; resolve the FSx security groups via the ENIs —
  see the note above)
- **Logic**: Flag egress rules that are overly broad — a CIDR wider than `/16`, `0.0.0.0/0`, or
  all-protocols (`-1`) egress — on the FSx security group.
- **Status**: Pass — egress scoped to specific destinations/ports. Warning — egress broader than `/16`
  or all-protocols. Fail — `0.0.0.0/0` all-protocols egress.
- **Recommendation (Fail/Warning)**: Narrow overly broad egress rules to the specific destinations and
  ports the file system actually needs.
- **Fields**: `securityGroupId`, `broadEgressRules`, `status`, `severity`

---
