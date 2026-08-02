//
//  EarconPlayer.swift
//  The tones themselves.
//
//  ## Why these are synthesised rather than shipped as files
//
//  Not to save a few kilobytes. Because the parameters below — frequency, duration, the gap between
//  the two pips, the attack and release envelope — are things that will want adjusting once they have
//  been heard through AirPods at 160 steps per minute with music underneath, and a number in a Swift
//  file can be adjusted. A rendered .caf cannot.
//
//  ## Why they must not duck the music
//
//  This is the whole reason the tone channel exists. `AudioCoach` activates its session with
//  `.duckOthers`, which is right for speech: a sentence you cannot hear over music is a sentence
//  wasted. It is wrong for a 180 ms pip. Ducking Apple Music four times a minute is worse than the
//  problem the pips solve, and it is exactly the behaviour that makes people turn coaching off.
//
//  There is only one `AVAudioSession` per app, so the two cannot be configured differently at the
//  same time. What can be done — and what this does — is set the category options immediately before
//  activation, since the session is only active while something is actually playing:
//
//    * speech  -> `.duckOthers` + `.interruptSpokenAudioAndMixWithOthers`, music dips, then restores
//    * tones   -> `.mixWithOthers` alone, music is untouched and the pip sits on top of it
//
//  The cost is a category change per sound, which at these rates is nothing.
//
//  ## Why an envelope
//
//  A raw sine burst clicks at both ends, because the waveform starts and stops at a non-zero value.
//  The click is louder and more startling than the tone. A few milliseconds of raised-cosine fade at
//  each end removes it entirely. This is the difference between a sound that reads as part of the app
//  and one that reads as a fault.
//

import Foundation
import AVFoundation

/// Plays the non-speech vocabulary without disturbing whatever else is playing.
public final class EarconPlayer {

    // MARK: Tuning

    /// Pitches chosen to sit above most music's vocal range so they are audible without being loud,
    /// and far enough apart that the rise/fall contour survives compression and wind noise.
    private enum Pitch {
        static let low: Double = 587.33      // D5
        static let mid: Double = 740.0       // F#5
        static let high: Double = 880.0      // A5
    }

    /// Short. A pip long enough to notice consciously is long enough to interrupt a thought.
    private let pipS: Double = 0.09
    /// Gap inside a two-pip pattern. Long enough to hear as two events, short enough to hear as one
    /// gesture rather than two separate warnings.
    private let gapS: Double = 0.055
    /// Raised-cosine fade at each end of every pip, to kill the click.
    private let fadeS: Double = 0.008

    /// Level relative to full scale. Deliberately modest — the tone has to be heard *over* music, not
    /// instead of it, and an alarm-loud pip four times a minute is its own kind of failure.
    public var level: Float = 0.5

    // MARK: State

    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private let format: AVAudioFormat
    private var buffers: [Earcon: AVAudioPCMBuffer] = [:]
    private var engineRunning = false

    public init() {
        format = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 1)!
        engine.attach(player)
        engine.connect(player, to: engine.mainMixerNode, format: format)
        buffers = Self.allBuffers(format: format, pipS: pipS, gapS: gapS, fadeS: fadeS)
    }

    // MARK: Playing

    public func play(_ earcon: Earcon) {
        guard let buffer = buffers[earcon] else { return }
        do {
            let session = AVAudioSession.sharedInstance()
            // `.mixWithOthers` WITHOUT `.duckOthers`. See the file header — this is the single most
            // important line in this file. `.ambient` would be wrong: it is silenced by the ring
            // switch, and a pace cue that disappears because the phone is on silent is a pace cue
            // that cannot be relied on.
            try session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
            try session.setActive(true)

            if !engineRunning {
                try engine.start()
                engineRunning = true
            }
            player.volume = level
            player.play()
            player.scheduleBuffer(buffer, at: nil, options: []) { [weak self] in
                // Deactivate on the main queue once the sound has finished, so the session is not
                // held open between tones. Held open, it would keep other apps in a mixed state for
                // the whole run for no reason.
                DispatchQueue.main.async { self?.finish() }
            }
        } catch {
            NSLog("EarconPlayer: could not play \(earcon.rawValue): \(error)")
        }
    }

    private func finish() {
        guard engineRunning else { return }
        player.stop()
        engine.pause()
        engineRunning = false
        try? AVAudioSession.sharedInstance().setActive(false,
                                                       options: [.notifyOthersOnDeactivation])
    }

    public func stop() { finish() }

    // MARK: Synthesis

    private static func allBuffers(format: AVAudioFormat, pipS: Double, gapS: Double,
                                   fadeS: Double) -> [Earcon: AVAudioPCMBuffer] {
        func seq(_ steps: [(Double, Double)]) -> [(Double, Double)] { steps }

        // Contour carries the meaning. Falling means back off, rising means more — the same mapping
        // as almost every other interface a person has used, which is the point: nothing to learn.
        let recipes: [Earcon: [(freq: Double, dur: Double)]] = [
            .ease:    [(Pitch.high, pipS), (0, gapS), (Pitch.low, pipS)],
            .lift:    [(Pitch.low, pipS), (0, gapS), (Pitch.high, pipS)],
            .inBand:  [(Pitch.mid, pipS * 1.3)],
            .attend:  [(Pitch.low, pipS * 0.6), (0, gapS * 0.7),
                       (Pitch.mid, pipS * 0.6), (0, gapS * 0.7),
                       (Pitch.high, pipS * 0.6)],
            // Deliberately unlike the others: low, dull and doubled, so a degradation notice is never
            // mistaken for a pace instruction.
            .degraded: [(220.0, pipS * 1.2), (0, gapS), (220.0, pipS * 1.2)],
        ]

        var out: [Earcon: AVAudioPCMBuffer] = [:]
        for (earcon, recipe) in recipes {
            if let b = render(recipe, format: format, fadeS: fadeS) { out[earcon] = b }
        }
        return out
    }

    /// Render a sequence of `(frequency, duration)` segments. Frequency 0 means silence.
    private static func render(_ segments: [(freq: Double, dur: Double)],
                               format: AVAudioFormat, fadeS: Double) -> AVAudioPCMBuffer? {
        let rate = format.sampleRate
        let total = segments.reduce(0.0) { $0 + $1.dur }
        let frames = AVAudioFrameCount(total * rate)
        guard frames > 0,
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames),
              let channel = buffer.floatChannelData?[0] else { return nil }
        buffer.frameLength = frames

        var index = 0
        for seg in segments {
            let n = Int(seg.dur * rate)
            let fade = max(1, Int(fadeS * rate))
            for i in 0..<n where index + i < Int(frames) {
                var sample: Float = 0
                if seg.freq > 0 {
                    let phase = 2.0 * Double.pi * seg.freq * Double(i) / rate
                    // Raised-cosine envelope at both ends. Without it the discontinuity at the start
                    // and end of the burst is audible as a click, which is louder and more startling
                    // than the tone it wraps.
                    var envelope = 1.0
                    if i < fade {
                        envelope = 0.5 * (1 - cos(Double.pi * Double(i) / Double(fade)))
                    } else if i > n - fade {
                        envelope = 0.5 * (1 - cos(Double.pi * Double(n - i) / Double(fade)))
                    }
                    sample = Float(sin(phase) * envelope)
                }
                channel[index + i] = sample
            }
            index += n
        }
        return buffer
    }
}
