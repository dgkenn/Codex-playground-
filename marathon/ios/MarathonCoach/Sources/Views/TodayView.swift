//
//  TodayView.swift
//  The home screen: one question answered — what am I doing today, and should I?
//
//  Deliberately not a dashboard. Garmin Connect's redesign is widely criticised for being a grid of
//  widgets that each half-work; the failure mode is that nothing on screen is the answer. So this shows
//  today's session, the readiness verdict that may have changed it, and one button. Everything else is
//  a tap away.
//
//  The readiness verdict is shown *above* the session and states plainly when it has modified it,
//  because a plan that silently rewrites itself is the black-box complaint people have about
//  TrainAsONE. If the intervals became an easy run, that must be visible along with why.
//

import SwiftUI

struct TodayView: View {
    @EnvironmentObject var app: AppModel
    @State private var showRun = false
    @State private var showPlan = false
    @State private var showSettings = false

    private var weekday: Int {
        // Monday = 0, to match the plan's day_offset.
        (Calendar.current.component(.weekday, from: Date()) + 5) % 7
    }

    private var todaySession: PlannedSessionDTO? {
        guard let plans = app.plans, let st = app.planState,
              let week = plans.week(phase: st.currentPhase, weekInPhase: st.weekInPhase)
        else { return nil }
        return plans.session(in: week, weekday: weekday)
    }

