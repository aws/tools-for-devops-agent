# Permission chain - per-layer reference

Order of evaluation. Stop at the first denying layer; if several are broken, list all
in this order.

## 1. Lake Formation grants
- API: `lakeformation:ListPermissions` (filter by principal + resource),
  `lakeformation:GetDataLakeSettings`.
- Levels: CATALOG, DATABASE, TABLE, COLUMN (and `DESCRIBE` vs `SELECT`).
- Common gap: grant at DATABASE level but the operation needs TABLE `SELECT`; or the
  principal lacks `DESCRIBE` on the database and so cannot see the table at all.
- Hybrid access mode: `IAMAllowedPrincipals` present on a resource changes behavior -
  check whether the resource is under Lake Formation control or still IAM-only.
- Canonical permission taxonomy (per-resource valid permissions, DESCRIBE vs SELECT,
  DATA_LOCATION_ACCESS, hybrid access mode `IAMAllowedPrincipals` / `ALLIAMPrincipals`):
  https://docs.aws.amazon.com/lake-formation/latest/dg/lf-permissions-reference.html

## 2. Resource links / granted-but-unlinked
- API: `glue:GetDatabase`, `glue:GetTable`, `glue:GetTables`.
- A resource link is a Data Catalog object pointing at a shared/target resource.
- Both must hold: (a) the resource link exists in the consuming context, and (b) Lake
  Formation permission exists on BOTH the link and the target resource.
- granted-but-unlinked: permission on target but no link (query has nothing to
  reference), or a link with no permission on the target (link resolves to a denied
  target).

## 3. Cross-account share (AWS RAM)
- API: `ram:GetResourceShares`, `ram:GetResourceShareAssociations`,
  `glue:GetResourcePolicy`.
- Producer must grant cross-account Lake Formation permission; consumer must accept
  the RAM share; the Data Catalog resource policy must permit the consumer account /
  organization.

## 4. IAM identity policy
- API: `iam:SimulatePrincipalPolicy` with the required actions and `ResourceArns`;
  pass relevant `ContextEntries`.
- Include SCPs. The simulator evaluates SCPs (condition keys + resource scoping) and
  attributes an explicit deny to the organization, but does NOT return the matched SCP
  statement and does NOT list SCP-only condition keys. Treat an org-attributed deny as
  "an SCP is blocking - exact statement needs org-level review or a dedicated SCP
  evaluator."
- Typical data-plane actions: `lakeformation:GetDataAccess`, `glue:GetTable`,
  `glue:GetPartitions`, `athena:StartQueryExecution`, `athena:GetQueryResults`,
  `s3:GetObject`, `s3:ListBucket`.

## 5. S3 bucket policy
- API: `s3:GetBucketPolicy`.
- Evaluate for the principal AND the Lake Formation data-access role (Lake Formation
  vends credentials via a registered role).
- Watch: explicit Deny, missing Allow, `aws:CalledVia`, `aws:SourceVpce`, and
  `s3:DataAccessPointArn` conditions.

## 6. KMS
- API: `kms:GetKeyPolicy`.
- If the S3 data or the Data Catalog is encrypted with a customer managed key, the
  principal or the Lake Formation data-access role needs `kms:Decrypt`
  (+ `kms:GenerateDataKey` for writes). Cross-account keys must name the external
  principal in the key policy.

## Notes
- Lake Formation "vends" temporary credentials scoped by the grant; a denial can come
  from the grant OR from the underlying S3/KMS the vended role reaches. Check both.
- Results from policy simulation can differ from live; confirm in the account.

## Doc-verified facts (sources)
- `lakeformation:GetDataAccess` is required when the underlying S3 location is
  registered with Lake Formation. Athena requires the caller to hold it; other
  integrated engines require their execution role to hold it. Its policy Resource must
  be `*`. LF does not block direct S3 access granted via IAM/S3 policies.
  Source: https://docs.aws.amazon.com/lake-formation/latest/dg/access-control-underlying-data.html
- LF does not support cross-Region credential vending: the S3 data location must be
  registered in the same Region as the API call. Full-table-access vending must be
  enabled in data lake settings and the caller needs SELECT or SUPER on the table.
  Source: https://docs.aws.amazon.com/lake-formation/latest/APIReference/API_GetTemporaryDataLocationCredentials.html
