//
//  RunView.swift
//  The in-run screen. One number, large, and a colour that tells you if you are in the right place.
//
//  Design constraints that come from actually running with a phone, not from a design system:
//
//  • **Glanceable at arm's length, while moving, in sunlight, possibly in the rain.** That means one
//    dominant metric and a background colour carrying the in/out-of-zone state, so the answer to
//    "am I doing this right" arrives before you have focused on any text. Garmin Connect's redesign
//    is widely criticised for being a cluttered grid of widgets; this is the opposite.
//
//  • **Colour is never the only signal.** The zone state is also stated in words and in the icon,
//    because roughly 8% of men have some form of colour vision deficiency and red/green is the worst
//    possible pair to rely on. It also degrades gracefully in bright sun where saturation washes out.
//
//  • **The audio cue is the primary interface; the screen is the fallback.** You will mostly be
//    listening, not looking. So the cue text is shown persistently after it is spoken, rather than
//    flashing and vanishing — if you half-hear something at 18 km you can check what it said.
//
//  • **Sensor state is always visible.** Not hidden behind a menu. If heart rate is dropped out or
//    locked to cadence, that changes how you should interpret everything else on the screen, so it
//    is shown at the top rather than silently degrading.
//
//  • **The pain button is one tap away, always.** It is the highest-value input the app collects and
//    the one that has to work when you are tired and annoyed.
//

import SwiftUI

// MARK: - Note on where the state comes from
//
// This view observes `RunSession` directly. An earlier version had its own `RunSessionViewModel` with
// its own `InRunController`, which meant two controllers existed: the one in `RunSession` that actually
// received sensor ticks, and the view's, which never did. The screen showed a permanently-unknown zone
// state while the real controller ran invisibly behind it. One controller, one source of display state.

// MARK: - The screen

public struct RunView: View {
    @ObservedObject var session: RunSession
    @ObservedObject var sensor: VeritySensor
    let sessionTitle: String
    @State private var showPainSheet = false

    public init(session: RunSession, sensor: VeritySensor, sessionTitle: String) {
        self.session = session; self.sensor = sensor; self.sessionTitle = sessionTitle
    }

    public var body: some View {
        ZStack {
            tint(for: session.zoneState).ignoresSafeArea()
            VStack(spacing: 0) {
                sensorBar
                Spacer(minLength: 8)
                dominantMetric
                Spacer(minLength: 8)
                secondaryMetrics
                cuePanel
                painButton
            }
            .padding(.horizontal, 20)
        }
        .foregroundStyle(.white)
        // Keep the screen awake: a run screen that sleeps mid-interval is useless, and the phone is
        // likely in a belt where a wake gesture is awkward.
        .onAppear { UIApplication.shared.isIdleTimerDisabled = true }
        .onDisappear { UIApplication.shared.isIdleTimerDisabled = false }
        .sheet(isPresented: $showPainSheet) { PainSheet(session: session, isPresented: $showPainSheet) }
    }

    /// Colour lives here rather than on `RunSession.ZoneState`, because `Color` is a SwiftUI type and
    /// the session must stay free of UI imports so it can be exercised without a view.
    ///
    /// These are deliberately desaturated rather than pure red/green: on a phone in direct sunlight,
    /// saturated colour washes out to near-indistinguishable, and the state is also carried by the icon
    /// and the words for the same reason.
    private func tint(for state: RunSession.ZoneState) -> Color {
        switch state {
        case .inZone: return Color(red: 0.13, green: 0.45, blue: 0.28)
        case .tooHard: return Color(red: 0.62, green: 0.20, blue: 0.16)
        case .tooEasy: return Color(red: 0.18, green: 0.33, blue: 0.55)
        case .unknown: return Color(white: 0.28)
        }
    }

    // MARK: Sensor state — always visible, never hidden in a menu

