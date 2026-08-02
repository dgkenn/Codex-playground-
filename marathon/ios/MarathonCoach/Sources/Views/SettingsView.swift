//
//  SettingsView.swift
//  Configuration, data export, and the honest status of every input.
//
//  The "sources" section exists because the correctness of the readiness engine depends on which HRV
//  metric is in play, and that is invisible otherwise. HealthKit can only provide SDNN; the
//  SleepController provides Polar-derived RMSSD. They are different quantities, cannot be converted,
//  and are never mixed into one baseline — so the app states which one it is using rather than
//  presenting an undifferentiated "HRV".
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var urlText = UserDefaults.standard.string(forKey: "sleepControllerURL") ?? ""
    @State private var tokenText = ""
    @State private var tokenSaved = TokenStore.load() != nil
    @State private var exportURL: URL?
    @State private var showRehearsal = false
    @AppStorage("toneChannel") private var toneChannel = true
    @AppStorage("toneLevel") private var toneLevel = 0.5
    @AppStorage("splitEveryM") private var splitEveryM = 1000.0

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    if let p = app.profile {
                        LabeledContent("Age", value: "\(Int(p.age))")
                        LabeledContent("Resting HR", value: "\(Int(p.hrRest)) bpm")
                        LabeledContent("Max HR", value: "\(Int(p.hrMax)) bpm")
                        LabeledContent("Max HR source",
                                       value: p.hrMaxSource.replacingOccurrences(of: "_", with: " "))
                        LabeledContent("VDOT", value: String(format: "%.0f", p.vdot))
                        LabeledContent("Pace basis",
                                       value: p.prescriptionBasis == "hr_from_ramp"
                                       ? "measured HR/speed" : "VDOT tables")
                        LabeledContent("HR/speed slope",
                                       value: String(format: "%.1f bpm per km/h", p.hrSpeedSlope))
                    } else {
                        Text("No profile yet — run the assessment week.")
                    }
                } header: {
                    Text("Profile")
                } footer: {
                    if app.profile?.hrMaxSource == "age_formula" {
                        Text("Max HR is still an age estimate, with roughly ±7 bpm standard error and "
                             + "up to 20 bpm individual error. It is replaced only by a heart rate "
                             + "observed under strict conditions, and an unconfirmed optical reading "
                             + "can move it by at most 5 bpm at a time — one artifact adopted as a "
                             + "maximum would shift every zone upward.")
                    }
                }

                Section {
                    TextField("http://sleep.local:8000", text: $urlText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField(tokenSaved ? "Token saved — enter to replace" : "Ingest token",
                                text: $tokenText)
                    Button("Save") { saveConnection() }
                    if tokenSaved {
                        Button("Remove token", role: .destructive) {
                            TokenStore.delete(); tokenSaved = false
                        }
                    }
                } header: {
                    Text("SleepController")
                } footer: {
                    Text("The token is kept in the Keychain, not in preferences. The authoritative HRV "
                         + "series is the RMSSD your controller computes from Polar beat intervals — "
                         + "Apple Health can only provide SDNN, which is a different measurement and "
                         + "is kept in its own series with its own baseline rather than blended in.")
                }

                Section("Data") {
                    Button("Export everything") { doExport() }
                    if let u = exportURL {
                        ShareLink(item: u) { Label("Share export", systemImage: "square.and.arrow.up") }
                    }
                    Text("One JSON file with your profile, sessions, nights and pain log. It is your "
                         + "data; you should be able to take it elsewhere.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Health") {
                    Button("Grant Health access") {
                        Task { try? await app.health.requestAuthorization() }
                    }
                    Text("Runs are written to Health so they appear in Fitness. No heart-rate "
                         + "variability is ever written back — writing a Polar RMSSD into a field "
                         + "labelled SDNN would corrupt your own health record with a mislabelled "
                         + "metric.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Audio") {
                    Toggle("Pace tones", isOn: $toneChannel)
                    Text("Short beeps that tell you whether you are holding pace, without ducking "
                         + "your music. Falling pair = ease off, rising pair = lift, single pip = "
                         + "back on pace. Silence means you are fine.")
                        .font(.footnote).foregroundStyle(.secondary)

                    Toggle("Chime before speech", isOn: $app.audio.preRollBeforeSpeech)
                    Text("Three rising notes just before the voice, so the first words do not land "
                         + "while the music is still dipping.")
                        .font(.footnote).foregroundStyle(.secondary)

                    VStack(alignment: .leading) {
                        Text("Tone volume")
                        Slider(value: $toneLevel, in: 0.1...1.0)
                    }
                    Button("Play them now") {
                        // Ordered as you would meet them, with enough spacing to tell apart.
                        let order: [Earcon] = [.ease, .lift, .inBand, .attend, .degraded]
                        for (i, e) in order.enumerated() {
                            DispatchQueue.main.asyncAfter(deadline: .now() + Double(i) * 0.9) {
                                app.audio.earcons.play(e)
                            }
                        }
                    }
                    Text("Do this with Apple Music playing. If a tone is inaudible over the music, "
                         + "or loud enough to startle you, this slider is the fix.")
                        .font(.footnote).foregroundStyle(.secondary)

                    Picker("Spoken splits", selection: $splitEveryM) {
                        Text("Every km").tag(1000.0)
                        Text("Every 2 km").tag(2000.0)
                        Text("Off").tag(0.0)
                    }
                    Text("A two-second line — distance, pace, on-pace or not. This is what makes "
                         + "silence readable as \"you are fine\" rather than \"the app has died\".")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Testing") {
                    Button("Rehearse a run") { showRehearsal = true }
                    Text("Play a scripted session through the real voice, without the sensor. Use it "
                         + "to hear what a session type sounds like before you do it for real.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $showRehearsal) { RehearsalView() }
            .onChange(of: toneLevel) { _, new in app.audio.earcons.level = Float(new) }
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
    }

    private func saveConnection() {
        if let u = URL(string: urlText), !urlText.isEmpty {
            UserDefaults.standard.set(u, forKey: "sleepControllerURL")
        }
        if !tokenText.isEmpty {
            tokenSaved = TokenStore.save(tokenText)
            tokenText = ""
        }
        Task { await app.refreshNights() }
    }

    private func doExport() {
        guard let store = app.store, let data = try? store.exportAll() else { return }
        let u = FileManager.default.temporaryDirectory
            .appendingPathComponent("marathon-coach-export.json")
        try? data.write(to: u, options: [.atomic])
        exportURL = u
    }
}

/// Read-only browse of the whole plan, so the gates and phases are inspectable rather than implied.
struct PlanBrowserView: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                if let plans = app.plans {
                    ForEach(plans.plan.phases, id: \.phase) { phase in
                        Section {
                            Text(phase.goal).font(.callout)
                            LabeledContent("Minimum weeks", value: "\(phase.min_weeks)")
                            if let s = phase.stall_review_weeks {
                                LabeledContent("Stall review", value: "week \(s)")
                            }
                            ForEach(phase.gates, id: \.key) { g in
                                VStack(alignment: .leading, spacing: 3) {
                                    Label(g.label,
                                          systemImage: g.safety ? "exclamationmark.shield.fill"
                                                                : "checkmark.circle")
                                        .font(.subheadline.weight(.medium))
                                    Text(g.rationale).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        } header: {
                            Text(phase.phase.replacingOccurrences(of: "_", with: " ").capitalized)
                        }
                    }
                } else {
                    Text("Plan resource not loaded.")
                }
            }
            .navigationTitle("The plan")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
