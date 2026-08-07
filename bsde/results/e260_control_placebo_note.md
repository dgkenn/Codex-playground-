# E260 — the control-window placebo. P2 is vindicated; **the E250/E261 "corner" is not.**

*2026-08-07. 750 cases balanced across arms, 21 windows on the same grid centred 2,400 s before recovery,
≥ 900 s clear of both real landmarks and inside the anaesthetic. Extracted 15,747 windows, 15,547 `ok`,
**zero duplicate `recording_id`s**, 740 cases with ≥ 15 usable windows.*

---

## 1. P2 IS landmark-specific. E249's G1 stands, and E252's apparent failure was the artefact I diagnosed.

Splitting the control windows at their own centre — a place where nothing happens — gives:

| candidate | real P2 | **control P2** | ratio |
|---|---|---|---|
| `whole_head_exponent` | −0.3629 | **+0.0043** | −0.012 |
| `exponent_high` | −0.3587 | **+0.0036** | −0.010 |
| `emg_beta_gamma_fraction` | +0.3386 | **−0.0066** | −0.020 |
| `spectral_edge_95` | +0.3260 | **−0.0080** | −0.025 |
| `multiscale_entropy_slope` | −0.3161 | **+0.0084** | −0.027 |
| `relative_alpha_power` | −0.2287 | **+0.0093** | −0.041 |

**Every candidate collapses to within ±0.012 of zero.** The state tracking E249 measured is a property of
the ventilation landmark, not a within-case time trend.

E252 reported the placebo reproducing 89 % of P2 and I said it was uninformative by construction, because
the peri-landmark table spans only ±300 s and no fake landmark inside it can be far from the real one.
**That diagnosis was right, and this is the measurement that proves it.** The fix was a data-shape fix, it
cost 28 minutes of fetching, and it converts an untestable claim into a settled one.

## 2. AND THE PART THAT REVERSES LAST TURN'S HEADLINE

The same windows answer a second question nobody had asked: **is agent identity present away from the
transition?** It is — and for several measures it is *much larger* there.

| pair | candidate | **control** | peri-landmark |
|---|---|---|---|
| sevo vs ppf | `whole_head_exponent` | **0.3525** | 0.0668 |
| des vs ppf | `whole_head_exponent` | **0.3788** | 0.0635 |
| sevo vs des | `whole_head_exponent` | **0.1027** | 0.0023 |
| sevo vs ppf | `relative_alpha_power` | **0.2212** | 0.0015 |
| des vs ppf | `alpha_peak_hz` | **0.3545** | 0.2922 |
| sevo vs ppf | `relative_theta_power` | **0.2951** | 0.1798 |

**`whole_head_exponent` — the headline member of E250's low-leakage / high-tracking corner — is one of
the leakiest measures in the panel when leakage is measured during maintenance.** Its peri-landmark
leakage of 0.06 becomes **0.35–0.38** at steady state, a five- to six-fold increase.

### What this does to E261

E261 tested the corner against an exhaustive 11,628-subset null and got p = 0.0003. **That test is
arithmetically correct and its input was the wrong quantity.** It used E248's peri-landmark leakage, and
peri-landmark is precisely where the drug signature is weakest — the patient is emerging, the agent is
washing out, and the between-arm difference goes with it.

**So the corner is substantially an artefact of *where* leakage was measured, not a property of the
measures.** I reported it last turn as "the strongest result across both batteries" and as Challenge A's
shape. That was wrong, and this is the correction.

### The mechanism is not exotic and it generalises

Leakage scales with how much drug effect is present. Measured at emergence it is small; measured at
maintenance it is large. This is consistent with everything else in the two batteries and now explains
them: **E254** (leakage lives in the level, not the change), **E255** (pre-landmark leakage generally
exceeds post-landmark, only 0.28 of comparisons within 30 %), and now E260b as the extreme case.

**The reusable statement: a leakage value is meaningless without the state it was measured in.** A
representation that looks agent-invariant at one depth can be highly agent-identifying at another, and
Challenge A's minimisation criterion therefore has to be evaluated across the depth range, not at a
convenient landmark. Nothing in E248, E249, E250 or E261 did that.

## 3. What survives, precisely

* **E249's G1 and P2 — fully vindicated.** The state axis is real and landmark-specific.
* **E251/E262/E269 — untouched.** BIS's leakage, its reducibility to our panel, and its rank were all
  measured peri-landmark, but so were the candidates it is compared against. The *comparison* is
  internally consistent; its absolute level is now known to be an underestimate for everything involved.
* **E250's Spearman and E261's corner — withdrawn as evidence for a low-leakage/high-tracking family.**
  The dissociation may still exist; it has not been tested with leakage measured where the drug is acting.
* **E264, E265, E268** (suppression, SQI, case mix) — unaffected, all peri-landmark internal contrasts.

## 4. What a successor owes

1. **Re-run the dissociation with control-window leakage** against peri-landmark state tracking. The data
   now exists for 740 cases; this is a one-pass analysis, not an extraction.
2. **Extract control windows at two or more depths** and measure the leakage-versus-depth curve per
   candidate. That is the quantity Challenge A actually needs and no one has it.
3. **Never quote a leakage number without the state it was measured in** — add it to the ledger's
   registration fields if leakage is going to keep being reported.
