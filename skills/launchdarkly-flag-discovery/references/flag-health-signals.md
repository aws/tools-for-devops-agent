# Flag Health Signals

How to interpret the data you get back from LaunchDarkly when assessing flag health.

## Lifecycle States

Every flag in every environment has a lifecycle state. Here's what each one means and what action it implies:

| State | Meaning | Action |
|-------|---------|--------|
| `new` | Flag was recently created, hasn't received meaningful traffic | Leave alone: still being set up |
| `active` | Flag is receiving SDK evaluations and serving variations | Healthy, doing its job |
| `launched` | Flag is on, serving a single variation to everyone, no recent changes | Candidate for cleanup: rollout is complete |
| `inactive` | Flag hasn't received SDK evaluations in a while | Strong candidate for cleanup |

## Staleness Signals

| Signal | How to check | Interpretation |
|--------|-------------|----------------|
| **Last requested date** | `status.lastRequested` on the flag | How recently an SDK evaluated this flag. Older = more stale. |
| **Inactive duration** | Compare `lastRequested` to today | 30+ days: likely stale. 7-30 days: might be infrequent. <7 days: probably active. |
| **Never requested** | `lastRequested` is null | Flag was created but never evaluated by any SDK. Possibly abandoned during development. |
| **Flag age** | Compare `creationDate` to today | Old temporary flags that are inactive are strong cleanup candidates. |

## Targeting Complexity

The more complex a flag's targeting, the more carefully you need to assess it:

| Indicator | What to check | Implications |
|-----------|--------------|--------------|
| **Rules count** | Number of targeting rules | More rules = more contexts depending on this flag = higher removal risk |
| **Individual targets** | Users/contexts individually targeted | Someone specifically configured these: check before removing |
| **Prerequisites** | Other flags that depend on this flag | **Hard blocker**: cannot remove without updating dependent flags |
| **Percentage rollout** | Fallthrough uses weighted variations | Flag is mid-rollout: not ready for removal |

## Cross-Environment Signals

Use `get-flag-status-across-envs` to build a complete picture:

| Pattern | Interpretation |
|---------|---------------|
| Inactive everywhere | Safe to consider for removal |
| Launched everywhere | Rollout complete: candidate for code cleanup |
| Active in production, inactive in staging | Normal: production is the source of truth |
| Inactive in production, active in staging | Unusual: might be pre-release, or staging is stale |
| Mixed states across environments | Needs investigation: don't recommend action without understanding why |

## Decision Matrix

Combine signals to reach a recommendation:

| Temporary? | State | Age | Dependencies | Recommendation |
|-----------|-------|-----|-------------|----------------|
| Yes | Inactive 30+ days | Any | None | **Strong cleanup candidate** |
| Yes | Launched | Any | None | **Ready to hardcode and remove** |
| Yes | Never requested, 7+ days old | Any | None | **Likely abandoned: verify and remove** |
| Yes | Active | Any | Any | **Leave alone: actively used** |
| No | Inactive 30+ days | Any | None | **Ask the user**: permanent flags may be intentionally dormant |
| No | Launched | Any | None | **Ask the user**: may want to keep as permanent config |
| Any | Any | Any | Has dependents | **Cannot remove**: update dependents first |
| Any | Active in some envs | Any | Any | **Needs investigation**: understand why states differ |
