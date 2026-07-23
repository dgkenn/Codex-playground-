# Gate Step 2 — Code Custody Report

**Date:** July 23, 2026. Research: web sweep of papers, journal records, arXiv ancillary files, Zenodo, institutional repositories, the Polymath wiki, and library documentation (GitHub itself out of session scope). Status: **Step 2 is partially discharged** — custody routes mapped, substrate secured and working locally; original-code custody requires author contact (which is also Gate Step 6's courtesy contact).

## 1. Platt–Trudgian verification code

**Not published anywhere findable** — no arXiv ancillary files, no journal supplement, no Zenodo DOI, no institutional code repository, and the Bull. LMS paper has no code/data availability statement. What *is* published is the output data of the 2017 computation: ~103.8 billion zero ordinates (1.3 TB), stored via Bober in LMFDB, with the 2017 paper explicitly inviting researchers to contact the author for copies.

**Contact route:** Dave Platt, dave.platt@bris.ac.uk (arXiv header; Bristol profile "Honorary Research Associate", School of Mathematics; Heilbronn-affiliated). Homepage: people.maths.bris.ac.uk/~madjp. PhD supervisor and algorithm progenitor: Andrew Booker (the 2017 algorithm is a windowed specialization of Booker's rigorous L-function algorithm).

**Reconstruction assessment: moderate-high difficulty, tractable.** The 2017 Math. Comp. paper (86, 2449–2467) is unusually explicit: the Gaussian-windowed completed-zeta function f(t) = Λ(t+t₀)·exp(π(t+t₀)/4 − t²/2h²); an 8-step procedure with two DFT passes and Taylor-expansion convolutions (Lemmas 3.2–3.3); rigorous error bounds in Appendices A–C; Turing-method completeness via |∫S| ≤ 2.067 + 0.059 log t₂ (Trudgian's constants); Whittaker–Shannon upsampling with a Weiss-type error bound; and the actual tuned parameters (300-bit precision, h = 176431/2048, J = 104000, K = 44, N = 2¹⁵ upsampled to 2²⁰). The 2020 rewrite swapped MPFI → Arb and dropped fine zero isolation. No third-party reimplementation exists — reconstructing it is itself roadmap target territory (adjacent to T3).

## 2. dbn_upper_bound (Polymath15)

**Primary home is the GitHub repo (out of session scope); no Zenodo mirror found; Software Heritage status unconfirmed** (anti-bot blocks — a human should check archive.softwareheritage.org directly). The Polymath wiki (michaelnielsen.org/polymath1, "De Bruijn-Newman constant" page) documents the repo layout: Pari/GP, Arb, and Julia implementations, "Arb scripts recommended for large scale runs," plus a Julia port `DBNUpperBound.jl`.

**Contact routes:** Terence Tao (Polymath15 organizer; the ~10 numbered blog threads at terrytao.wordpress.com narrate the barrier computations); numerics contributors Rudolph Dwars and Kalpesh Muchhal (the "km" of `km-git-acc`, inferred from initials + co-authored numerics updates on Tao's tenth thread — tentative, unconfirmed); Julia port by "WilCrofter" (Bill Bauer).

**Reconstruction assessment: higher difficulty than item 1** — the mathematics is in the paper but the implementation knowledge (barrier placement heuristics, stored-sums caching) is scattered across wiki + blog threads + repo discussions with no single canonical spec. This is exactly the Gap-B risk in `PROPOSAL.md` §3, now with named contacts.

**To obtain the repos in-session:** ask to add `km-git-acc/dbn_upper_bound` (and `flintlib/flint` if needed) — repository access must be explicitly granted by the user.

## 3. Substrate (Arb / FLINT / python-flint) — SECURED

Arb is merged into FLINT as of 3.0.0 (Oct 2023); current stable FLINT 3.6.0 (June 2026); LGPL v3+; build deps GMP ≥ 6.2.1, MPFR ≥ 4.1.0. Python bindings: python-flint 0.9.0 (July 2026), wheels for Linux/macOS/Windows, exposing `acb` ball arithmetic and, critically, `dirichlet_char.hardy_z()` — native rigorous Hardy Z. **Installed and validated in this environment**: native `hardy_z` agrees ball-for-ball with an independently constructed e^{iθ(t)}ζ(½+it) at test points (see `verification/rs_verify.py`, which keeps both paths for cross-validation). Consequence for the project: no low-level ball-arithmetic zeta machinery needs reconstructing — only the windowing/FFT orchestration, zero-isolation bookkeeping, and Turing accounting layers.

## Follow-ups

1. Email Platt (merges Step 2 custody with Step 6 courtesy contact) — request code or blessing for reconstruction, and ask whether an extension is already running (Step 0).
2. Human check of Software Heritage for both repos.
3. User-authorized `add_repo` of `km-git-acc/dbn_upper_bound` for direct code audit (Gap B).
4. Extract the Polymath15 paper's acknowledgments verbatim to formally identify code contributors (PDF parse failed once; retry with page-range reads).
