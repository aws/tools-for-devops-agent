# datalake-access-analyzer

Diagnoses AWS Lake Formation and cross-service data-lake access-denied errors by
tracing the full authorization chain and pinpointing the missing or incorrect grant.

## What it does
Given a denied principal and a governed resource (or a failed request), it walks the
chain in order - Lake Formation grants -> Data Catalog resource links -> cross-account
AWS RAM shares -> IAM identity policy -> S3 bucket policy -> KMS key policy - and
reports the first breaking layer with a corrective Lake Formation / IAM / RAM patch.
It also detects two common silent failures: resources that are granted but not
resource-linked, and catalog-level vs table-level grant-scope mismatches.

It is read-only. It recommends fixes; it does not apply them.

## Prerequisites
The invoking role needs read-only access to:
- `lakeformation:GetDataLakeSettings`, `lakeformation:ListPermissions`, `lakeformation:ListResources`
- `glue:GetDatabase`, `glue:GetTable`, `glue:GetTables`, `glue:GetResourcePolicy`
- `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:GetRole`
- `iam:SimulatePrincipalPolicy` (optional - corroboration only; frequently unavailable in the DevOps Agent runtime)
- `ram:GetResourceShares`, `ram:GetResourceShareAssociations`
- `s3:GetBucketPolicy`
- `kms:GetKeyPolicy`
- `cloudtrail:LookupEvents` (optional, to correlate the failed request)

## How to use
Describe the problem in natural language, for example:
- "Our analytics role gets access denied querying the sales table in Athena even
  though we granted it in Lake Formation."
- "A cross-account consumer can't see the shared database."
- "EMR Spark job fails reading a governed table with insufficient Lake Formation
  permissions."

Provide the principal ARN, the target database/table (or S3 location), the region and
account, and the querying engine. The skill returns the breaking layer, evidence, and
a remediation patch.

## Limitations
- IAM evaluation uses direct policy reads as the primary method.
  `iam:SimulatePrincipalPolicy` is used only as optional corroboration and is frequently
  unavailable in the DevOps Agent runtime; the skill never blocks on it.
- SCPs: the policy simulator evaluates unconditional SCPs but does NOT evaluate SCPs that
  contain conditions, and cannot simulate cross-account access. It also does not reveal
  which SCP statement denied. When a deny is attributed to AWS Organizations, the skill
  flags that an SCP is blocking and defers exact-statement attribution to an
  organization-level review (or a dedicated SCP evaluator). It is not a definitive SCP
  verdict.
- Results from policy simulation can differ from the live environment; confirm against
  the live account.

## Disclaimer
This skill is sample code, not intended for production use without additional review
and testing. Users should validate in a non-production environment first.
