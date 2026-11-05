# Rollback reasoning

Produce the *substance* of a safe reversal for any change with medium-or-higher
blast radius. This is reasoning and a plan the human executes — not a rendered
change-request document, and not an automated action.

## Three parts

### 1. Pre-change snapshot (capture BEFORE changing anything)
The known-good baseline to restore to. For an IAM change, that is the current
state of everything the change touches:
- the current policy document(s) — managed version(s) and any inline policy
  bodies, verbatim
- every attachment (which roles/users/groups the policy is attached to)
- the role's trust policy (`AssumeRolePolicyDocument`)
- for keys: current key IDs and their Active/Inactive state
Tell the user to record these before proceeding, and how (e.g. `get-policy-version`,
`get-role-policy`, `list-entities-for-policy`, `get-role`) — all read-only.

### 2. Reversal steps
The ordered actions to restore the snapshot if the change goes wrong. Order
matters and is the inverse of the change: e.g. re-attach before re-enabling
dependents; restore the prior policy version before deleting the new one;
reactivate a key before anything that depends on it runs again. Be specific to
the change actually proposed — reference the exact policy/role/key names from the
real state, not placeholders.

### 3. Trigger conditions (when to roll back)
The observable signals that should prompt a reversal, plus the window to watch:
- new `AccessDenied` / `UnauthorizedOperation` in CloudTrail for the affected
  principal
- failed `AssumeRole` on the changed role
- a CloudWatch alarm or a broken workflow tied to the identity
- watch through at least one full business cycle for the workload (a nightly
  batch, a weekly report), longer than the change feels like it needs

## Framing
Keep it tight and concrete. The point is that the user can act on it under
pressure: what to save, how to put it back, and what tells them to. Reversibility
is the safety net that makes an advisory recommendation responsible.
