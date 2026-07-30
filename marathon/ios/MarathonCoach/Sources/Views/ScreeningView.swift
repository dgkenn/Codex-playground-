//
//  ScreeningView.swift
//  The ACSM pre-participation screen. A gate, not a formality.
//
//  Design notes that matter more than the layout:
//
//  • **The three exertional symptoms are asked first and asked plainly.** Chest discomfort, unusual
//    breathlessness and exertional dizziness are the answers that stop the plan, and burying them
//    below a wall of demographic questions is how a screening form becomes something people click
//    through. They get their own section, at the top, in plain language.
//
//  • **The result is framed correctly in both directions.** The 2015 ACSM revision deliberately
//    *lowered* the barrier to starting exercise, because for almost everyone the risk of not exercising
//    is larger. So a clear result says "cleared" without ceremony, and a referral says what to do next
//    rather than implying exercise is dangerous.
//
//  • **Absolute risk is given, once, with a number.** Marathon cardiac arrest occurs in roughly 1 per
//    184,000 participants (Kim et al., NEJM 2012). Withholding that invites either complacency or
//    dread; stating it supports the actual rule, which is never to train through exertional symptoms.
//
//  The user is a physician. This screen assumes competence and does not lecture — but it also does not
//  skip the check on that basis, because knowing the criteria and applying them to yourself at 6 a.m.
//  are different things.
//

import SwiftUI

struct ScreeningView: View {
    @EnvironmentObject var app: AppModel

    @State private var chestDiscomfort = false
    @State private var dyspnoea = false
    @State private var dizziness = false
    @State private var palpitations = false
    @State private var oedema = false
    @State private var claudication = false

    @State private var knownCardiovascular = false
    @State private var knownMetabolic = false
    @State private var knownRenal = false

    @State private var exercisingRegularly = true
    @State private var familyHistory = false
    @State private var musculoskeletalPain = false
    @State private var onBetaBlocker = false

    @State private var age: Double = 30
    @State private var restingHr: Double = 55
    @State private var showResult = false

    private var anySymptom: Bool {
        chestDiscomfort || dyspnoea || dizziness || palpitations || oedema || claudication
    }
    private var anyDisease: Bool { knownCardiovascular || knownMetabolic || knownRenal }

