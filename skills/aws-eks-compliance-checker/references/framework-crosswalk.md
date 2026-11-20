# Framework crosswalk

Load in Step 6, only when the user asked for NIST SP 800-53, PCI DSS, SOC 2, or HIPAA. Each row maps a framework control to the CIS controls (plain IDs such as `5.4.1`) and supplementary checks (`AWS-n`) graded in Step 5. Mapping is derived after grading and never changes a graded status.

## Contents

- Derivation rules
- NIST SP 800-53 Rev. 5
- PCI DSS v4.0.1
- SOC 2 Trust Services Criteria (2017)
- HIPAA Security Rule

## Derivation rules

1. **Status per framework row** comes only from the graded statuses of its mapped IDs, in this order:
   - `FAIL` if any mapped ID is FAIL. List the failing IDs.
   - `Not assessed` if any mapped ID is Not assessed or Not covered.
   - `Manual review` if any mapped ID is Manual review.
   - `PASS` if every mapped ID is PASS.
2. **Coverage** is always `Partial` for these frameworks: a cluster review shows technical evidence for part of a control, never the whole control. Render a passing row as `PASS (partial coverage)`.
3. **Basis** is `Security Hub EKS.n` when AWS publishes the requirement as a *Related requirement* of a Security Hub EKS control, naming the control from the row (`Security Hub EKS.1`, `Security Hub EKS.2`, or `Security Hub EKS.8`), and `Indicative` otherwise. Mark `Indicative` rows as needing auditor confirmation.
4. **Totals** count framework rows, not mapped IDs: PASS (partial) / FAIL / Manual review / Not assessed.
5. Use the framework versions named in this file. If the user asks for another version, say the numbering may differ and map by control title.
6. Procedural, administrative, and physical requirements (policies, training, facilities, vendor management) are out of scope. Say so once per framework.

## NIST SP 800-53 Rev. 5

| NIST control(s) | Mapped IDs | Basis |
|---|---|---|
| AC-3, AC-4, AC-6, AC-21, SC-7 (EKS.1 public endpoint) | 5.4.1, 5.4.2 | Security Hub |
| CA-9(1), CM-2, SI-2 (EKS.2 supported version) | AWS-2 | Security Hub |
| AU-2, AU-3, AU-12, AC-2(4), SI-4, CA-7 (EKS.8 audit logging) | 2.1.1, AWS-1 | Security Hub |
| AC-6 least privilege | 4.1.1, 4.1.2, 4.1.3, 4.1.8, 5.1.3, 5.2.1 | Indicative |
| AC-2 account management, IA-2 identification and authentication | 4.1.7, 5.5.1 | Indicative |
| CM-6, CM-7 configuration settings and least functionality | 4.2.1, 4.2.2, 4.2.3, 4.2.4, 4.2.5, AWS-8 | Indicative |
| RA-5, SI-2 vulnerability monitoring and flaw remediation | 5.1.1, AWS-3, AWS-6 | Indicative |
| SC-7 boundary protection | 4.3.2, 5.4.3, 5.4.4 | Indicative |
| SC-8 transmission confidentiality | 5.4.5 | Indicative |
| SC-12, SC-28 key management and protection at rest | 5.3.1, AWS-7 | Indicative |
| AU-11 audit record retention | 2.1.2 | Indicative |
| SI-4 system monitoring | AWS-4, AWS-5 | Indicative |
| CP-9, CP-10 backup and recovery | AWS-9 | Indicative |

## PCI DSS v4.0.1

| Requirement | Mapped IDs | Basis |
|---|---|---|
| 1.4.4 (EKS.1 public endpoint) | 5.4.1, 5.4.2 | Security Hub |
| 10.2.1 audit logs enabled (EKS.8) | 2.1.1, AWS-1 | Security Hub |
| 12.3.4 hardware and software technologies reviewed (EKS.2) | AWS-2 | Security Hub |
| Req 1 — network security controls | 4.3.2, 5.4.3, 5.4.4 | Indicative |
| Req 2 — secure configurations | 4.2.1, 4.2.2, 4.2.3, 4.2.4, 4.2.5, AWS-8 | Indicative |
| Req 3 — protect stored account data | 5.3.1, AWS-7 | Indicative |
| Req 4 — strong cryptography in transit | 5.4.5 | Indicative |
| Req 6 — vulnerabilities identified and patched | 5.1.1, AWS-3, AWS-6 | Indicative |
| Req 7 — access restricted by need to know | 4.1.1, 4.1.2, 4.1.3, 4.1.8 | Indicative |
| Req 8 — identify and authenticate users | 4.1.7, 5.5.1 | Indicative |
| Req 10.5.1 — audit log retention | 2.1.2 | Indicative |
| Req 11.5 — intrusion and change detection | AWS-4 | Indicative |

## SOC 2 Trust Services Criteria (2017)

All SOC 2 rows are `Indicative`. The criteria are principle-based, and the auditor decides sufficiency.

| Criterion | Mapped IDs |
|---|---|
| CC6.1 logical access security | 4.1.1, 4.1.2, 4.1.3, 4.1.7, 5.2.1, 5.3.1 |
| CC6.6 boundary protection | 5.4.1, 5.4.2, 5.4.3, 4.3.2 |
| CC6.7 transmission protection | 5.4.5 |
| CC6.8 prevent or detect unauthorized software | 5.1.1, 5.1.4, AWS-6 |
| CC7.1 detect configuration changes and vulnerabilities | AWS-2, AWS-3, AWS-6 |
| CC7.2 monitor for anomalies | 2.1.1, AWS-4, AWS-5 |
| A1.2 recovery infrastructure | AWS-9 |

## HIPAA Security Rule

All HIPAA rows are `Indicative`. They show technical-safeguard alignment only, not administrative or physical safeguards.

| Safeguard | Mapped IDs |
|---|---|
| §164.312(a)(1) access control | 4.1.1, 4.1.2, 4.1.3, 4.1.7 |
| §164.312(a)(2)(iv) encryption and decryption | 5.3.1, AWS-7 |
| §164.312(b) audit controls | 2.1.1, 2.1.2, AWS-5 |
| §164.312(c)(1) integrity | 4.2.1, 5.1.1, AWS-6 |
| §164.312(d) person or entity authentication | 4.1.7, 5.5.1 |
| §164.312(e)(1) transmission security | 5.4.5, 5.4.2 |
| §164.308(a)(1)(ii)(D) information system activity review | AWS-4, AWS-5 |
| §164.308(a)(7) contingency plan | AWS-9 |
