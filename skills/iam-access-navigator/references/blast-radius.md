# Blast radius / change-safety

Answer "if I touch this, what breaks?" from the account's real state — never by
guessing. Run this before recommending any modification or deletion.

## Identify the target type from its ARN
- `:policy/` → policy
- `:role/` → role
- `:user/` → user

Default traversal depth 2 (max 3).

## Policy target
Paginate `list-entities-for-policy`. Every attached role, user, and group is a
**direct dependent** that loses permission if the policy changes:
- role → "role will lose permissions from this policy"
- group → "all users in this group will lose permissions"

Record attachment count. Note AWS-managed policies (you cannot edit them — a
stable dependency) and skip service-linked roles (name starts
`AWSServiceRoleFor`) unless asked to include them.

## Role target
1. **Trust policy** (`AssumeRolePolicyDocument`) — classify each principal:
   - `Principal: "*"` with no `Condition` → **CRITICAL** exposure
   - `AWS: "*"` → CRITICAL (no condition) / HIGH (with condition)
   - specific `Service` principal → INFO (normal)
   - otherwise → LOW
2. **Reverse references** (depth > 1): scan other roles' trust policies for this
   role's ARN in `Principal.AWS`. Those roles can assume the target; changing its
   trust may break their workflows. Flag them `can_assume_target`.
3. **Attached + inline policies** on the role itself.
4. **The role's own privilege** (critical, easy to miss): read managed *and*
   inline policy documents, count actions, detect `*` / admin. This is why a
   role nothing depends on is still not automatically "safe to leave".

## User target
Report group memberships and access keys as dependents ("access key will stop
working if the user is deleted").

## Blast-radius score (0–100, capped)
- dependents > 10 → +40; > 5 → +25; > 0 → +10
- CRITICAL trust principal → +30; HIGH → +15
- service-linked dependents → +20 (AWS-managed, cannot be modified)
- AWS-managed policy dependents → note only, no points (stable dependency)
- **privilege overlay:** admin/wildcard on the target → +40, with the explicit
  warning that *low blast radius means safe to CHANGE, not safe to LEAVE — a
  high-privilege unused role is a prime attack target*; else > 50 actions → +20

Bands and recommendation:
- ≥ 70 CRITICAL — "do not modify without change-management approval and a
  rollback plan"
- ≥ 50 HIGH — "test changes in a non-production environment first"
- ≥ 25 MEDIUM — "have a rollback plan ready"
- else LOW

## Output
`depends_on` (the policies it uses) vs `depended_on_by` (dependents + trust
principals); total impact radius = count of `depended_on_by`; the rating; and the
keyed recommendation. Always pair a change recommendation with a rollback plan
(`rollback.md`) when the rating is medium or higher.
