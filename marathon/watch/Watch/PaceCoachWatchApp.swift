import SwiftUI
import CoachCore

@main
struct PaceCoachWatchApp: App {
    @StateObject private var workout = WorkoutManager()

    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(workout)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var wm: WorkoutManager

    var body: some View {
        if wm.running {
            RunView()
        } else if let s = wm.summary {
            SummaryView(summary: s)
        } else {
            StartView()
        }
    }
}

// MARK: - before the run

struct StartView: View {
    @EnvironmentObject var wm: WorkoutManager

    var body: some View {
        List {
            Section {
                Button("Start run / walk") { wm.start() }
                    .foregroundStyle(.green)
                if !wm.authorized {
                    Button("Allow Health access") { wm.requestAuthorization() }
                }
                if let m = wm.message { Text(m).font(.footnote).foregroundStyle(.red) }
            }
            Section("Session") {
                Stepper("\(wm.settings.reps) × \(fmt(wm.settings.runMin)) min", value: $wm.settings.reps, in: 1...12)
                Stepper("Run \(fmt(wm.settings.runMin)) min", value: $wm.settings.runMin, in: 1...30, step: 1)
                Stepper("Walk \(fmt(wm.settings.walkMin)) min", value: $wm.settings.walkMin, in: 0.5...5, step: 0.5)
            }
            Section("Heart rate") {
                Stepper("Ceiling \(Int(wm.settings.ceilingBpm))", value: $wm.settings.ceilingBpm, in: 120...190, step: 1)
                Stepper("Floor \(Int(wm.settings.floorBpm))", value: $wm.settings.floorBpm, in: 90...160, step: 1)
            }
        }
        .navigationTitle("Pace Coach")
        .onAppear { if !wm.authorized { wm.requestAuthorization() } }
    }
}

// MARK: - during the run

struct RunView: View {
    @EnvironmentObject var wm: WorkoutManager

    var body: some View {
        VStack(spacing: 4) {
            Text(label).font(.system(size: 30, weight: .heavy, design: .rounded)).foregroundStyle(color)
            Text(detail).font(.footnote).foregroundStyle(.secondary)
            Text(wm.heartRate.map { "\(Int($0))" } ?? "--")
                .font(.system(size: 44, weight: .semibold, design: .rounded))
                .monospacedDigit()
            HeartBar(hr: wm.heartRate, floor: wm.settings.floorBpm, ceiling: wm.settings.ceilingBpm)
                .frame(height: 8)
            Text(clock(wm.elapsed)).font(.footnote).monospacedDigit().foregroundStyle(.secondary)
            Button("End", role: .destructive) { wm.end() }.padding(.top, 2)
        }
        .padding(.horizontal, 4)
    }

    var label: String {
        switch wm.phase {
        case .warmup: return "WARM-UP"
        case .run: return "RUN"
        case .walk: return "WALK"
        case .cooldown: return "COOL-DOWN"
        case .done: return "DONE"
        }
    }

    var color: Color {
        switch wm.phase {
        case .run: return .orange
        case .walk, .warmup: return .green
        default: return .blue
        }
    }

    var detail: String {
        let s = wm.settings
        switch wm.phase {
        case .run:
            let left = max(0, s.runMin * 60 - wm.phaseElapsed)
            return "block \(wm.rep) of \(s.reps) · \(clock(left)) left"
        case .walk: return "back to \(Int(s.floorBpm)) · \(clock(wm.phaseElapsed))"
        case .warmup: return "walk · \(clock(max(0, 300 - wm.phaseElapsed)))"
        default: return clock(wm.phaseElapsed)
        }
    }
}

/// Heart rate on a bar from the floor (left) to the ceiling (right).
struct HeartBar: View {
    let hr: Double?
    let floor: Double
    let ceiling: Double

    var body: some View {
        GeometryReader { g in
            let f = hr.map { min(1, max(0, ($0 - floor) / max(1, ceiling - floor))) } ?? 0
            ZStack(alignment: .leading) {
                Capsule().fill(Color.gray.opacity(0.3))
                Capsule().fill(f > 0.85 ? Color.red : Color.orange).frame(width: g.size.width * f)
            }
        }
    }
}

// MARK: - after the run

struct SummaryView: View {
    @EnvironmentObject var wm: WorkoutManager
    let summary: HrBlockSummary

    var body: some View {
        List {
            Text("Running \(clock(summary.runningS))")
            Text("Full blocks \(summary.blocksFull) of \(summary.blocksPlanned ?? summary.runBlocks)")
            if summary.blocksCut > 0 { Text("Cut by heart rate \(summary.blocksCut)") }
            if let p = summary.peakRunHr { Text("Peak in blocks \(Int(p))") }
            Button("Done") { wm.summary = nil }
        }
        .navigationTitle("How it went")
    }
}

func clock(_ s: Double) -> String {
    let t = Int(s.rounded())
    return String(format: "%d:%02d", t / 60, t % 60)
}

func fmt(_ m: Double) -> String {
    m == m.rounded() ? String(Int(m)) : String(format: "%.1f", m)
}
