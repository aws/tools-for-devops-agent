---
title: SDK Recipes
description: "Detection patterns, install hints, official doc links, and a per-SDK detail file under references/sdk/snippets/ for every LaunchDarkly SDK in the index"
---

# SDK Recipes

Use this reference to match a detected tech stack to the correct LaunchDarkly SDK.

**Field | Value** tables in this file are the **index layer**: package name, what to look for in the repo (detect files/patterns), a one-line install hint, and the official **Docs** link. Use them first to choose the right SDK and command—**before** opening a detail file.

Each recipe links to an **SDK detail** file under [`snippets/`](snippets/). Open that file for curated links to official docs, samples, and package registries. Ten of those files also include a **copy-paste onboarding sample**; the rest are pointer-only—follow LaunchDarkly's docs for install and initialization. Never commit real keys. Treat each **Docs** link in the table as canonical for API details and migrations.

> **Source of truth**: Official LaunchDarkly SDK documentation is authoritative. Prefer each recipe's **Docs** link over summaries here.

**Observability and session replay:** This file covers the feature-management SDKs only. When the user asks for observability, session replay, error monitoring, logs, or tracing, use [Observability plugin](observability-plugin.md) for the plugin package and `plugins` wiring per stack.

## Top 10 SDKs (start here)

These are the most common stacks—check here first before scanning less common SDKs below.

