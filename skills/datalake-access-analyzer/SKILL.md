---
name: datalake-access-analyzer
description: >
  Diagnoses AWS Lake Formation and cross-service data-lake "access denied" and
  "insufficient permissions" errors. Use when a principal cannot access a Glue Data
  Catalog database or table or a Lake Formation-governed resource, or when an Amazon
  Athena, Amazon EMR, Amazon Redshift Spectrum, or Amazon QuickSight query fails with
  access denied or a Lake Formation permission error. Traces the full authorization
  chain - Lake Formation grants, Data Catalog resource links, cross-account AWS RAM
  shares, IAM identity policies, S3 bucket policies, and KMS key policies - to pinpoint
  the missing or incorrect grant and produce a corrective Lake Formation grant, IAM, or
  RAM patch. Also detects governed resources that are granted but not resource-linked,
  and catalog-level vs table-level grant-scope mismatches. Read-only: it recommends
  fixes and does not apply them.
metadata:
  version: "0.1.0"
  author: jbakthav
aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA, Evaluation"
aws-devops-agent-skills.aws-services: "AWS Lake Formation, AWS Glue, Amazon Athena, Amazon EMR, Amazon QuickSight"
aws-devops-agent-skills.technical-domains: "Analytics"
---

## Instructions

Diagnose a data-lake access-denied failure by walking the authorization chain in
order and stopping at the first layer that denies. Report the breaking layer, the
evidence, and a corrective patch. This skill is read-only - every call is a
describe / list / get / simulate. Never apply changes; recommend them.

### When to use
Activate on symptoms such as:
- `AccessDeniedException` / "Insufficient Lake Formation permission(s)" on a Glue
  Data Catalog database, table, or column.
- Athena query fails with access denied or "not authorized to perform:
  lakeformation:GetDataAccess".
- EMR (Spark/Hive), Redshift Spectrum, or QuickSight cannot read a governed table.
- A cross-account consumer cannot see or query a shared database/table.
- A principal was granted access "but it still doesn't work."

### Layer states
Every layer in the chain (Steps 1-6) reports one of:
- **OK**: checked, permission is present and correctly scoped.
- **DENYING**: checked, this layer is the (or a) cause of the denial.
- **NOT_CHECKED**: collection failed or access was unavailable - state the reason.
- **INSUFFICIENT_DATA**: data returned but too incomplete to judge.

A layer that is OK after a successful check must render differently from a layer
that could not be checked. Never report a NOT_CHECKED layer as OK. The final verdict
is only as strong as the weakest checked layer - if a layer on the path is
NOT_CHECKED, say the diagnosis is partial.

### Inputs to collect
1. Principal ARN (role/user) that is denied.
2. Target resource: catalog id, database, table (and column set if relevant), or the
   underlying S3 location.
3. Region and account id of the resource; consumer account id if cross-account.
4. Optional: the failed request id or the CloudTrail AccessDenied event.
5. The querying engine (Athena / EMR / Redshift Spectrum / QuickSight / Glue ETL).

### Step 0 - Establish governance mode
Call `lakeformation:GetDataLakeSettings` and `lakeformation:ListResources`. Decide
whether the target is Lake Formation-governed or IAM-only. If IAM-only, skip the
Lake Formation layers (Steps 1-3) and go to Step 4.

### Step 1 - Lake Formation grants
`lakeformation:ListPermissions` for the principal and resource. Check the grant
level actually held (catalog / database / table / column) against the level the
operation needs.
- Detector - catalog-vs-table scope mismatch: a grant exists at database level but
  the operation needs table-level (or a table grant exists but the flow needs
  `DESCRIBE` on the database). Report the exact scope gap.

### Step 2 - Resource links and granted-but-unlinked
`glue:GetDatabase` / `glue:GetTable` / `glue:GetTables`. For shared or linked
resources, confirm BOTH exist and are consistent:
- a resource link object in the consuming context, AND
- Lake Formation permissions on BOTH the resource link and its target.
- Detector - granted-but-unlinked: Lake Formation permission is granted on the
  target but no resource link was created (or the link exists without permission on
  the target). Report which half is missing.

