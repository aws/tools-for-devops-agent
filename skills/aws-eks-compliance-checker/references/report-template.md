# Report template

Load in Step 8. Fill every section in order. Keep headings exactly as written. Omit a framework section only when the user did not request that framework.

```markdown
# EKS Compliance Checker — {cluster} ({account}, {region})

> This report is technical evidence collected read-only from the Kubernetes API and AWS APIs on {UTC timestamp}. It is not a certification, audit opinion, or attestation of compliance. Controls marked Indicative need confirmation by your auditor.

## 1. Summary
- Kubernetes {version} ({versionStatus}, standard support ends {endOfStandardSupportDate}), platform {platformVersion}
- Frameworks: CIS Amazon EKS Benchmark v1.8.0{, others requested}
- CIS totals: PASS {n} / FAIL {n} / Manual review {n} / Not assessed {n} / Not covered {n} (of {total})
- Supplementary AWS checks: PASS {n} / FAIL {n} / Manual review {n} / Not assessed {n} (of 9)
- 2–4 sentences on the most important FAILs.

## 2. Scope and access
- Access used: Agent Space role {role name only}, Kubernetes access {granted policy or "denied"}
- Exclusions applied: {system namespaces and subjects actually excluded}
- Reads that failed: {read ID — error}, or "none"

## 3. Failed controls
| ID | Control | Offending resources | Fix |
|---|---|---|---|
One row per FAIL, CIS first then AWS-n. "Fix" is one sentence naming the setting to change.

## 4. CIS Amazon EKS Benchmark v1.8.0
| ID | Type | Control | Status | Evidence |
|---|---|---|---|---|
Every control from the controls file, in its order, one row per control ID. Write the 13 Section 3 controls as 13 separate Not covered rows (3.1.1 to 3.1.4, then 3.2.1 to 3.2.9), never as a range.

## 5. Supplementary AWS checks
| ID | Check | Status | Evidence |
|---|---|---|---|
AWS-1 to AWS-9.

## 6. Framework crosswalk
For each requested framework: one totals line, then
| Control | Status | Mapped IDs (statuses) | Basis (`Security Hub EKS.n` or `Indicative`) |
|---|---|---|---|
End each framework with the out-of-scope sentence from the crosswalk rules.

## 7. Items needing human review
One bullet per Manual review control: the evidence collected and the question to answer.
One bullet for Section 3: run kube-bench with the `eks-1.8.0` benchmark on the worker nodes.
```

Evidence cells hold the field and value that decided the status, for example `endpointPublicAccess=true; publicAccessCidrs=[203.0.113.0/24]`. Truncate lists of offending resources after 10 and give the total count.
