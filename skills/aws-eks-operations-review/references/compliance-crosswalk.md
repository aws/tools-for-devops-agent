# Compliance crosswalk overlay

Load only when the compliance overlay is requested (see [`runtime/overlays.md`](runtime/overlays.md)), and only after S6 grading is complete. This file maps **already-graded canonical check IDs** to framework controls. It adds no checks, changes no verdict or severity, and is not an audit, certification, or attestation. State that limitation in the rendered section.

## Contents

- Derivation rules
- CIS Amazon EKS Benchmark v1.8.0
- NIST SP 800-53 Rev. 5
- PCI DSS v4.0.1
- SOC 2 Trust Services Criteria (2017)
- HIPAA Security Rule
- Out-of-scope controls

## Derivation rules

1. **Status per control** comes only from the ledger verdicts of its mapped IDs:
   - `FAIL` if any mapped ID is FAIL. List the failing IDs.
   - `PASS` if every mapped ID is PASS.
   - `Not assessed` if no mapped ID is FAIL and at least one is N/A or was not selected for this run.
   - `Not covered` if the row maps no IDs. Never mark it PASS.
2. **Coverage** is `Full` or `Partial`. A `Partial` row covers only part of the control. Render it as `PASS (partial coverage)`, never as a plain compliant PASS.
3. **Mapping basis** is `Benchmark` (CIS control title), `Security Hub` (the *Related requirements* published for the Security Hub EKS control), or `Indicative` (the skill's own alignment). Mark `Indicative` rows as needing auditor confirmation.
4. Per-framework totals count controls, not check IDs: PASS / PASS (partial) / FAIL / Not assessed / Not covered.
5. A targeted review that did not select a mapped unit shows those controls as `Not assessed — unit not selected`. It must not show them as gaps.
6. Use the framework versions named in this file. If the user asks for a different version, say the numbering may differ and map by control title.

## CIS Amazon EKS Benchmark v1.8.0

Control IDs and titles follow the CIS Amazon EKS Benchmark v1.8.0, as encoded in the open-source `kube-bench` `eks-1.8.0` profile.

| CIS | Control (abridged) | Mapped IDs | Coverage |
|---|---|---|---|
| 2.1.1 | Enable audit logs | AX10, SM2 | Full |
| 2.1.2 | Audit logs collected and managed | AX10, A22 | Partial — retention/forwarding only |
| 4.1.1 | cluster-admin only where required | S10 | Full |
| 4.1.2 | Minimize access to secrets | S11 | Partial — wildcard rules only |
| 4.1.3 | Minimize wildcards in Roles/ClusterRoles | S11 | Full |
| 4.1.5 | Default service accounts not actively used | Op16 | Full |
| 4.1.6 | SA tokens mounted only where necessary | S14 | Full |
| 4.1.7 | Use Cluster Access Manager API | S12, AX3 | Full |
| 4.2.1 | Minimize privileged containers | S1, S9 | Full |
| 4.2.2–4.2.4 | Minimize hostPID / hostIPC / hostNetwork | S2 | Full |
| 4.2.5 | Minimize allowPrivilegeEscalation | S3 | Full |
| 4.3.1 | CNI supports network policies | S15 | Partial — inferred from enforced policies |
| 4.3.2 | All namespaces have NetworkPolicies | S15 | Full |
| 4.4.1 | Secrets as files, not env vars | S19 | Full |
| 4.4.2 | Consider external secret storage | S18 | Full |
| 4.5.1 | Namespaces as administrative boundaries | S31 | Partial — tenant isolation only |
| 5.1.1 | Image vulnerability scanning | S21, S38, SM5 | Full |
| 5.1.3 | Cluster ECR access read-only | SM7 | Partial — node role scope only |
| 5.2.1 | Dedicated EKS service accounts | S13, Op16 | Full |
| 5.3.1 | Secrets encrypted with AWS KMS keys | AX11, SM1 | Full |
| 5.4.1 | Restrict access to the control plane endpoint | AX12, SM3 | Full |
| 5.4.2 | Private endpoint enabled, public access disabled | AX12 | Partial — AX12 can PASS with CIDR-restricted public access; render FAIL if `endpointPublicAccess=true` |
| 5.4.3 | Private nodes | NM2 | Full |
| 5.4.4 | Network policy enabled | S15 | Full |
| 5.5.1 | Manage RBAC users through IAM | S12, AX3 | Partial — access entries are the current mechanism |

CIS 5.4.2 is the only row where the skill reads a fact directly instead of using a verdict alone. Use the `endpointPublicAccess` value already recorded as AX12 evidence, and do not issue a new read.

## NIST SP 800-53 Rev. 5

`Security Hub` rows copy the related requirements that AWS publishes for Security Hub EKS controls EKS.1, EKS.2, and EKS.8.

| NIST control(s) | Mapped IDs | Basis | Coverage |
|---|---|---|---|
| AC-3, AC-4, AC-6, AC-21, SC-7 (EKS.1 public endpoint) | AX12, SM3, NM3 | Security Hub | Partial |
| CA-9(1), CM-2, SI-2 (EKS.2 supported version) | Op1 | Security Hub | Partial |
| AU-2, AU-3, AU-12, AC-2(4), SI-4, CA-7 (EKS.8 audit logging) | AX10, SM2 | Security Hub | Partial |
| AC-6 least privilege | S10, S11, S13, S29, SM7, AX9 | Indicative | Partial |
| IA-2, IA-5 identification and authenticators | S12, AX3, S26, S28 | Indicative | Partial |
| CM-6, CM-7 configuration settings / least functionality | S1–S9, S23, S24 | Indicative | Partial |
| RA-5, SI-2 vulnerability monitoring and flaw remediation | S21, S38, Op7, AX5, Op29 | Indicative | Partial |
| SC-8 transmission confidentiality | SM6 | Indicative | Partial |
| SC-12, SC-28 key management / protection at rest | AX11, SM1, SM4, S32 | Indicative | Partial |
| SI-4 system monitoring | S22, S37, O6, O21 | Indicative | Partial |
| CP-9, CP-10 backup and recovery | R20, R21 | Indicative | Partial |

## PCI DSS v4.0.1

| Requirement | Mapped IDs | Basis | Coverage |
|---|---|---|---|
| 1.4.4 (EKS.1 public endpoint) | AX12, SM3 | Security Hub | Partial |
| 10.2.1 audit logs enabled (EKS.8) | AX10, SM2 | Security Hub | Partial |
| 12.3.4 hardware/software technologies reviewed (EKS.2) | Op1 | Security Hub | Partial |
| Req 1 — network security controls | S15, NM2 | Indicative | Partial |
| Req 2 — secure configurations | S1–S9, S24 | Indicative | Partial |
| Req 3 — protect stored account data (encryption, keys) | AX11, SM1, SM4, S32 | Indicative | Partial |
| Req 4 — strong cryptography in transit | SM6 | Indicative | Partial |
| Req 6 — vulnerabilities identified and patched | S21, S38, Op7, AX5, Op29 | Indicative | Partial |
| Req 7 — access restricted by need to know | S10, S11, S13, S29 | Indicative | Partial |
| Req 8 — identify and authenticate users | S12, AX3, S26 | Indicative | Partial |
| Req 11 — intrusion detection / change detection | S22, S37 | Indicative | Partial |

## SOC 2 Trust Services Criteria (2017)

All SOC 2 rows are `Indicative`. The criteria are principle-based, and the auditor decides sufficiency.

| Criterion | Mapped IDs | Coverage |
|---|---|---|
| CC6.1 logical access security | S10, S11, S12, S13, S29, AX3, AX11 | Partial |
| CC6.6 boundary protection | AX12, SM3, NM2, S15 | Partial |
| CC6.7 transmission protection | SM6 | Partial |
| CC6.8 prevent/detect unauthorized software | S21, S23, S38 | Partial |
| CC7.1 detect configuration changes and vulnerabilities | S38, S39, AX1, O16 | Partial |
| CC7.2 monitor for anomalies | AX10, S22, S37, O6, O21 | Partial |
| CC8.1 change management | Op6, Op31, Op32 | Partial |
| A1.2 recovery infrastructure | R1, R20, R21, NM1 | Partial |

## HIPAA Security Rule

All HIPAA rows are `Indicative`. They show technical-safeguard alignment only. They do not show administrative or physical safeguards.

| Safeguard | Mapped IDs | Coverage |
|---|---|---|
| §164.312(a)(1) access control | S10, S11, S13, S29, AX3 | Partial |
| §164.312(a)(2)(iv) encryption and decryption | AX11, SM1, SM4, S32 | Partial |
| §164.312(b) audit controls | AX10, SM2, O16 | Partial |
| §164.312(c)(1) integrity | S20, SM5, S23 | Partial |
| §164.312(d) person or entity authentication | S12, AX3, S26 | Partial |
| §164.312(e)(1) transmission security | SM6, AX12 | Partial |
| §164.308(a)(1)(ii)(D) information system activity review | O16, S22, S37 | Partial |
| §164.308(a)(7) contingency plan | R1, R20, R21 | Partial |

## Out-of-scope controls

List these as `Not covered` with the reason. Do not grade them, and do not add discovery to approximate them:

- CIS 3.1.x and 3.2.x (worker-node file permissions and kubelet arguments) need node host access. Recommend running `kube-bench` on the nodes.
- CIS 4.1.4, 4.1.8–4.1.12 (create-pod, bind/impersonate/escalate, PV-create, node-proxy, webhook-config, and token-create access) are not graded by a canonical row.
- CIS 4.5.2 (default namespace unused), 5.1.2 (user ECR access), 5.1.4 (approved registries), and 5.4.5 (TLS on HTTPS load balancers) are not graded by a canonical row.
- Framework procedural, administrative, and physical requirements, such as policies, training, and facility controls.

## Render shape

Render as the `### Compliance crosswalk` subsection at the end of §5. Start with one disclaimer line. Then, for each requested framework, give a totals line and a table with columns `Control | Status | Mapped IDs (verdicts) | Coverage | Basis`. List every `Not covered` control in §7 with its reason.
