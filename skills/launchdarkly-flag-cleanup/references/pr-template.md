# PR Template for Flag Removal

Use this template when creating pull requests for flag cleanup.

```markdown
## Flag Removal: `{flag-key}`

### Removal Summary
- **Forward Value**: `{variation value being preserved}`
- **Critical Environments**: {list environments}
- **Status**: ✅ Ready for removal / ⚠️ Proceed with caution / ❌ Not ready

### Removal Readiness Assessment

**Configuration Analysis:**
| Environment | State | Serving | Rules | Targets |
|-------------|-------|---------|-------|---------|
| production | ON/OFF | `{value}` | none/present | none/count |
| {other env} | ON/OFF | `{value}` | none/present | none/count |

**Lifecycle Status:**
| Environment | Status | Evaluations (7d) |
|-------------|--------|------------------|
| production | launched/active/inactive/new | {count} |
| {other env} | launched/active/inactive/new | {count} |

**Code References:**
- Repositories with references: `{count}`
- This PR addresses: `{current repo}`
- Other repos requiring cleanup: `{list if any}`

### Changes Made
- Removed flag evaluation calls: `{count}` occurrences
- Files modified: `{list files}`
- Preserved behavior: `{describe what code now does}`
- Cleaned up: `{list dead code removed}`

### Risk Assessment

{Explain why this change is safe. Address:}
- Why the forward value is correct
- Any edge cases considered
- Impact on other environments (if any)

### Reviewer Checklist

- [ ] Forward value matches production behavior
- [ ] All flag references removed
- [ ] No unrelated changes included
- [ ] Tests pass (if applicable)
- [ ] Dead code properly removed

### Post-Merge Actions

- [ ] Archive flag in LaunchDarkly (after deployment confirmed)
- [ ] Notify other teams if they have code references
```

## Example: Ready for Removal

```markdown
## Flag Removal: `new-checkout-flow`

### Removal Summary
- **Forward Value**: `true`
- **Critical Environments**: production, prod-eu
- **Status**: ✅ Ready for removal

### Removal Readiness Assessment

**Configuration Analysis:**
| Environment | State | Serving | Rules | Targets |
|-------------|-------|---------|-------|---------|
| production | ON | `true` | none | none |
| prod-eu | ON | `true` | none | none |

**Lifecycle Status:**
| Environment | Status | Evaluations (7d) |
|-------------|--------|------------------|
| production | launched | 142,531 |
| prod-eu | launched | 89,203 |

**Code References:**
- Repositories with references: 2
- This PR addresses: `checkout-service`
- Other repos requiring cleanup: `mobile-app`

### Changes Made
- Removed flag evaluation calls: 3 occurrences
- Files modified: `CheckoutController.ts`, `CheckoutService.ts`, `checkout.test.ts`
- Preserved behavior: Always renders new checkout experience
- Cleaned up: Removed `renderOldCheckout()` function and related imports

### Risk Assessment

This change is safe because:
- Both production environments serve `true` to 100% of traffic
- Flag has been at 100% for 47 days with no issues
- No targeting rules or individual overrides exist
- The new checkout flow has been fully validated

### Post-Merge Actions

- [ ] Archive flag in LaunchDarkly (after deployment confirmed)
- [ ] Create follow-up ticket for mobile-app cleanup
```

## Example: Proceed with Caution

```markdown
## Flag Removal: `legacy-api-endpoint`

### Removal Summary
- **Forward Value**: `false`
- **Critical Environments**: production
- **Status**: ⚠️ Proceed with caution

### Removal Readiness Assessment

**Configuration Analysis:**
| Environment | State | Serving | Rules | Targets |
|-------------|-------|---------|-------|---------|
| production | OFF | `false` | none | none |

**Lifecycle Status:**
| Environment | Status | Evaluations (7d) |
|-------------|--------|------------------|
| production | inactive | 0 |

⚠️ **Warning**: Zero evaluations in the last 7 days. This flag may be:
- Dead code that's safe to remove
- Used by a batch job or infrequent process
- Referenced but never called

**Recommendation**: Verify with the team that this code path is truly unused before merging.
```
