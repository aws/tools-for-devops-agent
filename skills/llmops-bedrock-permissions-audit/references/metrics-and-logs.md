# Metrics & Logs Reference

The signal set for the LLM-BPA checks of the long-lived credential audit.

---

## Long-lived credential audit signals

This audit reads **IAM configuration only**. It reads **no Amazon CloudWatch metric and no log
group**, and it calls no CloudWatch, CloudWatch Logs or AWS CloudTrail API: every LLM-BPA finding
comes from the read-only IAM calls in `collection-reference.md`.

- Access key status, age and last use come from `iam:ListAccessKeys` and
  `iam:GetAccessKeyLastUsed`. Last use is the key's last call to any AWS service, and IAM does not
  report when an API key was last used (`api-quirks.md` sections 10 and 11).
- Which model a key invoked, and when, is usage history, not configuration, and this skill does not
  read it. AWS CloudTrail records Amazon Bedrock API calls, and Amazon GuardDuty AI Protection
  reports findings such as `Impact:IAMUser/AnomalousModelInvocation`.

Because there is no metric to read, CloudWatch "no datapoints" is not evidence for or against any
LLM-BPA finding. References:
[Monitor Amazon Bedrock API calls using CloudTrail](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html),
[GuardDuty AI Protection](https://docs.aws.amazon.com/guardduty/latest/ug/ai-protection.html).