### Step 3 - Cross-account share (AWS RAM)
For cross-account access: `ram:GetResourceShares` / `ram:GetResourceShareAssociations`
and `glue:GetResourcePolicy` (Data Catalog resource policy). Verify the producer
granted cross-account Lake Formation permission, the RAM share is accepted in the
consumer, and the Data Catalog resource policy permits the consumer.

### Step 4 - IAM identity policy
`iam:SimulatePrincipalPolicy` for the required data-plane actions (for example
`lakeformation:GetDataAccess`, `glue:GetTable`, `athena:StartQueryExecution`,
`s3:GetObject`). Include service control policies in the simulation.
- `lakeformation:GetDataAccess` is required whenever the underlying S3 location is
  registered with Lake Formation. Who must hold it differs by engine: Athena requires
  the CALLER (user/role) to have it; other integrated engines (EMR, Redshift Spectrum,
  QuickSight) require their EXECUTION ROLE to have it. Its policy `Resource` must be
  `*` (any other value is unsupported). Check the right identity for the engine.
- Note: the policy simulator evaluates SCPs (including their condition keys and
  resource scoping) but does not return which SCP statement matched - matched SCP
  statements are not surfaced and SCP-only condition keys are not listed. If the
  decision is an explicit deny attributed to the organization, report that an SCP is
  blocking and, if a dedicated SCP effective-permissions evaluator is available, hand
  off to it to identify the exact statement. Otherwise state that SCP-statement
  attribution requires organization-level review.

### Step 5 - S3 bucket policy
`s3:GetBucketPolicy` on the underlying data location. Evaluate for the principal and
for the Lake Formation data-access role. Watch for explicit Deny, missing Allow, and
`aws:CalledVia` / VPC-endpoint conditions that exclude the caller.

### Step 6 - KMS
If the data or catalog is encrypted with a customer managed key: `kms:GetKeyPolicy`.
Confirm the principal or the Lake Formation data-access role has `kms:Decrypt` (and
`kms:GenerateDataKey` for writes), and that a cross-account key policy names the
external principal.

### Step 7 - Synthesize and patch
Identify the first (or single) breaking link. Emit a corrective patch scoped to that
layer:
- Lake Formation: a `GrantPermissions` action with exact principal, resource, and
  permission set.
- IAM: the minimal policy statement to add.
- RAM / Data Catalog resource policy: the share or accept step.
Prefer least-privilege. If multiple layers are broken, list them in chain order.

### Known denial gotchas (doc-verified)
- Cross-Region registered location: Lake Formation does NOT vend credentials for an
  S3 data location registered in a different Region than the API call. If the
  registered location and the query engine are in different Regions, that alone causes
  the denial - flag it regardless of grants.
- "Works via S3 but not via the query engine": the Lake Formation model does not block
  direct S3 access granted through IAM/S3 policies. If a principal can read the object
  directly but the governed query fails, suspect the LF grant or
  `lakeformation:GetDataAccess`, not the S3 bucket policy.
- Full-table access credential vending must be enabled in the data lake settings, and
  the caller needs SELECT or SUPER on the associated table.
- Create/update-table denials at a registered location are governed by
  `DATA_LOCATION_ACCESS` (not table SELECT) - check that separately from read denials.

### Output format
Return: (1) verdict, (2) breaking layer, (3) a per-layer state line (OK / DENYING /
NOT_CHECKED / INSUFFICIENT_DATA) with the API called and the finding for each layer,
(4) corrective patch, (5) confidence, and (6) any layer that needs separate handling
(SCP attribution or a KMS grant owned by another account). If any on-path layer is
NOT_CHECKED, label the verdict "partial."

### Safety
Read-only diagnosis. All actions are describe / list / get / simulate. Recommend
remediation; do not execute it. Do not print secrets or full policy documents
containing credentials.

### References
- `references/permission-chain.md` - per-layer API and condition detail.
