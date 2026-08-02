# Challenge C feasibility: the cached grid cannot answer a timing question

*2026-08-02, run before any registration (rule 41).*

**Challenge C, verbatim:** *"seeing a transition before the conventional monitor."* The comparator is BIS,
which VitalDB records. The three prior verdicts (E26, E34, E37) used SEF95, a computed proxy, so the
briefed question has never been asked. The obvious move was to ask it on `vitaldb_grid`, which carries
both the candidate panel and `meta_bis`.

**It cannot be asked there.** Measured over all 250 cases:

| quantity | value |
|---|---|
| median window spacing within a case | **300 s** (IQR 300–600) |
| windows within ±10 min of anaesthesia start, per case | **median 0** |
| cases with ≥5 windows in that interval | **0 of 250** |
| BIS coverage per case | 0.895 (fine) |

`vitaldb_grid` samples the MAINTENANCE phase on a five-minute grid. It contains essentially no windows
around induction or emergence, which is where the transitions are. **BIS's reported lag is in the tens of
seconds; a 300 s sampling interval cannot resolve who detected a transition first**, and no amount of
analysis on this table fixes that. The failure is one of extraction design, not of the deposit — VitalDB
has the raw waveform and `meta_anestart_s` / `meta_aneend_s` for every case.

**What Challenge C actually needs**, and it is a single S3 pass rather than a new dataset:

* windows at ~10 s spacing (or finer), spanning roughly ±10 min around anaesthesia start AND end;
* BIS at its native recording rate over the same interval, not subsampled onto the feature grid;
* both transitions, because loss and recovery are not each other's reverse.

**Not launched yet, deliberately.** The extraction is expensive and the abstract-first rule says the
literature verdict comes first: if a raw spectral measure is already known to lead BIS, the line stops and
the pass is wasted. That check is running. **This probe cost minutes and would have been the right thing
to run before any of E26, E34 or E37** — all three settled for the comparator their extraction happened
to contain.
