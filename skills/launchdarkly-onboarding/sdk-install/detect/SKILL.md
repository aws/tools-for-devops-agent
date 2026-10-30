---
name: detect
description: "Detect repository stack for LaunchDarkly SDK onboarding: languages, frameworks, package managers, monorepo targets, entrypoints, existing LD usage. Nested under sdk-install; next is plan."
license: Apache-2.0
compatibility: Requires access to the project repository
metadata:
  author: launchdarkly
  version: "0.2.0"
---

# Detect repository stack (SDK install)

Before installing anything, you must understand the project. Identify what the project is built with and whether LaunchDarkly is already present.

This skill is nested under [LaunchDarkly SDK Install (onboarding)](../SKILL.md); the parent **Step 1** is **detect**. **Next:** [Generate integration plan](../plan/SKILL.md) unless the decision tree sends you elsewhere.

### 1. Language and framework

Look for the indicator files below (and related root layout), then read the relevant manifests to infer language and framework.

Look for these files to identify the stack:

| File | Language/Framework |
|------|--------------------|
| `package.json` | JavaScript/TypeScript (check for React, Next.js, Vue, Angular, Express, React Native, Electron, etc.) |
| `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py` | Python (check for Django, Flask, FastAPI) |
| `go.mod` | Go (check for Gin, Echo, Fiber, Chi) |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | Java/Kotlin (check for Spring, Quarkus, Android) |
| `Gemfile` | Ruby (check for Rails, Sinatra) |
| `*.csproj`, `*.sln`, `*.fsproj` | .NET/C# (check for ASP.NET, MAUI, Xamarin, WPF, UWP) |
| `composer.json` | PHP (check for Laravel, Symfony) |
| `Cargo.toml` | Rust (check for Actix, Axum, Rocket) |
| `pubspec.yaml` | Flutter/Dart |
| `Package.swift`, `Podfile`, `*.xcodeproj` | Swift/iOS |
| `AndroidManifest.xml` | Android (also check `build.gradle` for `com.android`) |
| `rebar.config`, `mix.exs` | Erlang/Elixir |
| `CMakeLists.txt`, `Makefile` (with C/C++ patterns) | C/C++ (check for `#include` patterns) |
| `*.cabal`, `stack.yaml` | Haskell |
| `*.lua`, `rockspec` | Lua |
| `manifest`, `*.brs` | Roku (BrightScript) |
| `wrangler.toml` | Cloudflare Workers (edge SDK) |
| `vercel.json` with edge functions | Vercel Edge (edge SDK) |

Read the dependency file to identify the specific framework. For `package.json`, check both `dependencies` and `devDependencies`.

If you cannot identify the language or framework:

**D5 -- BLOCKING:** Call your structured question tool now.
- question: "I couldn't detect the project's language or framework. Which SDK would you like to use?"
- options: Present the available SDKs from [SDK recipes](../../references/sdk/recipes.md) as selectable options.
- STOP. Do not write the question as text. Do not continue until the user selects an option.

### 2. Package manager

Identify how the project installs dependencies:

| Indicator | Package Manager |
|-----------|----------------|
| `package-lock.json` | npm |
| `yarn.lock` | yarn |
| `pnpm-lock.yaml` | pnpm |
| `bun.lockb` | bun |
| `Pipfile.lock` | pipenv |
| `poetry.lock` | poetry |
| `go.sum` | go modules |
| `Gemfile.lock` | bundler |

Use the detected package manager for all install commands. If multiple lock files exist, prefer the one that was most recently modified.

### 3. Monorepo layout

Some repositories host multiple packages or services. Look for these indicators:

| File / pattern | Tool or layout |
|----------------|----------------|
| `pnpm-workspace.yaml` | pnpm workspaces |
| `lerna.json` | Lerna |
| `nx.json` | Nx |
| `turbo.json` | Turborepo |
| `rush.json` | Rush |
| `packages/` directory with multiple `package.json` files | Generic monorepo |

When any of these apply, **do not assume the repo root is the integration target**:

