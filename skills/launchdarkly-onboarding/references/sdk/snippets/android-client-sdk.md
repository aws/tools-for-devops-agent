---
title: Android Client SDK — SDK detail
description: Kotlin onboarding sample and links for the LaunchDarkly Android SDK
---

# Android — SDK detail

- Official docs: [Android SDK reference](https://launchdarkly.com/docs/sdk/client-side/android) · [Set up Android SDK](https://launchdarkly.com/docs/home/onboarding/android) (onboarding)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Android)

**Install the dependency:** [Install the SDK](https://launchdarkly.com/docs/sdk/client-side/android#install-the-sdk) documents **two** Gradle styles—the same Maven coordinate, different syntax. Pick the one that matches your app module:

```groovy
// Gradle Groovy — typically app/build.gradle
implementation 'com.launchdarkly:launchdarkly-android-client-sdk:5.+'
```

```kotlin
// Gradle Kotlin DSL — typically app/build.gradle.kts
implementation("com.launchdarkly:launchdarkly-android-client-sdk:5.+")
```

**Import the SDK:** Use the imports that match your language ([Import the SDK](https://launchdarkly.com/docs/sdk/client-side/android#import-the-sdk)). Observability is **optional** (separate `launchdarkly-observability-android` dependency; requires Android client SDK **v5.9+**).

Kotlin:

```kotlin
import com.launchdarkly.sdk.*
import com.launchdarkly.sdk.android.*

// Optional observability plugin, requires LaunchDarkly Android Client SDK v5.9+
// import com.launchdarkly.observability.plugin.Observability
// import com.launchdarkly.sdk.android.integrations.Plugin
```

Java:

```java
import com.launchdarkly.sdk.*;
import com.launchdarkly.sdk.android.*;

// Optional observability plugin, requires LaunchDarkly Android Client SDK v5.9+
// import com.launchdarkly.observability.plugin.Observability;
// import com.launchdarkly.sdk.android.integrations.Plugin;
```

The init snippet below matches the [onboarding initialization example](https://launchdarkly.com/docs/home/onboarding/android): use a placeholder mobile key first, then wire a real value from build configuration (see optional Gradle section). `BuildConfig.LAUNCHDARKLY_MOBILE_KEY` is **not** defined unless you add `buildConfigField` yourself—do not paste it without the Gradle setup.

**Includes:** Copy-paste onboarding sample below (Kotlin). Place inside your `Application` subclass (for example `onCreate()`); `this` refers to that `Application` instance.

```kotlin
import com.launchdarkly.sdk.*
import com.launchdarkly.sdk.android.*

// Optional observability plugin, requires LaunchDarkly Android Client SDK v5.9+
// import com.launchdarkly.observability.plugin.Observability
// import com.launchdarkly.sdk.android.integrations.Plugin

val ldConfig = LDConfig.Builder(AutoEnvAttributes.Enabled)
    .mobileKey("YOUR_MOBILE_KEY")
    .build()

// A "context" is a data object representing users, devices, organizations, and other entities.
val context = LDContext.create("EXAMPLE_CONTEXT_KEY")

// If you don't want to block execution while the SDK tries to get
// latest flags, move this code into an async IO task and await on its completion.
val client: LDClient = LDClient.init(this, ldConfig, context, 5)
```

Replace `"YOUR_MOBILE_KEY"` with your **Mobile key** from LaunchDarkly **Project settings > Environments** (see [Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration)). Never commit real keys in source.

**Optional — `BuildConfig` + Gradle (Kotlin DSL):** Enable BuildConfig and pass the key from a non-committed `gradle.properties` or `local.properties` value:

```kotlin
// app/build.gradle.kts — excerpt
android {
    buildFeatures {
        buildConfig = true
    }
    defaultConfig {
        val key = (project.findProperty("LAUNCHDARKLY_MOBILE_KEY") as String?)?.trim().orEmpty()
        buildConfigField("String", "LAUNCHDARKLY_MOBILE_KEY", "\"$key\"")
    }
}
```

Then change `.mobileKey("YOUR_MOBILE_KEY")` to `.mobileKey(BuildConfig.LAUNCHDARKLY_MOBILE_KEY)` and set `LAUNCHDARKLY_MOBILE_KEY=…` where Gradle can read it (for example `~/.gradle/gradle.properties` or a CI secret), not in a committed file.
