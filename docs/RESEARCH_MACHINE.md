# Autonomous research machine — operating protocol

The standing protocol for running this repo as a 24/7, self-learning, publication-focused research
loop. Auto-loaded via CLAUDE.md. Read `docs/LESSONS.md` and `docs/EXPERIMENT_QUEUE.md` at the start of
every work cycle before doing anything else.

## Mission
Produce **ultra-high-impact findings that survive hostile peer review** (target: Anesthesiology / CCM /
ICM and above — Nature Medicine / JAMA / Lancet Digital Health for the strongest). Primary asset: HEEDB
(109k EEG + neuro outcomes, multi-site) via the frozen EEG foundation model; secondary: MIMIC-IV / eICU /
VitalDB / INSPIRE. **A finding does not exist until it has survived the hostile-review gate below.**

## The self-learning loop (one cycle)
1. **Orient** — read `docs/LESSONS.md` and `docs/EXPERIMENT_QUEUE.md`. Never repeat a ruled-out dead end.
2. **Pick** the top-ranked open experiment that fits current compute (CPU, overnight OK — see below).
2b. **GATE (mandatory pre-run — see `docs/IDEA_GATE.md`).** Score the candidate against the empirical gate
   BEFORE spending compute. Hard-fail if there is no ground-truth reference in the data or no named
   direction-predicting mechanism. Prefer a sharp falsifiable quantitative prediction (these produce the
   cleanest wins AND the cleanest nulls). Cheaply KILL gate-failures without running them — the kill list is
   where the gate pays for itself. Depth on a confirmed seam nears exhaustion; periodically hunt for new
   (mechanism + ground-truth reference + subgroup driver) triples.
3. **Run** it (delegate per the model policy). Log raw results to `cache/` + a dated note.
4. **HOSTILE-REVIEW GATE (mandatory — see next section).** Attack the result until it breaks or survives.
   A result that hasn't passed the gate is provisional and must NOT be reported as a finding.
5. **LEARN (mandatory).** Append to `docs/LESSONS.md`: what the experiment showed AND **what every
   red-team attack tried, what broke, and what survived, with the mechanism.** The lessons from the
   *attacks* are the most valuable memory — they stop us re-making the same mistakes. Re-rank the queue.
6. **Persist** — commit + push every cycle (reaps wipe uncommitted work). Never commit PHI.
7. **Promote or continue** — survived the gate + externally validated → advance toward manuscript; else
   pull the next queue item.

Self-learning = the filesystem is durable memory. Each cycle READS and UPDATES LESSONS/QUEUE/LEDGER,
and every red-team round writes its attack→outcome back into LESSONS, so the machine gets harder to fool
over time.

## Hostile-review gate (MANDATORY on every finding — aggressive by default)
Nothing is a "finding" until it survives this. Run it as a parallel panel (sonnet adversaries + haiku
reproduction), most-severe-first, and iterate rounds until a full round surfaces no new conclusion-changing
hole. Each finding must clear ALL of these lenses:
1. **Statistics / overfitting** — p≫n variance (in-sample vs OOF gap), multiplicity, CI honesty,
   leakage, seed/fold sensitivity, calibration.
2. **Causal / confounding** — confounding-by-indication, collider/selection, immortal-time (landmark),
   negative-control calibration, E-value; is the estimand what we claim?
3. **Novelty / prior art** — PubMed/Embase sweep; does it map to a named index or an existing paper?
   Desk-reject risk. What is the irreducible novel contribution in one sentence?
4. **External validity** — does it replicate on a held-out SITE/cohort? Internal-only = not a finding.
5. **Reproduction** — an independent haiku agent re-derives every headline number from raw data.
6. **The "collapse" skeptic** — one agent whose job is to reduce the finding to "already known + an
   artifact." If it collapses, it collapses.
Decision rule: promote only if it survives every lens AND external validation. Log the full attack map.
Scale aggression to ambition: a Nature-Medicine claim gets 3–5 adversarial rounds + 3–5-vote adversarial
verification per sub-claim; a quick check gets one round. When in doubt, attack harder.

## Impact bar & novelty discipline (hard-won — enforce every cycle)
- **Require external/cross-site validation.** Internal-only + observational = incremental, not top-tier.
- **Avoid already-named indices** (VIS, VDI, BPRI, HPI, SVV/PVI, augmentation index, SOFA, APACHE, shock
  index) — reviewers desk-reject. Novelty must be a construct with no established literature.
- **Avoid confounded treatment-decision questions** (liberation order, dose→outcome): confounding-by-
  indication caps them at "sicker patients" absent a genuine natural experiment.
- A clinical DECISION or a genuinely novel BIOMARKER beats another risk marker.
- Run a PubMed/prior-art novelty pre-screen BEFORE investing compute.

## Model delegation policy (cost-conscious — default to the cheapest sufficient model)
- **haiku** — mechanical/checkable: data pulls, cohort sizing, number reproduction/verification, running
  pre-written scripts, format/leakage checks, literature-hit triage. Use liberally.
- **sonnet** — judgment: the hostile-review panel, causal/stats critique, novelty assessment, analysis
  design, failure analysis, abstract drafting.
- **opus (main loop)** — orchestration, synthesis, strategic decisions, final verdicts only.
- Rule: checkable → haiku; needs judgment → sonnet; deciding-what's-next / integrating → opus. Prefer
  parallel haiku/sonnet panels over serial opus work.

## Compute awareness — CPU ONLY for now; long OVERNIGHT runs are OK
- No GPU currently. Design every experiment to run on CPU, using overnight wall-clock when needed
  (launch as a background job with a watcher that re-invokes on completion; checkpoint to disk every N
  items so a reap loses at most one chunk).
- **This is enough for a real EEG-foundation-model result** via the frozen-encoder path:
  1. Overnight, precompute **frozen CBraMod per-window embeddings** for thousands of patients (~3.9 s /
     30 s window on CPU; ~1 patient / 10 s incl. download → ~3–4k patients per 10 h). Cache them.
  2. Train a **small attention / multiple-instance (MIL) head over the cached per-window embeddings** —
     this is tiny and CPU-fast, and it AVOIDS the frozen-mean-pool ceiling (LESSONS: mean-pool is
     amplitude-dominated / low-rank). Do NOT mean-pool; let the head attend over windows.
  3. Cross-SITE validate. This whole path is CPU-feasible overnight; encoder fine-tuning is the only
     GPU-only piece and is deferred.
- Use CPU freely for tabular ML, data engineering, red-team panels, and pipeline validation.

## Guardrails (never violate)
- **PHI / DUA:** HEEDB is credentialed. Raw PHI in scratchpad only; NEVER commit it (aggregate metrics
  only). Respect the DUA on where data may live. BDSP access: `env -u AWS_ACCESS_KEY_ID -u
  AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN` + `AWS_PROFILE=physionet`.
- **Scripts:** create with the Write tool, NOT shell heredocs (they silently fail here — LESSONS).
- **Commit hygiene:** `git config user.email noreply@anthropic.com`; required trailer; no model id in
  commits; commit+push every cycle.
- **Honesty:** report nulls and confounds faithfully; a hypothesis killed in the gate and logged is a win.

## How to launch (operator)
- `/goal <objective>` — set the thread's objective (Stop hook keeps the loop honest).
- `/loop <cycle prompt>` — self-paced, or `/loop 8h ...` for an overnight cadence. Cron for scheduled
  sweeps; GitHub PR-watch to keep analysis code green.
