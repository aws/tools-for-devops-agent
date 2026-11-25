# Changelog

## 1.0.0

- Initial version.
- Diagnoses failed `AWS-RunPatchBaseline` runs (Run Command, maintenance window tasks and patch
  policies) on Linux and Windows instances and matches them to 84 reviewed SOPs.
- Safety gates: maintenance window with enough time left, at most 3 Install attempts in 12 hours,
  SOP prerequisites; no action at all when no SOP matches.
- Selects only the SOP steps that apply to the instance's OS, distribution and version.
- Every plan ends with a ready-to-run AWS CloudShell Command plan; copied patch parameters are
  validated against their documented formats.
- Runs the plan as directed actions in chat, one operator-approved step at a time.
- Scoped elevated-role CloudFormation template (Run Command on three AWS-owned documents, tagged
  instances by default, one Agent Space).
