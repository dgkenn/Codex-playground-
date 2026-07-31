# E78 first evaluation: G2 refused on 15 recordings, and what was seen before the extraction was extended

*Written immediately after the first evaluation and before the extended extraction returned, so the record
is contemporaneous. Same shape as `e76_first_pass_note.md`, and for the same reason.*

The registered coverage gate G2 requires **>= 20 usable recordings**. The first evaluation had **15** and
printed `GATE FAILED`, refusing to evaluate the primary — the registered behaviour, and rule 31's.

**Why 15.** The held-out pool is **128 recordings** (171 pEEG tables minus the 43 this project has already
used). The extractor was launched with `--n-recordings 60`, and most of that first 60 fail the shared
non-uniform-time-axis rule — the same rule, unchanged, that removed 14 of 40 in E76's pass. 4,109 windows
survived across 15 recordings. **The pool was always 128; only the launch argument was 60.** The extraction
was relaunched to cover more of it. **No registered threshold, cohort, contrast, gate or held-out
definition changed** — G1 (zero overlap with the used 43) passed and stays exactly as registered, and every
additional recording is drawn from the same pre-declared held-out pool.

**What had been seen when that relaunch was decided.** All of it:

| measure | median within-recording ρ vs MOAA/S, 15 held-out recordings |
|---|---|
| `pe_declared` (E76's corrected recipe) | **+0.5738** |
| `bis_rbr` | **+0.5291** |
| *the deposit's own* `PE31` | *+0.4925* |
| *the deposit's own* `SEF95` | *+0.1947* |

G1 passed (0 overlapping recordings), G3 dropped nothing for a constant measure, G4 passed (tie fraction
0.1696, band relative delta 0.1852).

**Two things a reader should weigh.** First, this table points toward the PE-BETTER branch, which is the
branch *against* Q35's amendment and is not the direction the registration predicted (it predicted D
includes zero) — so the extension is not being run in the direction of a hoped-for result. Second, and
more reassuring than either candidate's rank: on 15 recordings that share not one recording with the
partition Q35 used, **`bis_rbr` lands at +0.5291 against Q35's +0.5258, and the deposit's `PE31` at +0.4925
against Q36's +0.4944.** Both replicate to within 0.004. Whatever the primary turns out to be, the
measurements themselves are stable across disjoint halves of the deposit.
