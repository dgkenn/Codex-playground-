//
//  RehearsalView.swift
//  Run a session that never happened, on the sofa, with the real voice.
//
//  Reachable from Settings rather than the main tab bar, because it is a tool, not a feature — but
//  reachable *in the shipped build* rather than behind a debug flag, for two reasons.
//
//  First, this is a single-user app, so there is no one to hide it from. Second, and more usefully:
//  the day before a session type you have never done — your first tempo, your first long run over two
//  hours — rehearsing it tells you what the app is going to say, which means the cue that arrives at
//  minute 38 is one you have already heard once, in your kitchen, instead of a surprise at the point
//  where you are least able to think about it.
//
//  Everything here writes through `simulated: true`, so nothing it produces can reach the training
//  history, the load model, or the Health app. See `RunSession.simulated`.
//

import SwiftUI

struct RehearsalView: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var selected: Int = 0
    @State private var speed: Double = 1
    @State private var session: RunSession?
    @State private var log: [String] = []

    private var scenarios: [RunScenario] { ScenarioLibrary.all }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Plays a scripted run through the real coach, the real voice and the real "
                         + "run screen. Nothing it produces is saved as training.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Session") {
                    Picker("Scenario", selection: $selected) {
                        ForEach(scenarios.indices, id: \.self) { i in
                            Text(scenarios[i].name).tag(i)
                        }
                    }
                    Text(scenarios[selected].summary)
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Speed") {
                    Picker("Speed", selection: $speed) {
                        Text("Real time").tag(1.0)
                        Text("10×").tag(10.0)
                        Text("60×").tag(60.0)
                    }
                    .pickerStyle(.segmented)
                    Text(speed == 1
                         ? "Real time is the honest test of whether the cue rate is tolerable."
                         : "Compressed. Each tick is still one simulated second, so the controller "
                           + "behaves exactly as it would on a real run — only the waiting is skipped.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section {
                    if session?.state == .running {
                        Button("Stop", role: .destructive) { stop() }
                    } else {
                        Button("Start rehearsal") { start() }
                            .disabled(app.profile == nil)
                    }
                    if app.profile == nil {
                        Text("Finish the screening and setup first — a rehearsal needs your zones.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }

                if let s = session {
                    // Extracted into a child view taking @ObservedObject. Holding `session` in
                    // @State stores the reference but never subscribes to its objectWillChange, so
                    // the rows below would freeze at whatever the values were when the run started
                    // — a live display that is not live, which is worse than no display because it
                    // looks like it is working.
                    LiveSection(session: s)
                }

                if !log.isEmpty {
                    Section("Said so far") {
                        ForEach(log.indices, id: \.self) { i in
                            Text(log[i]).font(.footnote)
                        }
                    }
                }
            }
            .navigationTitle("Rehearse a run")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { stop(); dismiss() }
                }
            }
            .onDisappear { stop() }
        }
    }

    private struct LiveSection: View {
        @ObservedObject var session: RunSession

        var body: some View {
            Section("Live") {
                LabeledContent("Elapsed",
                               value: String(format: "%02d:%02d",
                                             Int(session.elapsed) / 60, Int(session.elapsed) % 60))
                LabeledContent("Heart rate", value: session.hr.map { "\(Int($0)) bpm" } ?? "—")
                LabeledContent("Signal", value: session.hrStatus)
                LabeledContent("Zone", value: session.zoneState.label)
            }
        }
    }

    private func start() {
        guard let store = app.store, let profile = app.profile else { return }
        let zones = ZoneModel.fiveZone(hrMax: profile.hrMax, hrRest: profile.hrRest,
                                       lthr: profile.lthr)
        log = []
        let s = SimulatedRun.session(scenario: scenarios[selected], zones: zones, profile: profile,
                                     audio: app.audio, store: store, timeScale: speed)
        session = s
        s.start(indoor: false)
    }

    private func stop() {
        guard let s = session, s.state == .running || s.state == .paused else { return }
        Task { await s.finish() }
        session = nil
    }
}
