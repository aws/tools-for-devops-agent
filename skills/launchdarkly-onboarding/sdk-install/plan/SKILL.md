---
name: plan
description: "Generate a minimal LaunchDarkly SDK integration plan from detected stack: choose SDK type(s), dual-SDK server+client when required, files to change, env conventions. Nested under sdk-install; follows detect, precedes apply."
license: Apache-2.0
compatibility: Requires completed or equivalent detect context (see sibling detect skill)
metadata:
  author: launchdarkly
  version: "0.3.0"
---

# Generate integration plan (SDK install)

Based on what you detected, choose the right SDK and plan the minimal set of changes needed.

This skill is nested under [LaunchDarkly SDK Install (onboarding)](../SKILL.md); the parent **Step 2** is **plan**. **Prior:** [Detect repository stack](../detect/SKILL.md). **Next:** [Apply code changes](../apply/SKILL.md).

## Choose the right SDK

Use the [SDK recipes](../../references/sdk/recipes.md) reference to match the detected stack to an SDK. Start with **Top 10 SDKs (start here)** in that file for common stacks; use the **(other)** sections for less common SDKs.

The key decision:

| Project Type | SDK Type | Key Type |
|-------------|----------|----------|
| Backend API, server-rendered app, CLI tool | Server-side SDK | SDK Key |
| Browser SPA (React, Vue, Angular, vanilla JS) | Client-side SDK | Client-side ID |
| iOS or Android native app | Mobile SDK | Mobile Key |
| React Native | Mobile SDK | Mobile Key |
| Flutter (iOS, Android, or desktop **app** targets) | Client-side SDK (Flutter) | Mobile Key |
| Flutter **web** | Client-side SDK (Flutter) | Client-side ID |
| Electron desktop app | Client-side SDK (Node.js) | Client-side ID |
| Cloudflare Workers, Vercel Edge, AWS Lambda@Edge | Edge SDK | SDK Key |
| .NET client (MAUI, Xamarin, WPF, UWP) | Mobile SDK (.NET) | Mobile Key |
| C/C++ client application | Client-side SDK (C/C++) | Mobile Key |
| C/C++ server application | Server-side SDK (C/C++) | SDK Key |
| Haskell server | Server-side SDK (Haskell) | SDK Key |
| Lua server | Server-side SDK (Lua) | SDK Key |
| Roku (BrightScript) | Client-side SDK (Roku) | Mobile Key |

For every supported SDK, package name, install hint, and official **Docs** link, use [SDK recipes](../../references/sdk/recipes.md) and the linked files under [`snippets/`](../../references/sdk/snippets/).

## Dual SDK integrations

Use this section when the user asked for **both** a server-side and a client-side integration, or when the stack clearly needs **two** LaunchDarkly SDKs (e.g. Next.js with server evaluation **and** browser UI flags, separate backend + SPA repos in one workspace target, etc.).

**Do not** "complete" onboarding with a single SDK while **hand-waving** the second (no second package in `package.json`, no second init path, no second recipe followed). Each SDK is a separate product with its own install command and initialization.

For **each** of the two SDKs, the plan must spell out (with no gaps):

**Server-side track:**

1. Recipe / [SDK recipes](../../references/sdk/recipes.md) row or snippet name
2. Package name(s) (exact artifact)
3. Install command (full command from recipe)
4. Dependency file (where the line is added)
5. Entrypoint file(s) (e.g. `instrumentation.ts`, API entry, `main.py`)
6. Env vars (typically `LAUNCHDARKLY_SDK_KEY`)
7. Init summary (where it runs; which doc/snippet)

**Client-side track:**

1. Recipe / snippet name (**different** row than server)
2. Package name(s) (e.g. React Web vs Node server -- must be the **client** artifact)
3. Install command (**second** command -- never implied)
4. Dependency file
5. Entrypoint file(s) (e.g. `app/providers.tsx`, root layout, `main.tsx`)
6. Env vars (bundler-prefixed **client-side ID**, e.g. `NEXT_PUBLIC_...`)
7. Init summary (provider/wrapper/hook from **client** recipe)

If you cannot name **two** packages and **two** entrypoints, you are not done planning -- go back to [SDK recipes](../../references/sdk/recipes.md) and detection.

**Important distinctions:**