**D5 -- BLOCKING:** Call your structured question tool now.
- question: "This is a monorepo. Which package, app, or service should I integrate LaunchDarkly into?"
- options: List the discovered packages/apps as selectable options.
- STOP. Do not write the question as text. Do not continue until the user selects an option.

Then run the rest of this detect step -- language, package manager, entrypoint, and SDK search -- **in that target directory** (and its subtree), not only at the root.

### 4. Application entrypoint

Find the main file where the application starts. In a monorepo, apply the patterns below within the chosen package after [section 3 Monorepo layout](#3-monorepo-layout). Common patterns:

- **Node.js (server)**: Check `package.json` `"main"` field, or look for `index.js`, `server.js`, `app.js`, `src/index.ts`
- **NestJS**: Look for `src/main.ts` or `src/main.js`
- **Python**: Look for `app.py`, `main.py`, `manage.py`, `wsgi.py`, or the `[tool.poetry.scripts]` section
- **Go**: Look for `main.go` or `cmd/*/main.go`
- **Java**: Search for `public static void main` or `@SpringBootApplication`
- **Ruby**: Look for `config.ru`, `config/application.rb`
- **React/Vue/Angular**: Look for `src/index.tsx`, `src/main.tsx`, `src/App.tsx`, `src/main.ts`
- **Next.js**: App Router -- `app/layout.tsx` or `app/layout.js` (root layout). Pages Router -- `pages/_app.tsx` or `pages/_app.js`
- **React Native**: Look for `App.tsx`, `App.js`, `index.js` (with `AppRegistry.registerComponent`)
- **Electron**: Check `package.json` `"main"`; common paths include `main.js` or `src/main.ts`
- **JavaScript (browser)**: Look for `index.html`, `src/index.js`, or bundler entry in `webpack.config.js` / `vite.config.ts`
- **Flutter**: Look for `lib/main.dart`
- **Swift/iOS**: Look for `AppDelegate.swift`, `SceneDelegate.swift`, or `@main` struct
- **Android**: Look for `MainActivity.java` or `MainActivity.kt`

### 5a. Classify workspace confidence

After sections 1-4, classify the workspace into **one of three states** before continuing. This classification determines how the rest of the flow proceeds.

| State | Meaning | Criteria |
|-------|---------|----------|
| **Clear app** | A runnable application was found | Language/framework detected, a real entrypoint exists, dependency manifest is present with application dependencies |
| **Unclear / weak evidence** | Something is present but it does not clearly represent a runnable app | Stray or minimal `package.json` (e.g. only devDependencies, no scripts), isolated config/manifest files, theme or config-only folders, token/fixture JSON, lockfiles without corresponding source, or multiple conflicting indicators with no dominant app structure |
| **No app found** | No recognizable application structure was detected | No dependency manifests, no entrypoints, no source files matching known patterns, or the workspace is empty / contains only documentation |

**Weak evidence must not be treated as confirmation.** Examples of weak evidence:

- A `package.json` with no `scripts` section and no application source files
- A lone `requirements.txt` in a directory of data files or notebooks
- Config, theme, or fixture directories with manifests that do not represent a runnable service
- Monorepo roots where the real apps live in subdirectories but none was selected

**Branching by state:**

- **Clear app** → continue to [section 6 (Existing LaunchDarkly SDK)](#6-existing-launchdarkly-sdk) and then SDK confirmation.

- **Unclear / weak evidence:**

**D5-UNCLEAR -- BLOCKING:** Call your structured question tool now.
- question: "I found some project files, but I'm not confident I've identified the right application to integrate. Can you point me to the correct app folder?"
- context: Briefly describe what you found and why it's ambiguous (e.g., "There's a `package.json` at the root, but it has no start script and no application source files").
- options:
  - Present any candidate folders you detected as selectable options
  - "It's somewhere else -- I'll tell you the path"
  - "There is no app yet -- help me create a demo"
- STOP. Do not make code changes, install packages, or generate an integration plan until the user confirms the target. Do not continue until the user selects an option.

After the user points to the correct folder, re-run detection (sections 1-4) scoped to that folder.

- **No app found:**

Tell the user clearly: "I didn't find a runnable application in this workspace." Then offer two paths:

**D5-NOAPP -- BLOCKING:** Call your structured question tool now.
- question: "I didn't find a runnable application in this workspace. How would you like to proceed?"
- options:
  - "Point me to the right folder -- the app is somewhere else"
  - "Create a minimal demo app so I can try LaunchDarkly"
- STOP. Do not continue until the user selects an option.

If the user chooses "point me to the right folder," re-run detection scoped to the path they provide. If they choose "create a demo app," create a minimal runnable app in a **new subfolder** (e.g. `launchdarkly-demo/`) using the simplest stack you can scaffold (Node.js + Express or a static HTML page are good defaults), then continue detection from that subfolder.

**Do not** declare onboarding complete unless the app target has been confirmed and the app can actually run.

### 6. Existing LaunchDarkly SDK

Search the codebase for existing LaunchDarkly usage:

```
Search for: launchdarkly, ldclient, ld-client, LDClient, @launchdarkly, launchdarkly-
```

Check:

- Is the SDK already in the dependency file?
- Is there initialization code?
- Is it properly configured or partially set up?
- Are there already feature flag evaluations?

## SDK confirmation

After detecting the stack, confirm the SDK choice with the user:

- **If one SDK is clearly the right fit**: Present your recommendation and get confirmation:

**D5 -- BLOCKING:** Call your structured question tool now.
- question: "Based on what I found, I recommend the [SDK name] SDK. Does that look right?"
- options:
  - "Yes, proceed with that SDK" -> continue to plan
  - "No, I want a different one" -> let user specify
- STOP. Do not write the question as text. Do not continue until the user selects an option.

- **If multiple SDKs could apply** (e.g., a Next.js project with both server and client components):
  - **If the user already asked for both** (e.g. "frontend and backend," "server + browser," "API and SPA"): Treat that as a **dual-SDK** scope. Proceed to [Generate integration plan](../plan/SKILL.md) with **both** SDKs in scope -- do **not** plan or implement only one and assume the other is "covered."
  - **If scope is unclear**:

**D5 -- BLOCKING:** Call your structured question tool now.
- question: "This project has both server-side and client-side surfaces. Which do you want to integrate?"
- options:
  - "Server-side only"
  - "Client-side only"
  - "Both server-side and client-side"
- STOP. Do not write the question as text. Do not continue until the user selects an option.

If they choose **both**, the plan must include **two** concrete integrations (see [plan: Dual SDK integrations](../plan/SKILL.md#dual-sdk-integrations)).

- **If you cannot determine the right SDK**: Present the available options from the [SDK recipes](../../references/sdk/recipes.md) as selectable options in your question tool and use the same blocking pattern above.

## Decision tree

After detection and confirmation:

- **No app found or unclear** --> Already handled by D5-NOAPP / D5-UNCLEAR in [section 5a](#5a-classify-workspace-confidence). Do not proceed to plan until the user confirms a real app target.
- **SDK already installed and initialized** --> If the user asked for observability, add the plugin to the existing init first ([Observability plugin](../../references/sdk/observability-plugin.md)). Then skip to the parent skill's [Step 4: First Flag](../../SKILL.md#step-4-first-flag), unless onboarding already finished and this is a follow-up request.
- **SDK installed but not initialized** --> Skip to [Apply code changes](../apply/SKILL.md) (just add init code)
- **SDK not present** --> Continue to [Generate integration plan](../plan/SKILL.md)
- **Multiple targets detected (e.g., frontend + backend)** --> If the user wants **both** SDKs (confirmed via D5 above), continue to [Generate integration plan](../plan/SKILL.md) with **dual-SDK** scope (two packages, two entrypoints). If they want **one** surface only, plan for that single SDK.
- **Language not detected** --> Already handled by the D5 blocking question in [section 1](#1-language-and-framework).

---

**Upon completion (normal path):** [Generate integration plan](../plan/SKILL.md)
