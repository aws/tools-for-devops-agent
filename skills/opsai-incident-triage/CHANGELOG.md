# Changelog

## 1.0.0
- When the fault sits in a dependency, the answer also says whether the feature should degrade gracefully (timeout, circuit breaker, defined fallback). Evals: `transient-vs-config-verdict` gives the provider-side evidence in the prompt; `model-available-but-unreachable` is removed (scored the same with and without the skill in two runs).
- When the loop and the model call run on different hosting, the TRIAGE line names both bindings and says that `AWS/Lambda` `Errors` cannot split client from server errors.
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Evals: `self-hosted-model-locus-not-provider` and `agent-loop-on-lambda-binding` say the workload is in an account that isn't connected, so the agent triages instead of searching for it. `fa-healthy-agent-status` accepts saying no model traffic can be tied to the search runtime.
- Evals: check-id assertions are dropped from the three questions that name no account resource.

- PR #268 review item 4: `SKILL.md` body cut from 877 to 473 lines. The classifier walkthrough, the Step 5b error-code table, the common wrong answers, the severity definitions and the routing table move to `references/`; the output templates and the R3 gate move to `assets/triage-report-template.md`. `SKILL.md` keeps the checklist and the rules a correct locus needs if a reference fails to load.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: new `EnableOpsaiIncidentTriage` template parameter (`bedrock:GetFoundationModelAvailability`, `bedrock:GetIngestionJob`, AgentCore status reads); `bedrock-agent:` names corrected to `bedrock:`; `iam:SimulatePrincipalPolicy` replaced by a static policy read.
- Initial release in this repository.
- Triages live model-call failures (errors, throttling, latency) and rules whether the fault is the provider, infrastructure or app.
- Renamed from the earlier incident triage skill. `Remediation owner` now names an owner track from `references/related-skills.md` instead of a skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