### React (Web)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-react-client-sdk` |
| Detect files | `package.json` |
| Detect patterns | `react`, `react-dom`, `"react":` |
| Install | `npm install launchdarkly-react-client-sdk` |
| Flag key behavior | **camelCase by default.** `useFlags()` transforms `my-flag-key` → `myFlagKey`. Disable with `reactOptions: { useCamelCaseFlagKeys: false }` on the provider. When wiring first-flag code, use the camelCased form unless the project disables it. |
| Docs | [React SDK reference](https://launchdarkly.com/docs/sdk/client-side/react) · [React Web SDK reference](https://launchdarkly.com/docs/sdk/client-side/react/react-web) |

**SDK detail:** [`snippets/react-web-sdk.md`](snippets/react-web-sdk.md) (includes onboarding sample)

**API:** Prefer **`asyncWithLDProvider`** with **`timeout`** (seconds; recommend **1–5**) so the app renders after the JS client initializes; alternatively **`withLDProvider`** if you initialize after mount. See [Initialize the client](https://launchdarkly.com/docs/sdk/client-side/react/react-web).

**Next.js:** If `next` is present, this **client** recipe covers browser/client-component flows; server routes and Server Components usually also need **[Node.js (Server)](#nodejs-server)** and an **SDK key** there—see the **Next.js** note under that recipe and [Generate integration plan](../../sdk-install/plan/SKILL.md).

### JavaScript (Browser)

| Field | Value |
|-------|-------|
| Package | `@launchdarkly/js-client-sdk` |
| Detect files | `package.json`, `index.html` |
| Detect patterns | `webpack`, `vite`, `parcel`, `rollup`; use when not using React / Vue wrappers |
| Install | `npm install @launchdarkly/js-client-sdk` |
| Docs | [JavaScript SDK reference](https://launchdarkly.com/docs/sdk/client-side/javascript) |

**SDK detail:** [`snippets/javascript-browser-sdk.md`](snippets/javascript-browser-sdk.md) (includes onboarding sample)

**API vs. other SDKs:** The current browser package is **`@launchdarkly/js-client-sdk`**: **`createClient`**, **`start()`**, then **`waitForInitialization({ timeout })`** (check `result.status`). See the [browser SDK API docs](https://launchdarkly.github.io/js-core/packages/sdk/browser/docs/). The legacy npm name `launchdarkly-js-client-sdk` (v3) used **`initialize()`** without `start()`—do not mix that flow with v4.

### Node.js (Server)

| Field | Value |
|-------|-------|
| Package | `@launchdarkly/node-server-sdk` |
| Detect files | `package.json` |
| Detect patterns | `express`, `fastify`, `koa`, `hapi`, `nestjs`, `next` (API routes), `"type": "module"` |
| Install | `npm install @launchdarkly/node-server-sdk` |
| Docs | [Node.js SDK reference (server-side)](https://launchdarkly.com/docs/sdk/server-side/node-js) |

**SDK detail:** [`snippets/node-server-sdk.md`](snippets/node-server-sdk.md) (includes onboarding sample)

**Next.js:** `next` in **Detect patterns** only signals that the **server-side** Node SDK may apply (API routes / Route Handlers, Server Components, server-only code). **Client components** in the browser still need the **[React (Web)](#react-web)** recipe (`launchdarkly-react-client-sdk` and a client-side ID)—do **not** silently pick only the Node server SDK for a full-stack Next app. Plan one or both SDKs depending on where flags are evaluated; align with [Generate integration plan](../../sdk-install/plan/SKILL.md) (Next.js callout there).

### Python (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-server-sdk` ([PyPI](https://pypi.org/project/launchdarkly-server-sdk/)) |
| Detect files | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` |
| Detect patterns | `flask`, `django`, `fastapi`, `starlette` |
| Install | `pip install launchdarkly-server-sdk` (observability: see [Observability plugin](observability-plugin.md)) |
| Docs | [Python SDK reference](https://launchdarkly.com/docs/sdk/server-side/python) |

**SDK detail:** [`snippets/python-server-sdk.md`](snippets/python-server-sdk.md) (includes onboarding sample)

**API:** **`ldclient.set_config(Config(sdk_key))`** then **`client = ldclient.get()`** (singleton). Forked workers: **`postfork()`**. See [Initialize the client](https://launchdarkly.com/docs/sdk/server-side/python#initialize-the-client).

### React Native

| Field | Value |
|-------|-------|
| Package | `@launchdarkly/react-native-client-sdk` |
| Detect files | `package.json` |
| Detect patterns | `react-native` |
| Install | `npm install @launchdarkly/react-native-client-sdk` |
| Flag key behavior | **camelCase by default.** Same behavior as React Web: `useFlags()` transforms `my-flag-key` → `myFlagKey`. Disable with `reactOptions: { useCamelCaseFlagKeys: false }`. |
| Docs | [React Native SDK reference](https://launchdarkly.com/docs/sdk/client-side/react/react-native) |

**SDK detail:** [`snippets/react-native-sdk.md`](snippets/react-native-sdk.md) (includes onboarding sample)

**API:** **`@launchdarkly/react-native-client-sdk` v10** — **`ReactNativeLDClient`** (mobile key) + **`LDProvider`** + **`identify(context)`** on mount. Non-Expo: add **`@react-native-async-storage/async-storage`** and **`npx pod-install`**. See [React Native SDK reference](https://launchdarkly.com/docs/sdk/client-side/react/react-native).

### .NET (Server)

| Field | Value |
|-------|-------|
| Package | `LaunchDarkly.ServerSdk` ([NuGet](https://www.nuget.org/packages/LaunchDarkly.ServerSdk/)) |
| Detect files | `*.csproj`, `*.sln`, `*.fsproj` (look for `BlazorWebAssembly`, `blazorwasm`, `UseBlazorWebAssembly`, `blazorserver`, or `Microsoft.AspNetCore.Components` / `Blazor` in the project) |
| Detect patterns | `Microsoft.AspNetCore`, `Microsoft.NET`, `Blazor`, `blazor`, `blazorserver` (host/server UI—**not** WASM-only client projects) |
| Install | `dotnet add package LaunchDarkly.ServerSdk` (observability: see [Observability plugin](observability-plugin.md)) |
| Docs | [.NET SDK reference (server-side)](https://launchdarkly.com/docs/sdk/server-side/dotnet) |

**SDK detail:** [`snippets/dotnet-server-sdk.md`](snippets/dotnet-server-sdk.md) (includes onboarding sample)

**API (current docs):** **`LaunchDarkly.Sdk`** / **`LaunchDarkly.Sdk.Server`** — build config with **`Configuration.Builder(sdkKey).StartWaitTime(...).Build()`**, then **`new LdClient(config)`** before **`WebApplication.CreateBuilder` → `Build()`**. Prefer **`LdClient`** as a **singleton** in DI for real services. See [Initialize the client](https://launchdarkly.com/docs/sdk/server-side/dotnet#initialize-the-client).

**Blazor:** **Blazor Server** (and other server-hosted Blazor where .NET runs on the server) → this **server-side** SDK and an **SDK key**. **Blazor WebAssembly** runs in the browser → use **[.NET (Client)](#net-client)** (`LaunchDarkly.ClientSdk`, **Client-side ID**). Inspect `.csproj` / SDK props: WASM projects typically use the Blazor WebAssembly workload or `blazorwasm` / `UseBlazorWebAssembly`; do **not** treat those as server-only.

### Java (Server)

| Field | Value |
|-------|-------|
| Package | `com.launchdarkly:launchdarkly-java-server-sdk` ([Maven Central](https://mvnrepository.com/artifact/com.launchdarkly/launchdarkly-java-server-sdk)) |
| Detect files | `pom.xml`, `build.gradle`, `build.gradle.kts`, `*.kt` (JVM services—see note below) |
| Detect patterns | `spring`, `quarkus`, `micronaut`, `dropwizard`, `kotlin`, `ktor`, `org.jetbrains.kotlin` |
| Install | **Maven** (`pom.xml`) and **Gradle** (Groovy / Kotlin DSL)—see **Install (Maven and Gradle)** below; pin `version` from [SDK releases](https://github.com/launchdarkly/java-core/releases) |
| Docs | [Java SDK reference](https://launchdarkly.com/docs/sdk/server-side/java) |

**SDK detail:** [`snippets/java-server-sdk.md`](snippets/java-server-sdk.md) (includes onboarding sample)

**Install (Maven and Gradle):** [Install the SDK](https://launchdarkly.com/docs/sdk/server-side/java#install-the-sdk) shows **XML** for Maven and **Gradle** coordinates. Match your build file (`pom.xml`, `build.gradle`, or `build.gradle.kts`). Example Gradle shortcut: `implementation 'com.launchdarkly:launchdarkly-java-server-sdk:7.+'` or `implementation("com.launchdarkly:launchdarkly-java-server-sdk:7.+")`.

**API:** **`import com.launchdarkly.sdk.*`** / **`com.launchdarkly.sdk.server.*`** — **`new LDClient(sdkKey)`** (default startup wait), **`isInitialized()`**. See [Initialize the client](https://launchdarkly.com/docs/sdk/server-side/java#initialize-the-client).

**Kotlin (JVM) backends:** For **Ktor**, **Spring Boot + Kotlin**, or other **server-side Kotlin on the JVM**, use this **Java server SDK** (`launchdarkly-java-server-sdk`) from Kotlin code—LaunchDarkly does not ship a separate Kotlin server artifact. `build.gradle.kts` plus `.kt` sources without Android-only signals should still match here. **Android** apps (Kotlin or Java) that talk to LaunchDarkly from the device use the **[Android](#android)** client SDK recipe, not this server SDK.

### Go (Server)

| Field | Value |
|-------|-------|
| Package | `github.com/launchdarkly/go-server-sdk/v7` |
| Detect files | `go.mod`, `go.sum` |
| Detect patterns | `net/http`, `gin`, `echo`, `fiber`, `chi` |
| Install | `go get github.com/launchdarkly/go-server-sdk/v7` |
| Docs | [Go SDK reference](https://launchdarkly.com/docs/sdk/server-side/go) |

**SDK detail:** [`snippets/go-server-sdk.md`](snippets/go-server-sdk.md) (includes onboarding sample)

### Swift / iOS

| Field | Value |
|-------|-------|
| Package | `LaunchDarkly` ([CocoaPods](https://cocoapods.org/pods/LaunchDarkly); SPM / Carthage via GitHub) |
| Detect files | `Package.swift`, `Podfile`, `Cartfile`, `*.xcodeproj` |
| Detect patterns | `UIKit`, `SwiftUI`, `ios` |
| Install | **SPM**, **CocoaPods**, or **Carthage** — see [Install the SDK](https://launchdarkly.com/docs/sdk/client-side/ios#install-the-sdk) and [`ios-client-sdk.md`](snippets/ios-client-sdk.md); pin versions from [SDK releases](https://github.com/launchdarkly/ios-client-sdk/releases) |
| Docs | [iOS SDK reference](https://launchdarkly.com/docs/sdk/client-side/ios) · [Set up iOS SDK](https://launchdarkly.com/docs/home/onboarding/ios) (onboarding) |

**SDK detail:** [`snippets/ios-client-sdk.md`](snippets/ios-client-sdk.md) (includes onboarding sample)

**API:** **`LDConfig(mobileKey:autoEnvAttributes:)`**, **`LDContextBuilder`**, **`LDClient.start(…, startWaitSeconds:completion:)`** — see [Initialize the client](https://launchdarkly.com/docs/sdk/client-side/ios#initialize-the-client). Observability: see [Observability plugin](observability-plugin.md).

### Android

| Field | Value |
|-------|-------|
| Package | `com.launchdarkly:launchdarkly-android-client-sdk` |
| Detect files | `build.gradle`, `build.gradle.kts`, `AndroidManifest.xml` |
| Detect patterns | `android`, `com.android`, `androidx` |
| Install | See **Install (two Gradle DSLs)** below — same artifact, different syntax for Groovy vs Kotlin DSL |
| Docs | [Android SDK reference](https://launchdarkly.com/docs/sdk/client-side/android) |

**Install (two Gradle DSLs):** The [Install the SDK](https://launchdarkly.com/docs/sdk/client-side/android#install-the-sdk) topic shows **both** forms. Use the one that matches the app module file you have:

- **Gradle Groovy** (`build.gradle`): `implementation 'com.launchdarkly:launchdarkly-android-client-sdk:5.+'`
- **Gradle Kotlin DSL** (`build.gradle.kts`): `implementation("com.launchdarkly:launchdarkly-android-client-sdk:5.+")`

**SDK detail:** [`snippets/android-client-sdk.md`](snippets/android-client-sdk.md) (includes onboarding sample)

---

## Server-side SDKs (other)

Server-side SDKs use an **SDK Key** and are intended for backends where the key stays secret.

The five most-used server runtimes (Node.js, Python, .NET, Java, Go) are in **[Top 10 SDKs (start here)](#top-10-sdks-start-here)** above.

### Apex (Salesforce)

| Field | Value |
|-------|-------|
| Package | Deploy from [apex-server-sdk](https://github.com/launchdarkly/apex-server-sdk) (no NuGet/Maven module) |
| Detect files | `sfdx-project.json`, `force-app`, `*.cls` |
| Detect patterns | `salesforce`, `Salesforce`, `Apex` |
| Install | Follow the docs (SFDX deploy and LaunchDarkly Salesforce bridge) |
| Docs | [Apex SDK reference](https://launchdarkly.com/docs/sdk/server-side/apex) |

**SDK detail:** [`snippets/apex-server-sdk.md`](snippets/apex-server-sdk.md)

### C++ (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-cpp-server` (via CMake `FetchContent`, vcpkg, or vendor) |
| Detect files | `CMakeLists.txt`, `Makefile`, `*.cpp`, `*.h` |
| Detect patterns | `cmake`, server-side C++ services |
| Install | See docs (CMake / vcpkg) |
| Docs | [C++ SDK reference (server-side)](https://launchdarkly.com/docs/sdk/server-side/c-c--) |

**SDK detail:** [`snippets/cpp-server-sdk.md`](snippets/cpp-server-sdk.md)

### Erlang / Elixir

| Field | Value |
|-------|-------|
| Package | Erlang: [launchdarkly_server_sdk](https://hex.pm/packages/launchdarkly_server_sdk) (Hex). Elixir: add the same dependency in `mix.exs` |
| Detect files | `rebar.config`, `mix.exs` |
| Detect patterns | `erlang`, `elixir`, `phoenix` |
| Install | Rebar or Mix per docs |
| Docs | [Erlang SDK reference](https://launchdarkly.com/docs/sdk/server-side/erlang) |

**SDK detail:** [`snippets/erlang-server-sdk.md`](snippets/erlang-server-sdk.md)

### Haskell (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-server-sdk` (Cabal / Stack / Hackage) |
| Detect files | `*.cabal`, `stack.yaml`, `package.yaml` |
| Detect patterns | `haskell`, `cabal`, `stack` |
| Install | Add dependency per docs |
| Docs | [Haskell SDK reference](https://launchdarkly.com/docs/sdk/server-side/haskell) |

**SDK detail:** [`snippets/haskell-server-sdk.md`](snippets/haskell-server-sdk.md)

### Lua (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-server-sdk` (LuaRocks) |
| Detect files | `*.lua`, `*.rockspec` |
| Detect patterns | `lua`, `luarocks`, OpenResty / NGINX / HAProxy Lua |
| Install | `luarocks install launchdarkly-server-sdk` (see docs for your runtime) |
| Docs | [Lua SDK reference](https://launchdarkly.com/docs/sdk/server-side/lua) |

**SDK detail:** [`snippets/lua-server-sdk.md`](snippets/lua-server-sdk.md)

### PHP (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly/server-sdk` |
| Detect files | `composer.json` |
| Detect patterns | `laravel`, `symfony`, `slim` |
| Install | `composer require launchdarkly/server-sdk` |
| Docs | [PHP SDK reference](https://launchdarkly.com/docs/sdk/server-side/php) |

**SDK detail:** [`snippets/php-server-sdk.md`](snippets/php-server-sdk.md)

### Ruby (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-server-sdk` |
| Detect files | `Gemfile`, `*.gemspec` |
| Detect patterns | `rails`, `sinatra`, `hanami` |
| Install | `gem install launchdarkly-server-sdk` or add to Gemfile |
| Docs | [Ruby SDK reference](https://launchdarkly.com/docs/sdk/server-side/ruby) |

**SDK detail:** [`snippets/ruby-server-sdk.md`](snippets/ruby-server-sdk.md)

### Rust (Server)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-server-sdk` |
| Detect files | `Cargo.toml` |
| Detect patterns | `actix`, `rocket`, `axum`, `warp` |
| Install | `cargo add launchdarkly-server-sdk` |
| Docs | [Rust SDK reference](https://launchdarkly.com/docs/sdk/server-side/rust) |

**SDK detail:** [`snippets/rust-server-sdk.md`](snippets/rust-server-sdk.md)

---

## Client-side SDKs (other)

Client-side SDKs use a **Client-side ID** for browser and desktop clients where that credential is expected to be visible in the app. Use the linked reference for bootstrap, privacy, and flag delivery behavior.

**React (Web)** and **JavaScript (browser)** are in **[Top 10 SDKs (start here)](#top-10-sdks-start-here)** above.

### Vue

| Field | Value |
|-------|-------|
| Package | `launchdarkly-vue-client-sdk` |
| Detect files | `package.json` |
| Detect patterns | `vue`, `"vue":` |
| Install | `npm install launchdarkly-vue-client-sdk` |
| Docs | [Vue SDK reference](https://launchdarkly.com/docs/sdk/client-side/vue) |

**SDK detail:** [`snippets/vue-client-sdk.md`](snippets/vue-client-sdk.md)

### Angular, Svelte, Preact, and other browser frameworks

| Field | Value |
|-------|-------|
| Package | `@launchdarkly/js-client-sdk` |
| Detect files | `package.json`, `angular.json`, `svelte.config.js` |
| Detect patterns | `@angular`, `svelte`, `preact` |
| Install | `npm install @launchdarkly/js-client-sdk` |
| Docs | [JavaScript SDK reference](https://launchdarkly.com/docs/sdk/client-side/javascript) (no dedicated SDK; use the JS client) |

**SDK detail:** [`snippets/browser-frameworks-sdk.md`](snippets/browser-frameworks-sdk.md)

**API:** Same package and **`createClient`** / **`start()`** / **`waitForInitialization`** flow as [JavaScript (Browser)](#javascript-browser). Prefer [`javascript-browser-sdk.md`](snippets/javascript-browser-sdk.md) for a copy-paste sample.

### .NET (Client)

| Field | Value |
|-------|-------|
| Package | `LaunchDarkly.ClientSdk` |
| Detect files | `*.csproj`, `*.sln` (WASM: `blazorwasm`, `BlazorWebAssembly`, `UseBlazorWebAssembly` in project) |
| Detect patterns | `Xamarin`, `MAUI`, `WPF`, `UWP`, `Avalonia`, `Blazor`, `blazor`, `blazorwasm` |
| Install | `dotnet add package LaunchDarkly.ClientSdk` |
| Docs | [.NET SDK reference (client-side)](https://launchdarkly.com/docs/sdk/client-side/dotnet) |

**SDK detail:** [`snippets/dotnet-client-sdk.md`](snippets/dotnet-client-sdk.md)

**Keys:** **MAUI, Xamarin, WPF, UWP** (and similar native/desktop shells) use this package as LaunchDarkly’s **.NET mobile client SDK** with a **mobile key**. **Blazor WebAssembly** (browser-hosted UI) uses the same package with a **Client-side ID**. **Blazor Server** (and server-rendered interactive Blazor) → **[.NET (Server)](#net-server)** with `LaunchDarkly.ServerSdk`. See [Generate integration plan](../../sdk-install/plan/SKILL.md).

### C++ (Client)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-cpp-client` (CMake / vcpkg per docs) |
| Detect files | `CMakeLists.txt`, `Makefile`, `*.cpp`, `*.h` |
| Detect patterns | Desktop or embedded C++ clients |
| Install | See docs |
| Docs | [C++ SDK reference (client-side)](https://launchdarkly.com/docs/sdk/client-side/c-c--) |

**SDK detail:** [`snippets/cpp-client-sdk.md`](snippets/cpp-client-sdk.md)

### Electron

| Field | Value |
|-------|-------|
| Package | `launchdarkly-electron-client-sdk` |
| Detect files | `package.json` |
| Detect patterns | `electron` |
| Install | `npm install launchdarkly-electron-client-sdk` |
| Docs | [Electron SDK reference](https://launchdarkly.com/docs/sdk/client-side/electron) |

**SDK detail:** [`snippets/electron-client-sdk.md`](snippets/electron-client-sdk.md)

### Node.js (Client)

| Field | Value |
|-------|-------|
| Package | `launchdarkly-node-client-sdk` |
| Detect files | `package.json` |
| Detect patterns | Node scripts or desktop tooling **without** Electron (see Electron above) |
| Install | `npm install launchdarkly-node-client-sdk` |
| Docs | [Node.js SDK reference (client-side)](https://launchdarkly.com/docs/sdk/client-side/node-js) |

**SDK detail:** [`snippets/node-client-sdk.md`](snippets/node-client-sdk.md)

### Roku (BrightScript)

| Field | Value |
|-------|-------|
| Package | [roku-client-sdk](https://github.com/launchdarkly/roku-client-sdk) (GitHub releases) |
| Detect files | `manifest`, `*.brs`, SceneGraph `*.xml` |
| Detect patterns | `brightscript`, `roku`, `SceneGraph` |
| Install | Add SDK components per docs |
| Docs | [Roku SDK reference](https://launchdarkly.com/docs/sdk/client-side/roku) |

**SDK detail:** [`snippets/roku-client-sdk.md`](snippets/roku-client-sdk.md)

---

## Mobile SDKs (other)

These entries are **mobile or app-embedded** targets. Most use a **Mobile key**; **Flutter web** is an exception (see below). Each **Docs** link points at the official reference (same pages as the client-side SDK family on launchdarkly.com/docs).

**Swift / iOS**, **Android**, and **React Native** are in **[Top 10 SDKs (start here)](#top-10-sdks-start-here)** above.

### Flutter

LaunchDarkly documents this as the **Flutter client SDK** (`launchdarkly_flutter_client_sdk`); it is listed here because **iOS, Android, and typical desktop app** builds use a **Mobile key**.

| Field | Value |
|-------|-------|
| Package | `launchdarkly_flutter_client_sdk` |
| Detect files | `pubspec.yaml` |
| Detect patterns | `flutter` |
| Install | `flutter pub add launchdarkly_flutter_client_sdk` |
| Docs | [Flutter SDK reference](https://launchdarkly.com/docs/sdk/client-side/flutter) |

**SDK detail:** [`snippets/flutter-client-sdk.md`](snippets/flutter-client-sdk.md)

**Keys:** **Mobile key** for iOS, Android, and typical **desktop app** targets; **Client-side ID** (and your bundler’s public env pattern) for **Flutter web**. Multi-target apps may need separate config per surface—see [Generate integration plan](../../sdk-install/plan/SKILL.md).

---

## Edge SDKs

Edge SDKs run on edge platforms and use an **SDK Key** (see each platform's reference for environment and constraints).

| Platform | Detect pattern | Docs |
|----------|----------------|------|
| Akamai EdgeWorkers | `bundle.json`, `edgeworkers` | [Akamai SDK reference](https://launchdarkly.com/docs/sdk/edge/akamai) |
| Cloudflare Workers | `wrangler.toml`, `@cloudflare/workers-types` | [Cloudflare SDK reference](https://launchdarkly.com/docs/sdk/edge/cloudflare) |
| Fastly Compute | Fastly service config, `@fastly/js-compute` (per your stack) | [Fastly SDK reference](https://launchdarkly.com/docs/sdk/edge/fastly) |
| Vercel Edge | `vercel.json` with edge functions, `@vercel/edge` | [Vercel SDK reference](https://launchdarkly.com/docs/sdk/edge/vercel) |

**SDK detail:** [`snippets/edge-sdks.md`](snippets/edge-sdks.md) (all edge platforms)

---