- **Next.js**: Server-side SDK for API routes / server components / RSC contexts that evaluate on the server; React client SDK for client components. If the user requested **both**, the plan lists **both** tracks in full. If they only want one surface to start, state that explicitly in the plan.
- **Node.js**: If it's a backend service (Express, Fastify, etc.), use the server-side SDK. There is also a [Node.js client SDK](https://launchdarkly.com/docs/sdk/client-side/node-js) for desktop/Electron apps.
- **React**: If it's a standalone SPA, use `launchdarkly-react-client-sdk`. If it's part of Next.js, see above.
- **.NET**: Use the **server** SDK (`LaunchDarkly.ServerSdk`) for ASP.NET and backend services. For MAUI, Xamarin, WPF, and UWP, use the **.NET mobile SDK** (`LaunchDarkly.ClientSdk`, **mobile key**) -- [SDK recipes -- .NET (Client)](../../references/sdk/recipes.md#net-client). **Blazor WebAssembly** (and other browser-hosted .NET client UI) still uses `LaunchDarkly.ClientSdk` but with a **client-side ID**, not a mobile key -- see the same recipe.
- **Flutter**: Use the Flutter client SDK (`launchdarkly_flutter_client_sdk` -- [SDK recipes -- Flutter](../../references/sdk/recipes.md#flutter)). Use a **mobile key** for typical iOS/Android/desktop **app** builds; use the **client-side ID** (and the project's pattern for public env vars) for **Flutter web**. If the user ships multiple targets, confirm which to wire first or plan separate env/config per target.

## Plan the changes

Your integration plan should identify exactly:

### 1. Files to modify

Use the information gathered during [Detect repository stack](../detect/SKILL.md) -- specifically the detected package manager, dependency file, and application entrypoint:

- **Dependency file**: The file identified during detection (e.g., `package.json`, `requirements.txt`, `go.mod`) -- use the detected package manager to add the SDK
- **Entrypoint file**: The application entrypoint identified during detection -- where SDK initialization code will go. Dual-SDK plans list **two** entrypoints (see [Dual SDK integrations](#dual-sdk-integrations)).
- **Environment/config file**: Prefer `.env` at the integration root for real secrets (create it if it does not exist); ensure `.env` is listed in `.gitignore` there. Use `.env.example` / `.env.sample` for placeholders only. If the project does not use dotenv, follow its existing config pattern -- see [Apply code changes](../apply/SKILL.md) Step 2 for consent, writing keys, and hybrid server+client cases.

### 2. Code changes

For **each SDK** in scope (one or two tracks), describe the specific changes:

1. **Add SDK dependency** -- the install command from the SDK recipe (repeat for each package when dual-SDK)
2. **Add SDK import** -- the import statement at the top of that track's entrypoint
3. **Add SDK initialization** -- the init code for that SDK from that recipe/snippet, placed early in the right lifecycle (server vs client)
4. **Configure credentials** -- via environment variable, never hardcoded (SDK key vs client-side ID per track)
5. **Observability plugin (only when the user mentioned observability, session replay, error monitoring, logs, or tracing)** -- the plugin package(s) and the `plugins` entry on that track's client, from [Observability plugin](../../references/sdk/observability-plugin.md). No new env var; the plugin reuses the client's key. For dual-SDK plans, add the matching plugin to each track.

### 3. Environment variable convention

Check how the project handles configuration:

- **`.env`:** If the stack uses dotenv (or you are introducing it for LaunchDarkly), plan to create `.env` at the integration root when it is missing, then add `LAUNCHDARKLY_SDK_KEY`, `LAUNCHDARKLY_CLIENT_SIDE_ID` / bundler-prefixed client ID, or `LAUNCHDARKLY_MOBILE_KEY` as appropriate (see [Apply code changes](../apply/SKILL.md) Step 2 for names, consent before real values, and hybrid server+client cases). Plan to verify `.gitignore` includes `.env` at that root (add the entry if missing, with the same user permission as other repo edits).
- **`.env.example` / `.env.sample`:** If present, plan **placeholder** entries only (no real secrets).
- **Config module or `process.env`:** If the project does not use `.env`, plan to follow the existing pattern for secrets.

## Present the plan

Before making any changes, summarize the plan to the user.

**Single SDK:**

1. Install `[package name]` using `[install command]`
2. Add SDK dependency to `[dependency file]`
3. Add import and initialization to `[entrypoint file]`
4. Add `[env var]` to `.env` (create if missing; real value after user consent)
5. Ensure `.env` is in `.gitignore`
6. Add placeholder to `.env.example` if the project uses one

When observability was requested, add one more line: "Add `[plugin package(s)]` to the client's `plugins` option in `[entrypoint file]`."

Only LaunchDarkly SDK packages will be added unless the user explicitly approves other dependency changes.

**Dual SDK:** Present the same numbered format **separately for each track** (e.g. "Server-side:" steps 1-7, then "Client-side:" steps 1-7), following [Dual SDK integrations](#dual-sdk-integrations). Do not omit the second track.

After presenting the plan:

**D6 -- NON-BLOCKING (proceed unless objected):** Present the plan summary to the user with a note like "Here's what I'm going to do -- say stop or let me know if anything looks wrong." Then **continue into [Apply code changes](../apply/SKILL.md)** without waiting for explicit approval. If the user objects or says something looks wrong, stop and adjust the plan before continuing.

This is intentionally non-blocking to reduce ceremony. The plan is visible to the user and they can interrupt at any time. The real safety gates are D7 (secret consent) and D8 (non-LD dependency changes) in the apply step.

If the entrypoint is ambiguous or multiple SDKs could apply, those specific questions **are** blocking -- ask them as part of the plan presentation using your structured question tool and wait for an answer before proceeding.

**Do not** ask for SDK keys, client-side IDs, or mobile keys as part of plan confirmation -- the parent flow collects those at [Apply code changes](../apply/SKILL.md). The **Key type** column above is for technical planning only, not a prompt for secrets.

**Do not** promise or imply that you will upgrade unrelated dependencies to satisfy the latest SDK -- [Apply](../apply/SKILL.md) requires **explicit approval** before any non-LaunchDarkly package changes.

---

**Upon completion:** [Apply code changes](../apply/SKILL.md)
