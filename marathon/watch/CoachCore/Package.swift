// swift-tools-version:5.9
// The coaching logic shared by the watch app (and later the iPhone app), with no Apple-only imports,
// so `swift test` runs it on a plain Mac in CI. Ported from marathon/tools/*.js; the JS stays the
// reference until the web app is retired.
import PackageDescription

let package = Package(
    name: "CoachCore",
    platforms: [.iOS(.v17), .watchOS(.v10), .macOS(.v13)],
    products: [.library(name: "CoachCore", targets: ["CoachCore"])],
    targets: [
        .target(name: "CoachCore"),
        .testTarget(name: "CoachCoreTests", dependencies: ["CoachCore"]),
    ]
)
