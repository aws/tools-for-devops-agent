---
title: iOS (Swift) Client SDK — SDK detail
description: Onboarding sample and links for the LaunchDarkly iOS SDK
---

# Swift / iOS — SDK detail

- Official docs: [iOS SDK reference](https://launchdarkly.com/docs/sdk/client-side/ios) · [Set up iOS SDK](https://launchdarkly.com/docs/home/onboarding/ios) (onboarding)
- API reference: [iOS SDK API docs](https://launchdarkly.github.io/ios-client-sdk/)
- Recipe (detect / install): [SDK Recipes](../recipes.md) (Swift / iOS)

**Why this differs from the home onboarding page:** [Set up iOS SDK](https://launchdarkly.com/docs/home/onboarding/ios) uses a **`"YOUR_MOBILE_KEY"`** literal and a linear script. This skill keeps the **same `LDConfig` / `LDContextBuilder` / `LDClient.start`…`startWaitSeconds`** flow as [Initialize the client](https://launchdarkly.com/docs/sdk/client-side/ios#initialize-the-client), but resolves the mobile key from **Xcode scheme env** or **Info.plist** so archives are not missing the key. Substituting `LDConfig(mobileKey: "YOUR_MOBILE_KEY", …)` matches the docs verbatim when you only need a quick local paste.

**Install the SDK:** LaunchDarkly documents **Swift Package Manager**, **CocoaPods**, and **Carthage** ([Install the SDK](https://launchdarkly.com/docs/sdk/client-side/ios#install-the-sdk)). Pin versions from the [SDK releases](https://github.com/launchdarkly/ios-client-sdk/releases) page; the examples below follow the [onboarding install](https://launchdarkly.com/docs/home/onboarding/ios) style.

**Swift Package Manager** (`Package.swift` excerpt):

```swift
// ...
dependencies: [
    .package(url: "https://github.com/launchdarkly/ios-client-sdk.git", .upToNextMajor("9.15.0")),
    // Optional observability — iOS SDK v9.14+; see reference Install the SDK
    // .package(url: "https://github.com/launchdarkly/swift-launchdarkly-observability.git", .upToNextMajor("1.0.0")),
],
targets: [
    .target(
        name: "YOUR_TARGET",
        dependencies: ["LaunchDarkly"]
    ),
]
// ...
```

**CocoaPods** (`Podfile`):

```ruby
use_frameworks!
target 'YourTargetName' do
  pod 'LaunchDarkly', '~> 9.15'
  # Optional — LaunchDarklyObservability, iOS SDK v9.14+
  # pod 'LaunchDarklyObservability', '~> 1.0'
end
```

**Carthage** (`Cartfile`):

```
github "launchdarkly/ios-client-sdk" ~> 9.15
```

**Import** ([Import the SDK](https://launchdarkly.com/docs/sdk/client-side/ios#import-the-sdk)):

```swift
import LaunchDarkly
// Optional observability — iOS SDK v9.14+
// import LaunchDarklyObservability
```

**Mobile key:** Never ship a real key in source. `ProcessInfo.processInfo.environment` is set from the **Xcode scheme** for local runs; **TestFlight / App Store** builds need **Info.plist** (e.g. `LaunchDarklyMobileKey`) or xcconfig. Logical name: [Apply: environment configuration](../../../sdk-install/apply/SKILL.md#step-2-add-the-sdk-key-to-environment-configuration).

**Includes:** Call `configureLaunchDarkly()` from `application(_:didFinishLaunchingWithOptions:)` (UIKit) or your SwiftUI startup path.

```swift
import LaunchDarkly

func configureLaunchDarkly() {
    let mobileKey: String?
    if let v = ProcessInfo.processInfo.environment["LAUNCHDARKLY_MOBILE_KEY"], !v.isEmpty {
        mobileKey = v
    } else if let v = Bundle.main.object(forInfoDictionaryKey: "LaunchDarklyMobileKey") as? String, !v.isEmpty {
        mobileKey = v
    } else {
        mobileKey = nil
    }

    guard let mobileKey else {
        print("LaunchDarkly: missing mobile key (scheme LAUNCHDARKLY_MOBILE_KEY for Xcode runs, or Info.plist LaunchDarklyMobileKey for archives).")
        return
    }

    let config = LDConfig(mobileKey: mobileKey, autoEnvAttributes: .enabled)
    // Optional observability — iOS SDK v9.14+; add package/pod and set config.plugins per
    // https://launchdarkly.com/docs/sdk/client-side/ios#initialize-the-client

    let contextBuilder = LDContextBuilder(key: "EXAMPLE_CONTEXT_KEY")
    guard case .success(let context) = contextBuilder.build() else {
        print("LaunchDarkly: could not build context")
        return
    }

    LDClient.start(config: config, context: context, startWaitSeconds: 5) { timedOut in
        if timedOut {
            print("SDK didn't initialize in 5 seconds. SDK is still running and trying to get latest flags.")
        } else {
            print("SDK successfully initialized with the latest flags")
            if let client = LDClient.get() {
                // For onboarding only — events are flushed automatically in normal use.
                client.flush()
            }
        }
    }

    print("SDK started.")
}
```