    private var clearance: String {
        if anySymptom { return "urgent_review" }
        if anyDisease { return "medical_clearance_first" }
        return "proceed"
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Two minutes, once. Everything else in the plan is behind this, because the "
                         + "plan eventually asks you for a maximal effort.")
                        .font(.callout)
                }

                Section {
                    Toggle("Chest pain, pressure or tightness on exertion", isOn: $chestDiscomfort)
                    Toggle("Breathlessness out of proportion to the effort", isOn: $dyspnoea)
                    Toggle("Light-headedness or feeling faint when exercising", isOn: $dizziness)
                    Toggle("Palpitations or an irregular heartbeat", isOn: $palpitations)
                    Toggle("Ankle swelling", isOn: $oedema)
                    Toggle("Calf pain on walking that eases with rest", isOn: $claudication)
                } header: {
                    Text("Any of these, at rest or on exertion?")
                } footer: {
                    Text("The first three are the ones that matter most. Any of them stops the plan "
                         + "until it has been explained — whether or not it feels like it should.")
                        .foregroundStyle(anySymptom ? .red : .secondary)
                }

                Section("Known disease") {
                    Toggle("Cardiovascular disease", isOn: $knownCardiovascular)
                    Toggle("Diabetes (type 1 or 2)", isOn: $knownMetabolic)
                    Toggle("Kidney disease", isOn: $knownRenal)
                }

                Section("Context") {
                    Toggle("Currently exercising regularly (30+ min, 3+ days/week, 3+ months)",
                           isOn: $exercisingRegularly)
                    Toggle("Family history of sudden death under 50", isOn: $familyHistory)
                    Toggle("Current joint or muscle pain", isOn: $musculoskeletalPain)
                    Toggle("Taking a beta blocker", isOn: $onBetaBlocker)
                }

                Section("Starting numbers") {
                    Stepper("Age: \(Int(age))", value: $age, in: 16...90)
                    Stepper("Resting heart rate: \(Int(restingHr)) bpm", value: $restingHr, in: 35...90)
                    Text("Resting heart rate: measure it lying down, before you get up, for a minute. "
                         + "It anchors every zone, so a guess here propagates everywhere.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section {
                    Button("Check") { showResult = true }
                        .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("Before you start")
            .sheet(isPresented: $showResult) { resultSheet }
        }
    }

    @ViewBuilder
    private var resultSheet: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    switch clearance {
                    case "urgent_review":
                        Label("Get these assessed before training", systemImage: "exclamationmark.triangle.fill")
                            .font(.title3.bold()).foregroundStyle(.red)
                        Text("Exertional chest discomfort, unusual breathlessness and exertional "
                             + "dizziness are the three symptoms that need explaining before you load "
                             + "your cardiovascular system deliberately. This is not a reason to be "
                             + "alarmed; it is a reason to find out.")
                        Text("The plan stays locked until this is resolved. That is the point of "
                             + "asking.")
                            .font(.callout.italic())
                    case "medical_clearance_first":
                        Label("Medical clearance first", systemImage: "stethoscope")
                            .font(.title3.bold()).foregroundStyle(.orange)
                        Text("With known cardiovascular, metabolic or renal disease, ACSM recommends "
                             + "clearance before starting or intensifying exercise. Light-to-moderate "
                             + "activity is usually actively encouraged even so — the clearance step is "
                             + "about the progression this plan involves, not about whether you should "
                             + "move.")
                    default:
                        Label("Cleared to start", systemImage: "checkmark.seal.fill")
                            .font(.title3.bold()).foregroundStyle(.green)
                        Text("No symptoms, no known cardiovascular, metabolic or renal disease.")
                        Text("For calibration rather than alarm: cardiac arrest during a marathon or "
                             + "half marathon occurs in roughly 1 per 184,000 participants (Kim et al., "
                             + "NEJM 2012). The absolute risk is very low. The rule that follows is not "
                             + "'do not run' — it is 'never train through exertional chest discomfort, "
                             + "unusual breathlessness, or feeling faint'.")
                            .font(.callout)
                    }

                    if onBetaBlocker {
                        divider
                        Text("Beta blockade blunts heart rate at every intensity, so zones from an age "
                             + "formula will be wrong for you. The ramp test matters more than usual, "
                             + "and effort and the talk test should lead.")
                            .font(.callout)
                    }
                    if familyHistory {
                        divider
                        Text("Family history of sudden death under 50 is worth raising with a clinician "
                             + "before any maximal effort, even with no symptoms of your own.")
                            .font(.callout)
                    }
                    if musculoskeletalPain {
                        divider
                        Text("Get the existing pain assessed first. Starting a running programme on an "
                             + "unexplained painful joint is how a small problem becomes the reason you "
                             + "stop.")
                            .font(.callout)
                    }

                    if clearance == "proceed" {
                        Button("Continue to the assessment week") { complete() }
                            .buttonStyle(.borderedProminent)
                            .frame(maxWidth: .infinity)
                            .padding(.top, 8)
                    }
                }
                .padding()
            }
            .navigationTitle("Result")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Back") { showResult = false }
                }
            }
        }
    }

    private var divider: some View {
        Divider().padding(.vertical, 2)
    }

    private func complete() {
        // HRmax starts as the Tanaka estimate and is explicitly labelled as such, so nothing downstream
        // mistakes it for a measurement. The ramp test replaces the slope; a guarded observation later
        // replaces the max.
        let hrMax = 208.0 - 0.7 * age
        var p = app.profile ?? AthleteProfile(
            age: age, hrRest: restingHr, hrMax: hrMax, hrMaxSource: "age_formula",
            vdot: 22, vdotSource: "unset", lthr: nil, hrSpeedSlope: 12)
        p.age = age
        p.hrRest = restingHr
        p.hrMax = hrMax
        p.hrMaxSource = "age_formula"
        p.screeningCleared = true
        p.screeningDate = Date()
        app.save(profile: p)
        showResult = false
    }
}
