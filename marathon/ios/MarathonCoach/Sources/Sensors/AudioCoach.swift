//
//  AudioCoach.swift
//  Spoken coaching that ducks Apple Music instead of killing it.
//
//  This is a small file with a lot of ways to get it wrong, so the reasoning is written down.
//
//  ## The requirement
//
//  Music plays from Apple Music. Coaching cues arrive over the top, briefly, then the music comes
//  back at full volume. Nothing pauses, nothing stops, and the music app does not lose its "now
//  playing" status or its lock-screen controls.
//
//  ## Why the obvious approach breaks it
//
//  `AVAudioSession.setCategory(.playback)` — the category you would reach for to play audio — is
//  **exclusive** by default. Activating it *stops* whatever else is playing, and Apple Music does not
//  resume on its own afterwards. The user gets one cue and then silence for the rest of the run. This
//  is the single most common way running apps break music playback.
//
//  The fix has three parts, and all three are required:
//
//  1. **`.mixWithOthers`** so activating our session does not interrupt the other app at all.
//  2. **`.duckOthers`** so the music drops in volume while we speak and returns afterwards. Ducking
//     is handled by the system, which is why it sounds like a native navigation prompt rather than
//     two things fighting.
//  3. **Deactivate with `.notifyOthersOnDeactivation`** after speaking, so the system knows to
//     restore the other app's volume promptly rather than at some later point.
//
//  `.duckOthers` and `.mixWithOthers` are usually described as mutually exclusive — and for the
//  *option pair* on a plain `.playback` session they effectively are, since ducking implies mixing.
//  The combination that behaves correctly here is category `.playback` with
//  **`.interruptSpokenAudioAndMixWithOthers` plus `.duckOthers`**: mix (do not stop) with music,
//  duck it while speaking, and interrupt *other spoken audio* — a podcast or audiobook, which you
//  cannot usefully hear underneath a cue anyway — rather than interrupting music.
//
//  ## Why the session is not left active
//
//  Holding an active ducking session for a three-hour run means the music plays quietly for three
//  hours. So the session is activated immediately before speaking and deactivated immediately after.
//  That costs a few milliseconds of latency per cue, which does not matter for a coaching prompt, and
//  it means the music is at full volume the ~99% of the time we have nothing to say.
//
//  ## Why cues are dropped rather than queued
//
//  Nike Run Club has a well-known bug where narration stalls and then dumps all the missed content in
//  a burst after a pause/resume. That is what a queue does to time-sensitive content. A pace cue is
//  only useful for about a minute; after that it is actively misleading, because the runner has
//  already changed something. So `speak(_:)` **replaces** a pending cue of equal or lower priority
//  rather than queueing behind it, and stale cues are discarded outright. The only exception is a
//  safety cue, which always speaks and always interrupts.
//
//  ## Interruptions
//
//  A phone call, Siri, or another app taking exclusive audio all arrive as an interruption. We
//  register for the notification so a cue is never spoken into a phone call, and so the session is
//  re-established afterwards rather than silently staying dead for the rest of the run.
//

import Foundation
import AVFoundation
import Combine

public final class AudioCoach: NSObject, ObservableObject {

    /// Set false to silence coaching entirely without tearing down the run.
    @Published public var enabled = true
    /// What was last spoken, for the run screen to display persistently.
    @Published public private(set) var lastSpoken: (text: String, at: Date)?
    @Published public private(set) var isInterrupted = false

    private let synth = AVSpeechSynthesizer()
    private var pending: Cue?
    private var pendingDeadline: Date?
    private var sessionActive = false

    /// A cue older than this is discarded rather than spoken. Pace guidance goes stale fast: by the
    /// time you hear "ease off" 90 seconds late, you may already have eased off, and being told again
    /// is worse than not being told.
    private let staleAfter: TimeInterval = 20

    public override init() {
        super.init()
        synth.delegate = self
        NotificationCenter.default.addObserver(
            self, selector: #selector(handleInterruption(_:)),
            name: AVAudioSession.interruptionNotification, object: nil)
        NotificationCenter.default.addObserver(
            self, selector: #selector(handleRouteChange(_:)),
            name: AVAudioSession.routeChangeNotification, object: nil)
        configureSession()
    }

    // MARK: - Session

