---
name: apply
description: "Apply LaunchDarkly SDK onboarding: install dependency (or dual-SDK pair), configure env and secrets with consent, add init at entrypoint(s), verify compile. Nested under sdk-install; next is run."
license: Apache-2.0
compatibility: Requires integration plan and LaunchDarkly credentials (see parent onboarding)
metadata:
  author: launchdarkly
  version: "0.3.0"
---

# Apply code changes (SDK install)

Execute the integration plan. Install the SDK(s) and add the minimal code needed to initialize **each** tracked surface.

This skill is nested under [LaunchDarkly SDK Install (onboarding)](../SKILL.md); the parent **Step 3** is **apply**. **Prior:** [Generate integration plan](../plan/SKILL.md). **Next:** [Start the application](../run/SKILL.md).

**Dual SDK:** If the approved plan is **dual SDK** ([plan: Dual SDK integrations](../plan/SKILL.md#dual-sdk-integrations)), you must complete Steps 1-3 **for both tracks** -- **two** packages in the manifest, **two** install commands run (or equivalent), **two** credential lines where needed, **two** inits in **different** entrypoints per recipe. **Do not** claim the second SDK is set up without performing its real install and init. If the plan only listed one track but the user asked for both, **stop** and return to [plan](../plan/SKILL.md) -- do not invent the second half from memory.

**Credential timing:** This is the first nested step where you ask the user for **SDK key / client-side ID / mobile key** (or consent to fetch/write them). Account status is not asked upfront -- it is inferred earlier via MCP OAuth when MCP is already configured or surfaced here at D7 (option 4) if the user has no account yet ([parent Prerequisites](../../SKILL.md#prerequisites)).

## Step 1: Install the SDK dependency

Use the **exact** package or module name and install command from the SDK row you already matched in [SDK recipes](../../references/sdk/recipes.md), with the project's package manager. Do not copy a generic install line from elsewhere -- each recipe names the right artifact.

**Dual SDK:** Run the **install command for Track A**, then the **install command for Track B** (from the plan). Confirm **both** package names appear in `package.json` / `requirements.txt` / lockfile (or the correct package manifest for each language). Skipping the second install is **not** optional when the plan says dual.

After installation, verify the dependency appears in the lock file or dependency manifest (**all** LaunchDarkly packages from the plan).

### Permission before changing other dependencies

**Allowed without asking for extra permission (beyond normal repo-edit consent):** Installing **only** the LaunchDarkly SDK package(s) named in the recipe(s) for this integration (e.g. one server SDK, **or** the **exact server + client pair** listed in a dual-SDK plan -- **both** packages count as in-scope LD installs). When the user asked for observability or session replay, the plugin package(s) from [Observability plugin](../../references/sdk/observability-plugin.md) are in scope too. Use the **minimum** install each recipe specifies (exact package names).

**Requires explicit user approval *before* you run any command or edit manifests:** Any change beyond that scope, including but not limited to:

- Upgrading, downgrading, pinning, or adding **non-LaunchDarkly** packages (peer-dependency "fixes," `npm install X@latest`, `yarn upgrade`, `pnpm update`, bumping React/Node types, transitive lockfile churn, etc.)
- Running **`npm audit fix`**, **bulk updates**, or **replacing** the project's package manager resolution strategy to satisfy the SDK
- Changing **engine** / **packageManager** fields, **resolutions** / **overrides**, or **workspaces** entries for reasons other than adding the LD artifact line

If the package manager reports peer conflicts or install failures:

**D8 -- BLOCKING:** Call your structured question tool now.
- question: "The install reported [specific error]. To fix this, I would need to [specific changes to non-LD packages]. Should I proceed with those additional changes?"
- options:
  - "Yes, make those changes"
  - "No, keep only the LaunchDarkly package -- I'll resolve conflicts myself"
  - "Show me the exact commands first"
- STOP. Do not write the question as text. Do not upgrade an older repo "to match the newest SDK's dependencies" silently. Do not continue until the user selects an option.

If the user **declines** broader changes: keep only the LD package addition if possible, document the conflict, and proceed with placeholders or manual steps.

## Step 2: Add the SDK key to environment configuration

**Never hardcode SDK keys, client-side IDs, or mobile keys in application source files** (only reference them via environment variables).

### Permission before secrets

**D7 -- BLOCKING (MANDATORY -- DO NOT SKIP):** Call your structured question tool now. This decision point exists for security compliance -- the user must explicitly choose how secrets are handled. Skipping this and proceeding to write keys without consent is a critical failure.
- question: "The SDK needs an SDK key (or client-side ID / mobile key) for your environment. How would you like to set up the secret?"
- options:
  - "I'll tell you where to put it"
  - "I'll set up the secret myself -- just tell me what variable name to use"
  - "Write it to a `.env` file for me"
  - "I don't have an account yet -- help me sign up" -> point to the resolved signup URL (see [Source Attribution](../../SKILL.md#source-attribution)), write placeholders and continue (real keys deferred until account is ready)
- STOP. Do not write the question as text. Do not fetch keys from LaunchDarkly or write real values into the repo without the user selecting an option first. Do not infer the answer from context or prior conversation -- always present this choice.

**If the user chooses option 1 ("Tell me where to put it"):**
1. Ask where they want the secret written (file path, secrets manager, etc.)
2. Ask how they want to provide the key: paste it, or have the agent fetch it via MCP/API
3. Write the key **only** to the location the user specified
4. Do not create a `.env` or modify any other file

**If the user chooses option 2 ("I'll set it up myself"):**
1. Tell them the variable name(s) they need to set (see the table below)
2. Link them to the right dashboard page. When the project key and environment key are known: **`https://app.launchdarkly.com/projects/{projectKey}/settings/environments/{envKey}/keys`**. When only the project key is known: **`https://app.launchdarkly.com/projects/{projectKey}/settings/environments`** and tell them to select the environment. When neither is known: **`https://app.launchdarkly.com/projects`** and tell them to navigate to **Settings > Environments** to find the key.
3. Wait for the user to confirm the secret is in place before proceeding to Step 3
4. Do not fetch, write, or handle the key value at all

**If the user chooses option 3 ("Write it to a `.env` file for me"):**
1. Ask how they want to provide the key: paste it, or have the agent fetch it via MCP/API
2. Follow the [Write to `.env`](#write-to-env-when-the-user-consents) section below
3. Ensure `.env` is in `.gitignore` before writing any real values

**If the user chooses option 4 ("I don't have an account yet"):**
1. Point them to the resolved signup URL (see [Source Attribution](../../SKILL.md#source-attribution))
2. Explain that SDK key setup requires an account -- they can complete setup after signing up
3. Ensure `.env` is in `.gitignore` before writing (same check as option 3 / [Write to `.env`](#write-to-env-when-the-user-consents))
4. Write placeholder variable names to `.env` (no real values) so the code compiles
5. Continue with Step 3 (init code) using the placeholder env var references. The app will fail to connect to LaunchDarkly until real keys are set, which is expected.
6. Note in the onboarding log that key setup is pending account creation

### Fetching keys via MCP

When the user asks the agent to fetch the key (via option 1 or 3 above), use the **`get-environments`** MCP tool (if configured). Call it with the project key — the response includes each environment's **SDK key**, **client-side ID**, and **mobile key**. Do **not** make separate API requests for individual keys when `get-environments` already returns them.

```
get-environments({ request: { projectKey: "PROJECT_KEY" } })
```

**Security: Treat MCP responses containing keys as sensitive.** Write keys only to the location the user chose without echoing full key values in chat responses. Keys in agent conversation history or logs may persist beyond the session.

Pick the correct key type from the matching environment in the response (see table below). If MCP is not configured, direct the user to the LaunchDarkly dashboard to retrieve their keys: `https://app.launchdarkly.com/projects/{PROJECT_KEY}/settings/environments/{ENV_KEY}/keys`.

### Variable names and where values come from

| SDK Type | Variable name (typical) | Source in LaunchDarkly |
|----------|-------------------------|-------------------------|
| Server-side | `LAUNCHDARKLY_SDK_KEY` | `get-environments` response → environment → SDK key |
| Client-side | Logical / bundler-prefixed name (see below) | `get-environments` response → environment → Client-side ID |
| Mobile | `LAUNCHDARKLY_MOBILE_KEY` | `get-environments` response → environment → Mobile key |

**Client-side (browser) projects:** The LaunchDarkly value is still the Client-side ID. In `.env`, use a name the bundler exposes to client code:

| Stack | `.env` key | Read in code |
|-------|------------|--------------|
| Create React App | `REACT_APP_LAUNCHDARKLY_CLIENT_SIDE_ID` | `process.env.REACT_APP_LAUNCHDARKLY_CLIENT_SIDE_ID` |
| Vite | `VITE_LAUNCHDARKLY_CLIENT_SIDE_ID` | `import.meta.env.VITE_LAUNCHDARKLY_CLIENT_SIDE_ID` |
| Next.js | `NEXT_PUBLIC_LAUNCHDARKLY_CLIENT_SIDE_ID` | `process.env.NEXT_PUBLIC_LAUNCHDARKLY_CLIENT_SIDE_ID` |

Other stacks may use different prefixes or plain `LAUNCHDARKLY_CLIENT_SIDE_ID` -- match what the project already uses for public env vars.

### Write to `.env` (when the user consents)

Use the **integration root** for the file path (repo root or the target package in a monorepo -- see [Detect repository stack](../detect/SKILL.md)).

1. **Create or update `.env`:** If `.env` does not exist, create it. If it exists, **append or update** only the LaunchDarkly lines -- do not remove unrelated variables.
2. **Add what the integration needs:**
   - Server-only: `LAUNCHDARKLY_SDK_KEY=...`
   - Client/browser: the **client-side ID** under the correct bundler-prefixed key (e.g. `VITE_LAUNCHDARKLY_CLIENT_SIDE_ID=...`).
   - **Full-stack or hybrid (e.g. Next.js, SSR + client):** add **both** the server SDK key and the client-side ID lines when both SDKs are in use.
   - Mobile: `LAUNCHDARKLY_MOBILE_KEY=...` when applicable.
3. **`.gitignore`:** Ensure `.env` is listed in `.gitignore` at the same root where you created `.env` (or the nearest relevant ignore file in a monorepo). If the entry is missing, add it -- only after the user has agreed to repo changes (same permission scope as writing `.env`). Do not commit files that contain real secrets.
4. **`.env.example` / `.env.sample`:** If the project uses one, add **placeholder** entries only (no real keys), so teammates know which variables to set.

If the project does not use dotenv and relies on a config module or hosted secrets, follow existing patterns there instead -- the same D7 consent above still applies before writing real values into any file.

## Step 3: Add SDK initialization code

Initialization shape **depends on which SDK was chosen** during detection and planning. This skill does not include copy-paste samples per SDK -- using the wrong snippet (e.g. React Web when the recipe is Node server) will mislead you.

**Source of truth (use in order, repeat per track when dual-SDK):**

1. **[SDK recipes](../../references/sdk/recipes.md)** -- the row for **this** track's SDK: install is Step 1 above; for init, follow the **SDK detail** / doc links listed there.
2. **SDK detail files** under [`snippets/`](../../references/sdk/snippets/) (when linked from the recipe) -- curated links and, for many SDKs, a full onboarding sample aligned with that SDK.
3. **LaunchDarkly's official docs** for that SDK (URLs from the recipe or detail file) -- use their entrypoint and async patterns (e.g. React Web: [React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web)).

Wire credentials using Step 2: server SDKs use `LAUNCHDARKLY_SDK_KEY`; client/browser SDKs use the client-side ID with the **bundler-prefixed** env names from Step 2 where applicable.

Add imports and init to the **application entrypoint** for **that** track (or the target package's entrypoint in a monorepo -- see [Detect repository stack](../detect/SKILL.md)). **Dual SDK:** server init goes in the **server** entrypoint from the plan; client/provider init goes in the **client** entrypoint -- **never** a single shared block that pretends to cover both unless the official docs for that stack explicitly prescribe one pattern for both.

**Observability plugin:** When the plan includes it, add the plugin(s) to the `plugins` option of the client you just initialized, following [Observability plugin](../../references/sdk/observability-plugin.md). Do not create a second client or a second credential.

### Key principles

1. **Import at the top** of the file with other imports
2. **Initialize early** in the application lifecycle **for that runtime** (Node server vs browser)
3. **Wait for initialization** before evaluating flags when the SDK supports it
4. **Handle errors** -- log failures but don't crash the application
5. **Match existing code style** -- same patterns (async/await, callbacks, modules CommonJS vs ESM) as the rest of the codebase
6. **Use the right pattern per surface** -- server-side init from the **server** recipe in server code; client/provider init from the **client** recipe in client code. **Do not** reuse one snippet for both tracks or skip the second track's init when the plan is dual-SDK.

## Step 4: Verify the code compiles

After making changes:

1. Run the project's build or compile step
2. Run the linter if one is configured
3. Fix any import errors or type issues **without** upgrading unrelated dependencies unless the user approved that scope ([Permission before changing other dependencies](#permission-before-changing-other-dependencies))

Do not proceed to the next step if the code doesn't compile.

---

**Upon completion:** [Start the application](../run/SKILL.md)
