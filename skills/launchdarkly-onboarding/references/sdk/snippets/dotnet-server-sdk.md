---
title: .NET Server SDK — SDK detail
description: ASP.NET Core onboarding sample and links for the LaunchDarkly server-side .NET SDK
---

# .NET (Server) — SDK detail

- Official docs: [.NET SDK reference (server-side)](https://launchdarkly.com/docs/sdk/server-side/dotnet)
- API reference: [Server SDK API](https://launchdarkly.github.io/dotnet-core/pkgs/sdk/server/)
- Published package: [LaunchDarkly.ServerSdk (NuGet)](https://www.nuget.org/packages/LaunchDarkly.ServerSdk/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (.NET Server)

Target the **current major** server SDK on NuGet (`LaunchDarkly.ServerSdk`); follow the docs for version compatibility ([.NET SDK reference](https://launchdarkly.com/docs/sdk/server-side/dotnet)).

**Install:** From the project directory ([Install the SDK](https://launchdarkly.com/docs/sdk/server-side/dotnet#install-the-sdk)):

```bash
dotnet add package LaunchDarkly.ServerSdk
```

Optional observability ([.NET observability](https://launchdarkly.com/docs/sdk/observability/dotnet)) — requires server SDK **8.10+**:

```bash
dotnet add package LaunchDarkly.Observability
```

**Import:** Namespace differs from the package name ([same page — import](https://launchdarkly.com/docs/sdk/server-side/dotnet#install-the-sdk)):

```csharp
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

// Optional — LaunchDarkly.Observability package; requires server SDK 8.10+
// using LaunchDarkly.Observability;
```

**Initialize:** Use **`Configuration.Builder(sdkKey)`** with **`StartWaitTime`** (docs recommend a short wait so a bad network does not hang forever). Construct **`LdClient`** **before** **`builder.Build()`** ([Initialize the client](https://launchdarkly.com/docs/sdk/server-side/dotnet#initialize-the-client)). In production, register **`LdClient`** as a **singleton** in DI instead of creating one per request.

**Includes:** Minimal **ASP.NET Core** `Program.cs`–style sample. SDK key: **`LAUNCHDARKLY_SDK_KEY`** ([Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration)).

```csharp
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

var builder = WebApplication.CreateBuilder(args);

var sdkKey = Environment.GetEnvironmentVariable("LAUNCHDARKLY_SDK_KEY");
if (string.IsNullOrWhiteSpace(sdkKey))
{
    Console.Error.WriteLine(
        "LAUNCHDARKLY_SDK_KEY is not set. Use Project settings > Environments > SDK key.");
    Environment.Exit(1);
}

var ldConfig = Configuration.Builder(sdkKey)
    .StartWaitTime(TimeSpan.FromSeconds(5))
    .Build();

// Construct the client before Build() per LaunchDarkly docs.
using var ldClient = new LdClient(ldConfig);

var app = builder.Build();

if (!ldClient.Initialized)
{
    Console.Error.WriteLine("LaunchDarkly client did not initialize within StartWaitTime.");
    Environment.Exit(1);
}

// For onboarding only — events are normally flushed in the background.
ldClient.Flush();
Console.WriteLine("LaunchDarkly client ready.");

// app.MapGet(...);
app.Run();
```

**Optional — observability (SDK 8.10+):** After adding **`LaunchDarkly.Observability`**, follow the **`ObservabilityPlugin.Builder(builder.Services)`** example in [Initialize the client](https://launchdarkly.com/docs/sdk/server-side/dotnet#initialize-the-client) inside **`Configuration.Builder`’s** **`Plugins`** chain.