    private var sensorBar: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(sensor.status.isUsable ? Color.green : Color.orange)
                .frame(width: 9, height: 9)
            Text(sensorLabel)
                .font(.system(size: 13, weight: .medium, design: .rounded))
                .lineLimit(2)
                .minimumScaleFactor(0.8)
            Spacer()
            if let b = sensor.batteryPercent {
                Text("\(b)%").font(.system(size: 13, design: .rounded).monospacedDigit())
            }
        }
        .opacity(0.9)
        .padding(.top, 6)
    }

    private var sensorLabel: String {
        switch session.hrStatus {
        case "cadence_lock":
            return "Heart rate locked to step rate — guiding by pace"
        case "dropout":
            return "No heart rate — guiding by pace and feel"
        case "warmup":
            return "Sensor warming up"
        default:
            return sensor.status.isUsable ? sessionTitle : sensor.status.userMessage
        }
    }

    // MARK: The one number that matters

    private var dominantMetric: some View {
        VStack(spacing: 2) {
            if let hr = session.hr, session.hrStatus == "ok" {
                Text("\(Int(hr))")
                    .font(.system(size: 132, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text("bpm").font(.system(size: 20, weight: .medium, design: .rounded)).opacity(0.85)
                if let b = session.targetBand {
                    Text("target \(Int(b.low))–\(Int(b.high))")
                        .font(.system(size: 17, design: .rounded)).opacity(0.8)
                }
            } else {
                // No trustworthy HR: promote pace to the dominant slot rather than showing a
                // placeholder where a number should be.
                Text(session.paceSecKm.map { Physiology.formatPace($0) } ?? "--:--")
                    .font(.system(size: 108, weight: .bold, design: .rounded))
                    .monospacedDigit().minimumScaleFactor(0.5).lineLimit(1)
                Text("min/km").font(.system(size: 20, weight: .medium, design: .rounded)).opacity(0.85)
            }

            HStack(spacing: 8) {
                Image(systemName: session.zoneState.symbol)
                Text(session.zoneState.label)
            }
            .font(.system(size: 22, weight: .semibold, design: .rounded))
            .padding(.top, 10)
            // Announce state changes to VoiceOver rather than relying on the colour change.
            .accessibilityLabel(session.zoneState.label)
        }
    }

    private var secondaryMetrics: some View {
        HStack {
            metric("time", formatDuration(session.elapsed))
            Divider().background(.white.opacity(0.4)).frame(height: 34)
            metric("distance", String(format: "%.2f km", session.distanceM / 1000))
            Divider().background(.white.opacity(0.4)).frame(height: 34)
            if session.hr != nil, session.hrStatus == "ok" {
                metric("pace", session.paceSecKm.map { Physiology.formatPace($0) } ?? "--:--")
            } else {
                metric("cadence", session.cadence.map { "\(Int($0))" } ?? "--")
            }
        }
        .padding(.vertical, 14)
    }

    private func metric(_ label: String, _ value: String) -> some View {
        VStack(spacing: 1) {
            Text(value)
                .font(.system(size: 26, weight: .semibold, design: .rounded))
                .monospacedDigit()
            Text(label)
                .font(.system(size: 12, weight: .medium, design: .rounded))
                .textCase(.uppercase).opacity(0.75)
        }
        .frame(maxWidth: .infinity)
    }

    /// The last cue persists rather than flashing. At 18 km, half-hearing a cue and being unable to
    /// check what it said is worse than not having it.
    private var cuePanel: some View {
        Group {
            if let cue = session.lastCue {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: cue.level == .safety ? "exclamationmark.triangle.fill"
                                                           : "speaker.wave.2.fill")
                        .font(.system(size: 15))
                    Text(cue.text)
                        .font(.system(size: 16, weight: cue.level == .safety ? .bold : .regular,
                                      design: .rounded))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.black.opacity(cue.level == .safety ? 0.42 : 0.24))
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .transition(.opacity)
            }
        }
    }

    /// One tap, always reachable. This is the highest-value data the app collects.
    private var painButton: some View {
        Button { showPainSheet = true } label: {
            Label("Something hurts", systemImage: "bandage.fill")
                .font(.system(size: 17, weight: .semibold, design: .rounded))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 15)
                .background(.white.opacity(0.18))
                .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .padding(.bottom, 10)
    }

    private func formatDuration(_ t: TimeInterval) -> String {
        let s = Int(t)
        return s >= 3600
            ? String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
            : String(format: "%d:%02d", s / 60, s % 60)
    }
}

// MARK: - Pain entry

struct PainSheet: View {
    @ObservedObject var session: RunSession
    @Binding var isPresented: Bool
    @State private var site = "left_calf"
    @State private var level = 3
    @State private var focal = false

    private let sites = [
        ("left_calf", "Left calf"), ("right_calf", "Right calf"),
        ("left_shin", "Left shin"), ("right_shin", "Right shin"),
        ("left_achilles", "Left Achilles"), ("right_achilles", "Right Achilles"),
        ("left_knee", "Left knee"), ("right_knee", "Right knee"),
        ("left_foot", "Left foot"), ("right_foot", "Right foot"),
        ("left_hip", "Left hip"), ("right_hip", "Right hip"), ("other", "Somewhere else"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("Where") {
                    Picker("Site", selection: $site) {
                        ForEach(sites, id: \.0) { Text($0.1).tag($0.0) }
                    }
                }
                Section {
                    Stepper("Pain: \(level) / 10", value: $level, in: 0...10)
                    Text(painGuidance)
                        .font(.footnote)
                        .foregroundStyle(level > RT.painStop ? .red : .secondary)
                }
                Section {
                    Toggle("It's one specific point, not spread out", isOn: $focal)
                    if focal {
                        Text("A single point of bone pain that worsens with each step is how a "
                             + "stress fracture presents — and it does not have to be severe to be "
                             + "serious. This will stop the run.")
                            .font(.footnote).foregroundStyle(.red)
                    }
                } header: {
                    Text("What kind")
                } footer: {
                    Text("Also log it tomorrow morning if it's still there. Next-day pain is the "
                         + "most informative signal there is and the easiest to forget about once "
                         + "it eases off.")
                }
            }
            .navigationTitle("Log pain")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        // Goes to the controller on the next tick, which is where the safety abort
                        // lives -- so a report above the stop threshold ends the run rather than
                        // merely being filed.
                        if focal {
                            session.reportSymptom("focal_bone_pain")
                        } else {
                            session.reportPain(level)
                        }
                        isPresented = false
                    }
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { isPresented = false }
                }
            }
        }
    }

    private var painGuidance: String {
        switch level {
        case 0...2: return "Acceptable. Carry on, and keep logging it."
        case 3...5: return "Warning band. Volume holds — no increases until two clean weeks, and "
                         + "today becomes easy."
        default: return "Above 5/10 the rule is stop. Every time."
        }
    }
}