    private var currentWeek: PlannedWeekDTO? {
        guard let plans = app.plans, let st = app.planState else { return nil }
        return plans.week(phase: st.currentPhase, weekInPhase: st.weekInPhase)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if !app.dataWarnings.isEmpty { warnings }
                    readinessCard
                    sessionCard
                    if let w = currentWeek, !w.notes.isEmpty { notesCard(w) }
                    sensorCard
                }
                .padding()
            }
            .navigationTitle(headline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button { showPlan = true } label: { Image(systemName: "list.bullet.rectangle") }
                }
            }
            .sheet(isPresented: $showSettings) { SettingsView() }
            .sheet(isPresented: $showPlan) { PlanBrowserView() }
            .fullScreenCover(isPresented: $showRun) { runScreen }
            .refreshable { await app.refreshNights() }
        }
    }

    private var headline: String {
        guard let st = app.planState else { return "Get started" }
        return "\(st.currentPhase.replacingOccurrences(of: "_", with: " ").capitalized) · wk \(st.weekInPhase)"
    }

    // MARK: Cards

    private var warnings: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(app.dataWarnings, id: \.self) { w in
                Label(w, systemImage: "exclamationmark.triangle")
                    .font(.footnote)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.yellow.opacity(0.18))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var readinessCard: some View {
        if let r = app.readiness {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Circle().fill(colour(for: r.band)).frame(width: 10, height: 10)
                    Text(r.headline).font(.headline)
                    Spacer()
                    if r.staleDays > 2 {
                        Text("\(r.staleDays)d old").font(.caption).foregroundStyle(.secondary)
                    }
                }
                Text(r.detail).font(.callout).foregroundStyle(.secondary)
                if r.action == "downgrade_to_easy" || r.action == "rest_or_walk" {
                    // Never silently rewrite the plan. See the file header.
                    Label(r.action == "rest_or_walk"
                          ? "Today's session has been cancelled."
                          : "Today's session has been downgraded to easy.",
                          systemImage: "arrow.triangle.2.circlepath")
                        .font(.callout.bold())
                        .padding(.top, 2)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }

    @ViewBuilder
    private var sessionCard: some View {
        if let s = todaySession {
            VStack(alignment: .leading, spacing: 10) {
                Text(s.title).font(.title2.bold())
                HStack(spacing: 14) {
                    if let d = s.duration_min { pill("\(Int(d)) min", "clock") }
                    if let k = s.distance_km { pill(String(format: "%.1f km", k), "ruler") }
                    if let p = s.pace_target { pill("\(p)/km", "speedometer") }
                    if !s.zones.isEmpty {
                        pill("Z" + s.zones.map(String.init).joined(separator: "-"), "heart")
                    }
                }
                if !s.structure.isEmpty {
                    Text(s.structure).font(.callout)
                }
                DisclosureGroup("Why this session") {
                    Text(s.intent).font(.callout).foregroundStyle(.secondary)
                    ForEach(s.cues, id: \.self) { c in
                        Label(c, systemImage: "info.circle").font(.footnote).padding(.top, 2)
                    }
                    if let f = s.fuelling, !f.isEmpty {
                        Label(f, systemImage: "drop").font(.footnote).padding(.top, 4)
                    }
                }
                .font(.subheadline)

                Button { showRun = true } label: {
                    Label("Start", systemImage: "play.fill")
                        .frame(maxWidth: .infinity).padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .disabled(app.zones == nil)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.3))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        } else {
            VStack(alignment: .leading, spacing: 8) {
                Text("Rest day").font(.title2.bold())
                Text("Adaptation happens now, not during the session. A 20-minute walk is fine and "
                     + "often helps; running is not required and does not help.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.3))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }

    private func notesCard(_ w: PlannedWeekDTO) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("This week").font(.headline)
            ForEach(w.notes, id: \.self) { n in
                Label(n, systemImage: "text.alignleft").font(.footnote)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.25))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var sensorCard: some View {
        HStack {
            Circle().fill(app.sensor.status.isUsable ? .green : .orange)
                .frame(width: 9, height: 9)
            Text(app.sensor.status.userMessage).font(.footnote)
            Spacer()
            if let b = app.sensor.batteryPercent {
                Text("\(b)%").font(.footnote.monospacedDigit())
            }
            Button("Connect") { app.sensor.start(mode: .run) }
                .font(.footnote)
        }
        .padding(12)
        .background(.quaternary.opacity(0.25))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var runScreen: some View {
        if let zones = app.zones, let profile = app.profile, let store = app.store,
           let plans = app.plans, let s = todaySession {
            let paces: [String: Double] = ["easy": 450, "marathon": 400, "threshold": 370,
                                          "interval": 340, "repetition": 320]
            let intent = plans.intent(for: s, paces: paces)
            let session = RunSession(sensor: app.sensor, location: app.location, audio: app.audio,
                                     store: store, health: app.health, profile: profile,
                                     zones: zones, intent: intent, plannedTitle: s.title)
            RunContainerView(session: session, sensor: app.sensor,
                             title: s.title, onClose: { showRun = false })
        } else {
            VStack(spacing: 12) {
                Text("Not ready to run yet").font(.headline)
                Text("Finish the assessment week first so the app knows your zones.")
                    .foregroundStyle(.secondary)
                Button("Close") { showRun = false }
            }
            .padding()
        }
    }

    private func pill(_ text: String, _ icon: String) -> some View {
        Label(text, systemImage: icon)
            .font(.footnote.weight(.medium))
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(.quaternary)
            .clipShape(Capsule())
    }

    private func colour(for band: String) -> Color {
        switch band {
        case "primed", "normal": return .green
        case "suppressed": return .orange
        case "strained": return .red
        default: return .gray
        }
    }
}

/// Hosts a `RunSession` and its screen. Deliberately thin: the session owns the only controller, and
/// the view observes it.
struct RunContainerView: View {
    @StateObject private var session: RunSession
    @ObservedObject var sensor: VeritySensor
    let title: String
    let onClose: () -> Void

    init(session: RunSession, sensor: VeritySensor, title: String,
         onClose: @escaping () -> Void) {
        _session = StateObject(wrappedValue: session)
        self.sensor = sensor
        self.title = title
        self.onClose = onClose
    }

    var body: some View {
        RunView(session: session, sensor: sensor, sessionTitle: title)
            .onAppear { session.start() }
            .overlay(alignment: .topTrailing) {
                Button {
                    Task { await session.finish(); onClose() }
                } label: {
                    Image(systemName: "stop.circle.fill").font(.title).padding(12)
                }
                .foregroundStyle(.white.opacity(0.85))
            }
            .onChange(of: session.state) { _, new in
                if new == .aborted { onClose() }
            }
    }
}
