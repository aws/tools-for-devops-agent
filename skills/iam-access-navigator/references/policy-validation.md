# Policy validation

Confirm a policy (generated in Capability 3, or supplied by the user) is
syntactically sound and won't break attachment or open a hole — before it is
applied. Read-only: uses IAM Access Analyzer's on-demand *validation* APIs, which
change nothing and — importantly — **need no analyzer configured and no Security
Hub**. They are a stateless call available in any account. Layer 3+ (the
heuristics) are pure in-skill reasoning and work even if you choose not to call
the validation APIs at all.

## Layers
1. **Parse JSON.** Malformed JSON → `is_valid = false`, a CRITICAL finding, stop.
2. **Access Analyzer `ValidatePolicy`** (policy type IDENTITY_POLICY by default;
   on-demand, no analyzer required).
   Surface each finding by type:
   - **ERROR** → blocks; sets `is_valid = false`
   - **SECURITY_WARNING** / **WARNING** → surface, don't block
   - **SUGGESTION** → surface as advice
   A `ValidationException` means the policy is malformed (the check still ran).
   Any other exception means validation is **unavailable** — report it per the
   coverage contract; do not claim the policy passed.
3. **Dangerous action + broad resource.** Flag `Action: *` (CRITICAL). Flag a
   dangerous action (e.g. `iam:*`, `iam:CreateUser`, `iam:CreateRole`,
   `iam:Attach*`, `iam:Put*`, `iam:CreatePolicyVersion`, `iam:PassRole`,
   `sts:AssumeRole`, `s3:*`, `ec2:*`, `lambda:*`, `kms:*`, `organizations:*`)
   **only when the resource is also broad** (`*` or empty) → HIGH. Include a
   plain-English "why this is dangerous" for each.
4. **Missing conditions** (SUGGESTION when a statement has no `Condition`):
   - `sts:AssumeRole` → `aws:PrincipalOrgID` / `aws:SourceAccount`
   - `s3:PutObject` → server-side encryption condition
   - `s3:GetObject` → VPC / source-IP condition
   - `kms:Decrypt` → `kms:ViaService`
   - `kms:CreateGrant` → `kms:GrantIsForAWSResource`
5. (Optional) **`CheckAccessNotGranted`** to prove specific dangerous actions are
   blocked — PASS/FAIL with the violating statements.

## Verdict
FAIL if any errors; else WARN if any warnings; else PASS. `is_valid` = (errors
== 0). Explain each finding in words and tie it back to what the user should
change. Pair this with least-privilege synthesis every time — an unvalidated
generated policy is itself a rollback risk.
