# Changelog

## 1.0.0
- Initial release. Read-only, report-only audit of IAM roles, users and
  customer-managed policies against their IAM limits (managed policies per
  role or user, policy document size, trust policy size, entities per
  account). Classifies each at-risk object as a consolidation candidate or an
  adjustable-quota increase candidate and never changes a policy or requests a
  quota increase.
- Enumerates objects with a single get-account-authorization-details call and
  falls back to attached-policy ARNs or Resource Explorer when IAM list calls
  are denied, stating the scope of the result.
