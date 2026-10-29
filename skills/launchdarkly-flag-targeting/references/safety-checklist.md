# Targeting Safety Checklist

Run through this checklist before applying any targeting changes, especially in production.

## Before Every Change

### 1. Right Environment?

- [ ] Confirmed the environment with the user (don't assume "production")
- [ ] If the user said "turn it on" without specifying, ask which environment

### 2. Right Flag?

- [ ] Confirmed the flag key matches what the user intends
- [ ] If the flag key could be ambiguous, verify with `get-flag`

### 3. Understand Current State

- [ ] Fetched the flag's current configuration in the target environment
- [ ] Noted the current `on` state, rules, and targets
- [ ] Identified any prerequisites that must be met

### 4. Approval Required?

Some environments require approval for changes.

- [ ] If any mutation tool returns `requiresApproval: true`, inform the user
- [ ] Provide the approval URL if one was returned
- [ ] Offer to create an approval request with `create-approval-request` using the returned `instructions`
- [ ] Include a clear description of the intended change in the approval request
- [ ] Do NOT attempt to bypass approval or auto-approve
- [ ] If checking on a previous request, use `list-approval-requests`
- [ ] Only apply a request (`apply-approval-request`) if reviewStatus is "approved"

See [Approval Workflows](approval-workflows.md) for the complete reference.

### 5. Audit Trail

- [ ] Added a `comment` to the change explaining what and why
- [ ] This is especially important for production changes

## For Percentage Rollouts

- [ ] Weights sum to exactly 100% (100000 in the API)
- [ ] The rollout is on the default rule (fallthrough) unless intentionally on a specific rule
- [ ] Individual targets and higher-priority rules aren't silently overriding the rollout for some users
- [ ] Consider starting small (1-5%) for high-risk features

## For Targeting Rules

- [ ] New rules are placed at the correct position in evaluation order
- [ ] Clauses correctly express the targeting intent (AND within a rule, OR between rules)
- [ ] The `negate` field is set correctly (default `false`)
- [ ] The context kind matches what the codebase sends (e.g., `user`, `device`, `organization`)
- [ ] Attribute names match exactly what the SDK sends (case-sensitive)

## For Individual Targets

- [ ] The values match exactly what the SDK sends as the user/context key
- [ ] Individual targets are intended to override rules (they always win)
- [ ] Using `replaceTargets` intentionally: it replaces ALL targets, not just adds

## For Cross-Environment Copies

- [ ] Source environment is the one you tested in
- [ ] Target environment is correct
- [ ] You've selected the right included actions (don't accidentally copy ON state to production if you only meant to copy rules)
- [ ] Target environment's approval requirements are considered

## Production-Specific Checks

For any change to a production environment:

- [ ] Change has been tested in a lower environment first (staging, dev)
- [ ] Rollback plan is clear (what to do if something goes wrong)
- [ ] Comment explains the change for audit trail
- [ ] If doing a percentage rollout, start with a small percentage first

## After the Change

- [ ] Verified the new state with `get-flag`
- [ ] Described the resulting targeting to the user in plain language
- [ ] Confirmed the change achieves what the user asked for