    /// Configure once, at start-up. This does NOT activate the session — see the file header.
    private func configureSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(
                .playback,
                mode: .voicePrompt,
                policy: .default,
                options: [.interruptSpokenAudioAndMixWithOthers, .duckOthers])
        } catch {
            // Non-fatal: coaching goes silent, the run continues, and the screen still works.
            NSLog("AudioCoach: could not configure session: \(error)")
        }
    }

    /// `.voicePrompt` mode matters as much as the options: it tells the system this is a short
    /// navigation-style announcement, which is what makes the ducking behave the way turn-by-turn
    /// directions do, and it routes sensibly to AirPods without stealing the route.
    private func activate() {
        guard !sessionActive else { return }
        do {
            try AVAudioSession.sharedInstance().setActive(true)
            sessionActive = true
        } catch {
            NSLog("AudioCoach: could not activate session: \(error)")
        }
    }

    /// Deactivating with `.notifyOthersOnDeactivation` is what brings the music back up promptly.
    /// Without the option the volume restore can lag noticeably.
    private func deactivate() {
        guard sessionActive else { return }
        do {
            try AVAudioSession.sharedInstance().setActive(
                false, options: [.notifyOthersOnDeactivation])
            sessionActive = false
        } catch {
            NSLog("AudioCoach: could not deactivate session: \(error)")
        }
    }

    // MARK: - Speaking

    /// Speak a cue. Replaces any pending cue of equal or lower priority; never queues behind one.
    public func speak(_ cue: Cue) {
        guard enabled || cue.level == .safety else { return }   // safety ignores the mute switch
        guard !isInterrupted || cue.level == .safety else { return }

        if cue.level == .safety {
            // Interrupt whatever we are mid-sentence on. A "stop now" cue that waits its turn behind
            // a split announcement is a defect, not politeness.
            synth.stopSpeaking(at: .immediate)
            pending = nil
            utter(cue)
            return
        }

        if synth.isSpeaking {
            // Hold at most one cue, and only if it outranks what is already waiting.
            if let p = pending, p.level > cue.level { return }
            pending = cue
            pendingDeadline = Date().addingTimeInterval(staleAfter)
            return
        }
        utter(cue)
    }

    private func utter(_ cue: Cue) {
        activate()
        let u = AVSpeechUtterance(string: cue.text)
        // Slightly faster than default: a runner is not settling in with a novel, and a long cue at
        // default rate outlasts its own relevance.
        u.rate = AVSpeechUtteranceDefaultSpeechRate * 1.08
        u.volume = 1.0
        u.preUtteranceDelay = 0
        u.postUtteranceDelay = 0
        // `Locale.current.identifier` is POSIX-style ("en_US"); AVSpeechSynthesisVoice wants BCP-47
        // ("en-US"). The mismatch is silent -- the initialiser returns nil and the fallback voice is
        // used -- so it would show up only as the wrong accent, which is the kind of defect that
        // survives forever because nobody files it.
        let tag = Locale.preferredLanguages.first ?? Locale.current.identifier.replacingOccurrences(
            of: "_", with: "-")
        u.voice = AVSpeechSynthesisVoice(language: tag)
            ?? AVSpeechSynthesisVoice(language: "en-GB")
        synth.speak(u)
        lastSpoken = (cue.text, Date())
    }

    /// Call when the run ends, so the session does not sit active holding the music down.
    public func stop() {
        synth.stopSpeaking(at: .immediate)
        pending = nil
        deactivate()
    }

    // MARK: - Interruptions and routing

    @objc private func handleInterruption(_ note: Notification) {
        guard let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
        switch type {
        case .began:
            // A call or Siri. Say nothing into it, and drop anything pending — by the time the call
            // ends the cue is meaningless.
            isInterrupted = true
            synth.stopSpeaking(at: .immediate)
            pending = nil
            sessionActive = false
        case .ended:
            isInterrupted = false
            // The category survives an interruption but activation does not, so the next cue will
            // re-activate. Nothing to do here except stop suppressing.
            break
        @unknown default:
            break
        }
    }

    @objc private func handleRouteChange(_ note: Notification) {
        guard let raw = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
              let reason = AVAudioSession.RouteChangeReason(rawValue: raw) else { return }
        // AirPods falling out mid-run is a real event. Do not keep talking to nobody, and do not
        // start playing cues out of the phone speaker in public.
        if reason == .oldDeviceUnavailable {
            synth.stopSpeaking(at: .immediate)
            pending = nil
            deactivate()
        }
    }
}

// MARK: - AVSpeechSynthesizerDelegate

extension AudioCoach: AVSpeechSynthesizerDelegate {

    public func speechSynthesizer(_ s: AVSpeechSynthesizer,
                                  didFinish utterance: AVSpeechUtterance) {
        // Speak the held cue only if it is still timely; otherwise discard. This is the
        // anti-burst rule: stale coaching is worse than no coaching.
        if let cue = pending, let deadline = pendingDeadline, Date() < deadline {
            pending = nil
            pendingDeadline = nil
            utter(cue)
        } else {
            pending = nil
            pendingDeadline = nil
            // Release the duck so the music returns to full volume.
            deactivate()
        }
    }

    public func speechSynthesizer(_ s: AVSpeechSynthesizer,
                                  didCancel utterance: AVSpeechUtterance) {
        deactivate()
    }
}
