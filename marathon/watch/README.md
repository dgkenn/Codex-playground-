# Pace Coach for Apple Watch

The run coach on the wrist: a HealthKit workout (keeps running with the screen off), heart rate from
the watch, run/walk blocks decided by heart rate with a tap on the wrist at every change, and a
screen readable at a glance. The phone web app stays the planner and analyst.

```
CoachCore/   the coaching logic in Swift (ported from ../tools/hr-blocks.js), tested with `swift test`
Watch/       the watch app (SwiftUI, HealthKit)
iOS/         the iPhone app that carries it (Apple delivers watch apps inside an iPhone app)
project.yml  XcodeGen spec; the .xcodeproj is generated in CI, never committed
```

There is no Mac in this project. `.github/workflows/watch-app.yml` builds on a GitHub Mac: tests and
simulator builds on every push, and an upload to TestFlight once the secrets below exist.

## One-time setup (about 15 minutes, after Apple approves the developer account)

1. **App Store Connect API key.** appstoreconnect.apple.com → Users and Access → Integrations →
   App Store Connect API → Team Keys → generate a key with **Admin** access (signing in the cloud
   needs it). Note the **Key ID** and the **Issuer ID** shown above the list, and download the
   `.p8` file (it can be downloaded once).
2. **Team ID.** developer.apple.com → Account → Membership details: the 10-character Team ID.
3. **GitHub.** Repository → Settings → Secrets and variables → Actions:
   - Secrets: `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_KEY_P8` (open the .p8 in a text editor and
     paste all of it, including the BEGIN/END lines).
   - Variables: `APPLE_TEAM_ID`. Optionally `BUNDLE_PREFIX` (default `com.dgkenn`).
4. **Run the workflow** (Actions → watch-app → Run workflow). The first run registers the app's IDs
   with Apple and then fails at the upload, because App Store Connect has no app record yet.
5. **Create the app record.** App Store Connect → Apps → + → New App: platform iOS, name
   "Pace Coach" (or any free name), bundle ID `com.dgkenn.pacecoach`, any SKU.
6. **Run the workflow again.** The build appears in TestFlight after Apple processes it (10-30
   minutes). Install TestFlight on the iPhone, open the build, install; the watch app installs from
   the Watch app on the iPhone (or automatically).

Builds after that upload on every push to `marathon/watch`.
