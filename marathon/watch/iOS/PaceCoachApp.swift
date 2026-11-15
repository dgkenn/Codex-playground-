// The iPhone side. Apple delivers a watch app inside an iPhone app, so this exists first of all to
// carry it; later it will receive finished runs from the watch and hand them on.
import SwiftUI

@main
struct PaceCoachApp: App {
    var body: some Scene {
        WindowGroup {
            VStack(spacing: 12) {
                Text("Pace Coach").font(.largeTitle.bold())
                Text("The run coach is on your Apple Watch. Open Pace Coach there to set the session and start a run.")
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
    }
}
