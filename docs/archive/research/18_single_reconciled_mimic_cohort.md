# Single reconciled MIMIC-IV cohort — all racial endpoints on ONE extraction (resolves §2.5 heterogeneity)

**Status:** Rigor/consolidation win. All ionized-based racial endpoints re-run on a single, uniformly-defined
MIMIC extraction from the full labevents, resolving the manuscript's disclosed cross-extraction heterogeneity
(§2.5) for the racial claims. Reproduces the headline (false hypercalcemia) and honestly refines the
masked-hypocalcemia endpoint to non-significant in the reconciled, unadjusted cohort.

## Cohort (one extraction, uniform bounds)
Full MIMIC-IV labevents → ionized Ca (50808), total Ca (50893), albumin (50862) paired within 2h per patient;
race ∈ {Black, White} from admissions; bounds ionized 0.5–2.0 mmol/L, total 4–16 mg/dL, albumin 1–6 g/dL.
**N = 23,449 paired draws (Black 3,553 / White 19,896; 9,324 patients).** corrected Ca = total + 0.8×(4−albumin).

## Unified endpoint table (all on this one cohort)
| endpoint | metric | result | reproduces manuscript? |
|---|---|---|---|
| E1 raw bias | total Ca Black offset at matched ionized | **+0.182 mg/dL (z=+11.1)** | yes (primary +0.15, z=+11.6) |
| E1b corrected bias | corrected Ca Black offset at matched ionized | **+0.185 mg/dL (z=+11.7)** — bias PERSISTS | yes (primary +0.15, z=+7.3) |
| E2 false hyperCa | corr>10.5 given ionized<1.30, Black vs White | **13.5% vs 8.6%, OR 1.65 [1.47,1.85]** | yes (primary 13.3% vs 8.0%, OR 1.77) |
| E3 masked hypoCa | corr≥8.5 given ionized<1.15, Black vs White | **79.6% vs 78.0%, OR 1.10 [0.98,1.23] — NS** | refines (manuscript already hedged "attenuated") |

## Honest refinements
1. **The racial disparity is robustly an UPPER-threshold phenomenon** (false hypercalcemia, E2). On this single
   reconciled cohort the racial masked-hypocalcemia gap (E3) is directionally consistent (Black 79.6% > White
   78.0%, the +0.18 mg/dL offset pushing truly-low values above the flag) but **not statistically significant**
   (OR 1.10, CI includes 1). This is consistent with — and sharpens — the manuscript's existing hedge that the
   lower-threshold error was "attenuated." Recommendation: state plainly that the confirmatory racial endpoint is
   false hypercalcemia; masked hypocalcemia is a real *aggregate* problem but not a demonstrated racial disparity.
2. **The lower-threshold masking is severe in AGGREGATE, race-neutral:** ~78% of truly-hypocalcemic (ionized<1.15)
   patients of both races are NOT flagged low by corrected Ca (corrected≥8.5) — corrected Ca misses most true
   hypocalcemia. This is a strong general reliability point (pairs with the "63% of high-Ca flags are false"
   result, doc/§3e), distinct from the racial claim.

## Manuscript impact (applied)
- Add a reconciled-cohort paragraph to §2.5 / §3e: all racial endpoints hold on ONE uniformly-extracted MIMIC
  cohort (N=23,449), so the cross-extraction heterogeneity is a provenance/disclosure matter, not a result-
  stability one — E1/E1b/E2 reproduce within noise on the unified cohort.
- Temper the masked-hypocalcemia racial framing (Abstract + §3b) to "present in aggregate but not a significant
  racial disparity in the reconciled cohort," keeping false hypercalcemia as the confirmatory racial endpoint.
- Provenance-tracked primary numbers (25,163 / 103,655) retained; the reconciled cohort is added as the
  rigor/consolidation check, not a replacement.

## Robustness — one-per-patient (cluster-safe)
Collapsing to one paired draw per patient (9,324 patients: 1,353 Black / 7,971 White), the false-hypercalcemia
disparity is unchanged: **OR 1.65 [1.26, 2.15]** (Black 6.0% vs White 3.7%), matching the draw-level OR 1.65 —
the reconciled-cohort headline is not an artifact of within-patient repeat draws.

## Files
- Analysis inline (reproducible from `scratchpad/ca_glob_full.csv` + `admissions.csv.gz`).
