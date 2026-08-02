// swift-tools-version: 5.9
//
// Package manifest for the parts of the app that are pure logic and can therefore be tested without
// a simulator: the PMD codec, the physiology and signal-quality ports, and the in-run controller.
//
// The app target itself (SwiftUI views, CoreBluetooth, HealthKit, CoreLocation) needs an Xcode project
// and a device or simulator. Keeping the logic in a plain SwiftPM library means `swift test` verifies
// the parts where correctness is subtle, on any machine, without opening Xcode.
//
import PackageDescription

let package = Package(
    name: "MarathonCoach",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "MarathonCoachCore", targets: ["MarathonCoachCore"]),
    ],
    targets: [
        .target(
            name: "MarathonCoachCore",
            path: "Sources",
            // Excluded because they need UIKit/SwiftUI, CoreBluetooth, HealthKit or CoreLocation and
            // cannot build on a non-Apple host. Everything left is portable, deterministic logic.
            exclude: ["Views", "MarathonCoachApp.swift",
                      "Sensors/VeritySensor.swift", "Sensors/AudioCoach.swift",
                      "Sensors/EarconPlayer.swift",
                      "Sensors/LocationPace.swift", "Store/HealthKitBridge.swift",
                      "Engine/RunSession.swift",
                      // Combine-dependent, so Apple-only. The scenario engine itself
                      // (Simulation/RunScenario.swift) deliberately is not, so a whole run can be
                      // replayed under `swift test` on any machine.
                      "Sensors/SensorProtocols.swift", "Simulation/SimulatedSources.swift"]
        ),
        .testTarget(
            name: "MarathonCoachCoreTests",
            dependencies: ["MarathonCoachCore"],
            path: "Tests",
            resources: [
                .copy("Fixtures/golden_vectors.json"),
                // Bundled so the PlanStore tests actually run rather than skipping. A test that skips
                // protects nothing.
                .copy("Fixtures/plan.json"),
            ]
        ),
    ]
)
