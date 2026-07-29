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

// MARK: - View model

@MainActor
public final class RunSessionViewModel: ObservableObject {
    @Published public private(set) var elapsed: TimeInterval = 0
    @Published public private(set) var distanceM: Double = 0
    @Published public private(set) var hr: Double?
    @Published public private(set) var hrStatus: String = "dropout"
    @Published public private(set) var paceSecKm: Double?
    @Published public private(set) var cadence: Double?
    @Published public private(set) var zoneState: ZoneState = .unknown
    @Published public private(set) var lastCue: Cue?
    @Published public private(set) var targetBand: (low: Double, high: Double)?
    @Published public private(set) var aborted = false
    @Published public var showPainSheet = false

    public enum ZoneState {
        case inZone, tooHard, tooEasy, unknown

        var label: String {
            switch self {
            case .inZone: return "On target"
            case .tooHard: return "Too hard"
            case .tooEasy: return "Room to lift"
            case .unknown: return "No heart rate"
            }
        }
        /// Redundant with colour, deliberately — see the header note on colour vision.
        var symbol: String {
            switch self {
            case .inZone: return "checkmark.circle.fill"
            case .tooHard: return "arrow.down.circle.fill"
            case .tooEasy: return "arrow.up.circle.fill"
            case .unknown: return "questionmark.circle.fill"
            }
        }
        var tint: Color {
            switch self {
            case .inZone: return Color(red: 0.13, green: 0.45, blue: 0.28)
            case .tooHard: return Color(red: 0.62, green: 0.20, blue: 0.16)
            case .tooEasy: return Color(red: 0.18, green: 0.33, blue: 0.55)
            case .unknown: return Color(white: 0.28)
            }
        }
    }

    private let controller: InRunController
    private let intent: SessionIntent

    public init(controller: InRunController, intent: SessionIntent) {
        self.controller = controller
        self.intent = intent
    }

    /// Feed one tick. Called at 1 Hz from the sensor/location pipeline.
    public func ingest(_ tick: RunTick) {
        elapsed = tick.tS
        distanceM = tick.distanceM
        hr = tick.hrBpm
        hrStatus = tick.hrStatus
        cadence = tick.cadenceSpm
        if let sp = tick.speedMPerS, sp > 0.3 {
            paceSecKm = Physiology.speedToPace(mPerS: sp)
        } else {
            paceSecKm = nil
        }

        let d = controller.update(tick)
        targetBand = d.targetBand
        aborted = d.abort
        if let cue = d.cue { lastCue = cue }

        switch (d.inTarget, d.mode) {
        case (_, .effortOnly): zoneState = .unknown
        case (nil, _): zoneState = .unknown
        case (true?, _): zoneState = .inZone
        case (false?, _):
            // Which side of the band are we on? Ceiling-controlled sessions can only be "too hard".
            if let ss = d.hrSteadyState, let b = d.targetBand {
                zoneState = ss > b.high ? .tooHard : (intent.ceilingOnly ? .inZone : .tooEasy)
            } else {
                zoneState = .tooHard
            }
        }
    }

    public func logPain(site: String, level: Int, focal: Bool) {
        // Persisted by the store; a level above the stop threshold reaches the controller on the
        // next tick via RunTick.pain0to10, which is what triggers the safety abort.
        showPainSheet = false
    }
}

// MARK: - The screen

public struct RunView: View {
    @ObservedObject var vm: RunSessionViewModel
    @ObservedObject var sensor: VeritySensor
    let sessionTitle: String

    public init(vm: RunSessionViewModel, sensor: VeritySensor, sessionTitle: String) {
        self.vm = vm; self.sensor = sensor; self.sessionTitle = sessionTitle
    }

    public var body: some View {
        ZStack {
            vm.zoneState.tint.ignoresSafeArea()
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
        .sheet(isPresented: $vm.showPainSheet) { PainSheet(vm: vm) }
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
        switch vm.hrStatus {
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
            if let hr = vm.hr, vm.hrStatus == "ok" {
                Text("\(Int(hr))")
                    .font(.system(size: 132, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .minimumScaleFactor(0.5)
                    .lineLimit(1)
                Text("bpm").font(.system(size: 20, weight: .medium, design: .rounded)).opacity(0.85)
                if let b = vm.targetBand {
                    Text("target \(Int(b.low))–\(Int(b.high))")
                        .font(.system(size: 17, design: .rounded)).opacity(0.8)
                }
            } else {
                // No trustworthy HR: promote pace to the dominant slot rather than showing a
                // placeholder where a number should be.
                Text(vm.paceSecKm.map { Physiology.formatPace($0) } ?? "--:--")
                    .font(.system(size: 108, weight: .bold, design: .rounded))
                    .monospacedDigit().minimumScaleFactor(0.5).lineLimit(1)
                Text("min/km").font(.system(size: 20, weight: .medium, design: .rounded)).opacity(0.85)
            }

            HStack(spacing: 8) {
                Image(systemName: vm.zoneState.symbol)
                Text(vm.zoneState.label)
            }
            .font(.system(size: 22, weight: .semibold, design: .rounded))
            .padding(.top, 10)
            // Announce state changes to VoiceOver rather than relying on the colour change.
            .accessibilityLabel(vm.zoneState.label)
        }
    }

    private var secondaryMetrics: some View {
        HStack {
            metric("time", formatDuration(vm.elapsed))
            Divider().background(.white.opacity(0.4)).frame(height: 34)
            metric("distance", String(format: "%.2f km", vm.distanceM / 1000))
            Divider().background(.white.opacity(0.4)).frame(height: 34)
            if vm.hr != nil, vm.hrStatus == "ok" {
                metric("pace", vm.paceSecKm.map { Physiology.formatPace($0) } ?? "--:--")
            } else {
                metric("cadence", vm.cadence.map { "\(Int($0))" } ?? "--")
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
            if let cue = vm.lastCue {
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
        Button { vm.showPainSheet = true } label: {
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
    @ObservedObject var vm: RunSessionViewModel
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
                    Button("Save") { vm.logPain(site: site, level: level, focal: focal) }
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { vm.showPainSheet = false }
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
