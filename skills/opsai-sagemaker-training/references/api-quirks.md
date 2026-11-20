# API Quirks

SageMaker read-only API responses whose obvious reading is **wrong** or misleading for a training / customization job review (traps §1–§5) or a Model Registry governance review (traps §6–§7). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. SageMaker training `InProgress` / `SecondaryStatus Pending` is NOT `Failed`

- **Trap:** A training/customization job that has not started training yet — `TrainingJobStatus: InProgress` with `SecondaryStatus: Starting`/`Pending` while it waits on GPU capacity — reads to an impatient operator as "failing", and gets reported as a failure.
- **Correct reading:** A job waiting on capacity is **control-plane-healthy**, not failed. Reporting it as a failure is a false positive. Report the true Pending-on-capacity status and prescribe **no** config change for a job that has not failed (LLM-SM-TRAIN-007). Only a `TrainingJobStatus: Failed` with a `FailureReason` is a failure.

## 2. `InsufficientInstanceCapacity` ≠ a quota problem

- **Trap:** Any "the job won't get instances" symptom reads as "request a quota increase."
- **Correct reading:** `InsufficientInstanceCapacity` is an **AWS-side** shortfall of the GPU instance type at that moment; a service quota of **zero** for the instance type is a **customer** limit. The remediations are **opposite** — retry/alternate instance or region for capacity (LLM-SM-TRAIN-002) versus `request-service-quota-increase` for a zero quota (LLM-SM-TRAIN-003). Distinguish by reading **both** the `FailureReason` and `service-quotas get-service-quota`; a quota increase does nothing for a capacity shortfall, and a retry does nothing for a zero quota.

## 3. `allow_percentage_invalid_samples` silently drops records

- **Trap:** A customization job that reports `Completed` reads as "all training data was used."
- **Correct reading:** When the recipe sets an invalid-sample tolerance (e.g. `allow_percentage_invalid_samples`), the job can **drop** malformed records up to that tolerance and still report `Completed` — the model trained on **less data than intended**. `Completed` ≠ "all data used". Check the drop count / training log, not just the status, before trusting a run; a few corrupt JSONL lines can be silently dropped rather than failing the job (LLM-SM-TRAIN-001).

## 4. Nova customization rejects a null `HyperParameters` map

- **Trap:** An omitted or null required hyperparameter reads as "it will fall back to a default."
- **Correct reading:** A Nova customization job **rejects a null/omitted required `HyperParameters` value at create/validate time** — it is a hard validation failure, not a "use the default." Supply every required value, none null, within the documented range (LLM-SM-TRAIN-004).

## 5. The recipe is referenced from S3, not inlined (~2500-char cap)

- **Trap:** A recipe error reads as a malformed API parameter to fix in the launch call.
- **Correct reading:** Nova/JumpStart recipes are passed **by S3 reference** because the inline hyperparameter field is capped (~2500 chars). A recipe error therefore points at the **S3 recipe object**, not the API parameter — inspect the object itself, and confirm the execution role can **read** it (ties to LLM-SM-TRAIN-004 / 005 / 006).

## 6. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource. Distinguish "zero measured" from "nothing reported." The Model Registry publishes no metric namespace, so absent datapoints say nothing about registry health.

## 7. An `Approved` package in the registry ≠ the deployed version is approved

- **Trap:** A model package in `ListModelPackages` with `ModelApprovalStatus: Approved` reads as "the group is governed."
- **Correct reading:** A model package in `ListModelPackages` with `ModelApprovalStatus: Approved` is only governed if the version that is actually deployed/staged is that approved version — a newer `PendingManualApproval`/`Rejected` version can be the one live. Resolve which version is deployed before clearing a group as approved (LLM-SM-REG-002).
