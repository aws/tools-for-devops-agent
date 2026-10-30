---
title: Java Server SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly Java server-side SDK
---

# Java (Server) — SDK detail

- Official docs: [Java SDK reference](https://launchdarkly.com/docs/sdk/server-side/java)
- API reference: [Java server SDK API](https://launchdarkly.github.io/java-core/lib/sdk/server/)
- Published artifact: [Maven Central](https://mvnrepository.com/artifact/com.launchdarkly/launchdarkly-java-server-sdk)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Java Server)

Pin **`version`** to a current release from the [SDK releases page](https://github.com/launchdarkly/java-core/releases). The blocks below mirror [Install the SDK](https://launchdarkly.com/docs/sdk/server-side/java#install-the-sdk) (Maven **XML** and **Gradle**); use the one that matches your build.

**Maven** (`pom.xml`):

```xml
<dependency>
  <groupId>com.launchdarkly</groupId>
  <artifactId>launchdarkly-java-server-sdk</artifactId>
  <version>7.0.0</version>
</dependency>
```

**Gradle (Groovy)** — long form as in the docs:

```groovy
implementation group: 'com.launchdarkly', name: 'launchdarkly-java-server-sdk', version: '7.0.0'
```

**Gradle (Groovy)** — common shortcut (still set a concrete or ranged version you intend to support):

```groovy
implementation 'com.launchdarkly:launchdarkly-java-server-sdk:7.+'
```

**Gradle (Kotlin DSL)** (`build.gradle.kts`):

```kotlin
implementation("com.launchdarkly:launchdarkly-java-server-sdk:7.+")
```

**OSGi “all” classifier** (bundled Gson/SLF4J): see [Using the Java SDK in OSGi](https://launchdarkly.com/docs/sdk/server-side/java#using-the-java-sdk-in-osgi).

**Import** ([same topic](https://launchdarkly.com/docs/sdk/server-side/java#install-the-sdk)):

```java
import com.launchdarkly.sdk.*;
import com.launchdarkly.sdk.server.*;
```

**Initialize:** [`new LDClient(sdkKey)`](https://launchdarkly.com/docs/sdk/server-side/java#initialize-the-client) connects with a **default ~5s** wait; use [`isInitialized()`](https://launchdarkly.github.io/java-core/lib/sdk/server/com/launchdarkly/sdk/server/LDClient.html#isInitialized--) to see if startup succeeded. For custom timeouts and options, use [`LDConfig.Builder`](https://launchdarkly.github.io/java-core/lib/sdk/server/com/launchdarkly/sdk/server/LDConfig.Builder.html). **`LDClient` must be a singleton** per environment.

**Includes:** Minimal `main` sample. SDK key: **`LAUNCHDARKLY_SDK_KEY`** ([Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration)).

```java
import com.launchdarkly.sdk.*;
import com.launchdarkly.sdk.server.*;

public class Main {
  public static void main(String[] args) {
    String sdkKey = System.getenv("LAUNCHDARKLY_SDK_KEY");
    if (sdkKey == null || sdkKey.trim().isEmpty()) {
      System.err.println(
          "LAUNCHDARKLY_SDK_KEY is not set. Use Project settings > Environments > SDK key.");
      System.exit(1);
    }

    try (LDClient client = new LDClient(sdkKey)) {
      if (client.isInitialized()) {
        // For onboarding only — events are normally flushed in the background.
        client.flush();
        System.out.println("LaunchDarkly client initialized.");
      } else {
        System.err.println(
            "LaunchDarkly client did not initialize within the default wait; defaults apply until connected.");
        System.exit(1);
      }
    }
  }
}
```
