# Removal Readiness Checklist

A systematic safety check to determine whether a feature flag can be safely removed. Run through this checklist before recommending flag removal to a user.

## The Checklist

### 1. Cross-Environment Status

**Check:** Use `get-flag-status-across-envs` to verify the flag's state in all environments.

**Pass criteria:**
- Flag is `inactive` or `launched` in ALL critical environments (production, staging, etc.)
- No environment shows `new` or `active` state

**Fail criteria:**
- Flag is `active` in any critical environment
- Flag is `new` anywhere (still being rolled out)
- Critical environments show different states (e.g., production ON, staging OFF)

### 2. Configuration Consistency

**Check:** Use `get-flag` for each critical environment and compare configurations.

**Pass criteria:**
- All critical environments serve the same variation (same `fallthrough.variation` or same `offVariation`)
- No targeting rules or individual targets exist in critical environments

**Caution criteria:**
- Environments serve the same variation but through different mechanisms (one via fallthrough, another via rules)
- Simple rules exist but all resolve to the same variation

**Fail criteria:**
- Critical environments serve different variations
- Complex targeting rules exist that serve multiple variations
- Individual targets override the default behavior

### 3. Dependency Check

**Check:** Look for `prerequisites` in the flag configuration. Also check if this flag appears as a prerequisite in other flags.

**Pass criteria:**
- No other flags list this flag as a prerequisite
- This flag has no prerequisites of its own (simpler removal)

**Fail criteria (hard blocker):**
- Other flags depend on this flag as a prerequisite: removing it would break their targeting logic

### 4. Code References

**Check:** If available, use `check-removal-readiness` which includes code reference statistics. Otherwise, use `get-code-references` to find repositories that reference this flag.

**Pass criteria:**
- No code references found, or references only exist in the current repository (about to be cleaned up)

**Caution criteria:**
- Code references exist in multiple repositories: flag removal in code needs to be coordinated

**Note:** Code reference scanning has limitations. It tracks static string matches and may miss dynamic flag key construction (`flag-${name}`) or have false positives from comments/documentation.

### 5. Expiring Targets

**Check:** Look for scheduled expiring targets on the flag.

**Pass criteria:**
- No expiring targets scheduled

**Caution criteria:**
- Expiring targets exist: someone actively set a future removal date. Coordinate with them.

### 6. Flag Type

**Check:** The `temporary` field on the flag.

**Pass criteria:**
- Flag is marked as `temporary`: it was intended to be removed

**Caution criteria:**
- Flag is marked as `permanent`: it may be intentionally long-lived. Confirm with the user before recommending removal.

## Readiness Levels

After running the checklist, categorize the result:

### Safe
All checks pass. No blockers or warnings.
- Recommend proceeding with code removal using the [flag cleanup skill](../../launchdarkly-flag-cleanup/SKILL.md)
- Suggest archival in LaunchDarkly after code changes are deployed

### Caution
No hard blockers, but warnings exist.
- Present each warning with context
- Recommend **archive** (reversible) over **delete** (permanent)
- Suggest addressing warnings first (e.g., remove code references, then re-check)

### Blocked
Hard blockers prevent safe removal.
- Present each blocker with specifics
- For prerequisite dependencies: user must update dependent flags first
- For active targeting: user should toggle off and wait for a cool-down period
- For active status: flag is still being used: don't remove

## Presenting Results

Structure the assessment as:

1. **Verdict**: Lead with safe / caution / blocked
2. **Blockers** (if any): Each with type and actionable detail
3. **Warnings** (if any): Each with type and context
4. **Forward value**: What variation should replace the flag in code (only if safe or caution)
5. **Next steps**: What to do now (proceed with cleanup, address warnings, resolve blockers)
