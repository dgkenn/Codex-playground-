# E76 first evaluation: G5 refused on 26 recordings, and what was seen before the extraction was extended

*Written 2026-07-31 immediately after the first evaluation and before the extended extraction returned, so
the record is contemporaneous rather than reconstructed.*

The registered coverage gate G5 requires **>= 30 recordings**. The first evaluation had **26** and
therefore printed `MACHINERY GATE FAILED` and refused to evaluate either co-primary — which is the
registered behaviour and rule 31's (a downstream verdict whose precondition failed is ABSENT, not
negative).

**Why 26 and not the 39 the prior pass has.** Both extractors select `[:n_recordings]` from the same
ordered pool. `extract_dosei_pe.py` accumulated its 39 across runs that reached recording `10-091`;
`extract_dosei_pe_variants.py` was launched once with `--n-recordings 40`, which stops at `10-060`, and
**14 of those 40 are refused by the shared non-uniform-time-axis rule** (`10-006, 10-011, 10-030, 10-035,
10-038, 10-041, 10-043, 10-047, 10-048, 10-053, 10-055, 10-057, 10-058, 10-060`). 40 − 14 = 26. The refusal
rule is byte-identical in the two scripts and the 26 recordings obtained are a strict subset of the prior
pass's 39, with no recording present here and absent there.

**So the shortfall is my launch argument, not the design.** The extraction was relaunched with
`--n-recordings 70` to reach the same pool. It is resumable and re-fetches nothing. **No registered
threshold, cohort, contrast or gate changed** — G5's floor of 30 is exactly as registered.

**What had been seen when that relaunch was decided.** All of it, and it is recorded here because the
descriptive table pointed the same way the primary is predicted to:

| arm | median rho vs PE31 | median rho vs MOAA/S |
|---|---|---|
| `pe_raw` | +0.7522 | +0.4433 |
| `pe_band` | +0.8349 | +0.5272 |
| `pe_tie` | +0.7603 | +0.4442 |
| **`pe_declared`** | **+0.8384** | **+0.5305** |
| `pe_placebo20` (wrong band) | +0.3919 | +0.2646 |
| the deposit's own PE31 | — | +0.5206 |

Machinery gates G2 (tie active, median tie fraction 0.1652), G3 (band active, median relative delta
0.2046) and G4 (self-check: 7,795 shared rows, max |diff| **0**) all passed on this partial table.

A reader who thinks extending an extraction after seeing that table is fishing has the information needed
to say so. The counter-argument is on the record too: G4 exists precisely to compare against the prior
pass's rows, so covering the prior pass's recordings was the design's intent before any number existed, and
the gate that refused is the one that caught the shortfall.
