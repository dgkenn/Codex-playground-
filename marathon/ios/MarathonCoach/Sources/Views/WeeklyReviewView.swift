//
//  WeeklyReviewView.swift
//  What the weekly review decided, and why — with the gate evidence shown, not summarised.
//
//  This screen exists because of the negative lesson from TrainAsONE: an adaptive plan that changes
//  itself without explanation is one you stop trusting, and for a self-coached user there is no coach to
//  translate the model's intent. So every decision arrives with its reason attached, and the gate
//  evidence is listed with the observed value next to the threshold.
//
//  Phase advancement requires a tap. Volume adjustments do not — they are small, capped, and usually
//  downward.
//

import SwiftUI

struct WeeklyReviewView: View {
    @EnvironmentObject var app: AppModel
    @Environment(\.dismiss) private var dismiss
    let outcome: WeeklyReviewService.Outcome

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    decisionCard
                    if !outcome.decision.warnings.isEmpty { warningsCard }
                    gatesCard
                    if outcome.gates.stalled { stalledCard }
                    if let next = outcome.phaseAdvanceAvailable { advanceCard(next) }
                }
                .padding()
            }
            .navigationTitle("Week in review")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
    }

    private var decisionCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                Text(headline).font(.title3.bold())
            }
            ForEach(outcome.decision.reasons, id: \.self) { r in
                Text(r).font(.callout)
            }
            if let v = outcome.decision.nextVolumeKm {
                LabeledContent("Next week's target", value: String(format: "%.1f km", v))
                    .font(.callout.weight(.medium)).padding(.top, 2)
            }
            Text("Completed \(Int(outcome.decision.completedFraction * 100))% of planned sessions.")
                .font(.footnote).foregroundStyle(.secondary)
            // The rule, stated rather than implied.
            Text("Missed volume is not carried forward. Adding a skipped run to next week turns a rest "
                 + "into a spike, which is the thing the caps exist to prevent.")
                .font(.footnote).foregroundStyle(.secondary).padding(.top, 2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.3))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var warningsCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(outcome.decision.warnings, id: \.self) { w in
                Label(w, systemImage: "info.circle").font(.footnote)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.yellow.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var gatesCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Gates for this phase").font(.headline)
            Text(outcome.gates.guidance).font(.callout).foregroundStyle(.secondary)
            ForEach(rows, id: \.0.key) { row, state in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: state.icon).foregroundStyle(state.colour)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(row.label).font(.subheadline.weight(.medium))
                            if row.safety {
                                Image(systemName: "exclamationmark.shield.fill")
                                    .font(.caption).foregroundStyle(.red)
                            }
                        }
                        // Observed next to the requirement: a gate you cannot see the evidence for is
                        // indistinguishable from an arbitrary obstacle.
                        if let o = row.observed {
                            Text(String(format: "measured: %.2f", o))
                                .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        } else {
                            Text("not measured yet").font(.caption).foregroundStyle(.secondary)
                        }
                        Text(row.rationale).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.25))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var stalledCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("This phase has stalled", systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
            Text("Volume holds where it is. A stalled gate plus rising load is how an overuse injury "
                 + "gets built, so the plan stops adding until something changes.")
                .font(.callout)
            ForEach(outcome.gates.diagnostics, id: \.self) { d in
                Label(d, systemImage: "magnifyingglass").font(.footnote)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.orange.opacity(0.16))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func advanceCard(_ next: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Ready for the next phase", systemImage: "checkmark.seal.fill")
                .font(.headline).foregroundStyle(.green)
            Text("Every gate is met and the minimum weeks are served. Moving to "
                 + "**\(next.replacingOccurrences(of: "_", with: " "))**.")
                .font(.callout)
            Button("Advance to \(next.replacingOccurrences(of: "_", with: " "))") {
                app.advancePhase(to: next)
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .frame(maxWidth: .infinity)
            // Requires a tap on purpose: a plan that reorganises itself overnight without saying why is
            // the thing that makes these apps feel like black boxes.
            Text("Your call, not the app's — this is a real change in what the weeks look like.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.green.opacity(0.14))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private enum RowState {
        case met, unmet, unknown
        var icon: String {
            switch self {
            case .met: return "checkmark.circle.fill"
            case .unmet: return "xmark.circle.fill"
            case .unknown: return "circle.dashed"
            }
        }
        var colour: Color {
            switch self {
            case .met: return .green
            case .unmet: return .red
            case .unknown: return .secondary
            }
        }
    }

    private var rows: [(GateEvaluation.Row, RowState)] {
        outcome.gates.unmet.map { ($0, .unmet) }
            + outcome.gates.unknown.map { ($0, .unknown) }
            + outcome.gates.met.map { ($0, .met) }
    }

    private var headline: String {
        switch outcome.decision.action {
        case .advance: return "Volume goes up"
        case .hold: return "Volume holds"
        case .cut: return "Volume comes down"
        case .cutback: return "Cutback week"
        case .rebuild: return "Rebuilding"
        }
    }

    private var icon: String {
        switch outcome.decision.action {
        case .advance: return "arrow.up.circle.fill"
        case .hold: return "pause.circle.fill"
        case .cut, .rebuild: return "arrow.down.circle.fill"
        case .cutback: return "arrow.down.right.circle.fill"
        }
    }
}
