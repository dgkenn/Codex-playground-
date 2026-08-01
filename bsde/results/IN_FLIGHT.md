# Tables currently being streamed, and the git flag that hides them

A feature table under extraction changes on every row, which makes the working tree permanently dirty for
the hours a stream takes. The flag below stops that:

    git update-index --assume-unchanged bsde/results/<table>.csv     # hide an in-flight table
    git update-index --no-assume-unchanged bsde/results/<table>.csv  # UNDO, before committing the result

**The flag is hidden state and that is its danger.** A file marked `--assume-unchanged` will not show in
`git status`, will not be staged by `git add -A`, and its completed contents can therefore be silently left
out of a commit. **Always clear the flag before committing a finished table**, and check with:

    git ls-files -v bsde/results/ | grep '^[a-z]'      # lower-case letter = assume-unchanged is SET

## Why the tables are committed at all, part-finished

This container's disk does not survive reclamation — it has already happened once mid-session, losing an
in-flight HBN stream and an uncommitted patch while every committed thing survived. Every extraction script
is resumable (`stream_features` reads what is present and fetches only the remainder), so a committed
part-finished table is a genuine checkpoint rather than clutter: the cost of losing it is the hours of
re-extraction, and the cost of committing it is a few hundred kilobytes.

## What is safe to read from a part-finished table

Nothing, without a row-count gate. Every experiment that consumes one of these refuses to report until its
own minimum is met, and says so in words that name the table rather than the candidate — see E15's
`GATE_MIN_ROWS`, which was added after a smoke test reported "GATE PASSED (100.0%)" from a single row.

## Currently in flight: `vitaldb_grid.s0-3.csv` (started 2026-07-30)

Four **case-sharded** streams of the VitalDB whole-case grid, 250 cases, ~6,679 windows total. They are
committed part-finished on purpose (see above): each is resumable, and the container's disk does not survive
reclamation.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_vitaldb_grid.py --n-cases 250 --case-shard $k --of 4 \
             --out bsde/results/vitaldb_grid.s$k.csv &
    done; wait
    python bsde/scripts/stream_vitaldb_grid.py --merge bsde/results/vitaldb_grid.csv \
           bsde/results/vitaldb_grid.seed.csv bsde/results/vitaldb_grid.s?.csv

`vitaldb_grid.seed.csv` is the first ~11 cases, streamed unsharded before sharding existed. Its rows are
valid and the merge de-duplicates on `recording_id`, so including it costs nothing and saves a re-fetch.

**E22 reads only the merged `vitaldb_grid.csv` and refuses to report below 1,500 rows**, so a partial merge
cannot be mistaken for a result.

## Currently in flight: `vitaldb_agents.csv` (started 2026-07-30)

The administered-dose join for E25 — MAC, inspired sevo/des, propofol Ce and remifentanil Ce, meaned over
the same 30 s windows the features used, keyed by `recording_id`. No EEG is re-read; this only adds columns
alongside `vitaldb_grid.csv`.

    python bsde/scripts/join_vitaldb_agents.py        # resumable: refetches only the cases not present

**E25 refuses to report below 240 joined CASES**, and that floor is on cases rather than rows for a reason
recorded in E25 itself: a row floor copied from E22 let it run at 60 of 250 cases and print a spurious gate
failure, because the join produces ~27 rows per case. A part-finished join therefore cannot be mistaken for
a result — but note that the stale `e25_challenge_a_dose.json` from that partial run WAS deleted rather than
committed, since a JSON on disk outlives the console output that would have explained it.

## Currently in flight: the eegmmidb tables and `vitaldb_fine.s0-3.csv` (2026-07-30)

Four extractions, all resumable, all committed part-finished per the convention above.

    bsde/results/vitaldb_fine.s0-3.csv      Challenge C's 60 s retest (E27). The plan was WIDENED after
                                            E27's first gate failure -- it now covers both SR thresholds'
                                            onsets per case, 94 cases / 3,595 windows -- so these shards
                                            are being extended, not rebuilt.
    bsde/results/eegmmidb_rest.csv          spontaneous features, baseline runs R01/R02 only (E28)
    bsde/results/eegmmidb_bci.csv           E28's LABEL: per-subject motor-imagery decoding AUC
    bsde/results/eegmmidb_bci_executed.csv  E28's PLACEBO: the same for EXECUTED movement

**E27 refuses below 75 joined cases and E28 below 60 subjects with both a resting row and a label**, so no
part-finished state here can be mistaken for a result. The eegmmidb label builders take roughly a minute per
subject and shard by subject (`--shard k --of n`), because their cost is the per-run HTTPS fetch.

### FLAG SET 2026-07-30 — clear it before reporting any of these

`--assume-unchanged` is currently SET on the seven tables listed above. It was set because four streams
write to them continuously, so `git status` reported the tree dirty every few seconds and each commit was
immediately stale. **The flag is hidden state and this heading exists so it is not forgotten.** Clear it and
verify before committing a finished table or reporting a result from one:

    for f in $(git ls-files -v bsde/results/ | grep '^[a-z]' | cut -d' ' -f2); do
        git update-index --no-assume-unchanged "$f"
    done
    git ls-files -v bsde/results/ | grep '^[a-z]'      # must print NOTHING when the flag is clear

## Currently in flight: `eegmmidb_trials.{imagery,executed}.s0-3.csv` (started 2026-07-31)

Eight subject-sharded streams caching the **per-trial** band powers behind E28's label — the vectors
`build_eegmmidb_bci_label.py` computed and threw away. Roughly 104 subjects x 2 tasks x 45 trials x 6
features, so a few hundred kilobytes in total and safe to commit part-finished.

    for t in imagery executed; do for k in 0 1 2 3; do
      python bsde/scripts/dump_eegmmidb_trials.py --task $t --shard $k --of 4 \
             --out bsde/results/eegmmidb_trials.$t.s$k.csv &
    done; done; wait

**E38 reads whatever shards exist and refuses below 60 subjects** at both G1 and the reliability estimator,
so a part-finished cache cannot be mistaken for a result. The dumper imports `_band_power`, `CHANNELS`,
`BANDS` and `EPOCH` from the label builder rather than reimplementing them, so the cache is the same
quantity the label was built from — and E38's G1 checks it against the stored per-subject AUC anyway.

**The flag is NOT set on these.** They are small and written once per subject rather than continuously, so
the `--assume-unchanged` dance that the VitalDB tables needed is not worth its hidden state here.

## Currently in flight: `eegmmidb_rest_v2.s0-3.csv` (started 2026-07-31)

Four recording-sharded streams re-extracting the eegmmidb **baseline** runs with the full 20-candidate
registry, which now includes `lrtc_alpha` and `icoh_alpha`. A **new path**, not an append: `stream_features`
rightly refuses to append to a table whose column set differs, and `eegmmidb_rest.csv` was written with 14.

    for k in 0 1 2 3; do
      python bsde/scripts/stream_eegmmidb_rest.py --shard $k --of 4 \
             --out bsde/results/eegmmidb_rest_v2.s$k.csv &
    done; wait

**E42 reads the shards directly and refuses below 60 subjects**, so a part-finished set cannot be mistaken
for a result. Committed part-finished on purpose — the container's disk does not survive reclamation, the
streams are resumable, and this table is a few tens of kilobytes.

**Task runs are never touched here.** The separation is the whole point: Challenge B's label is built from
the imagery runs, and this table must contain nothing from them or the association is circular.

## Currently in flight: `stieger_holdout_trials.s0-3.csv` and `eegmmidb_pretrial.s0-3.csv` (2026-08-01)

Two per-TRIAL tables for the Challenge B replications registered as E174 and E175. Both are committed
part-finished on purpose (see the top of this file): both extractors are resumable on their own key and
de-duplicate on load, so a second writer cannot corrupt a result (rule 56).

    # E174 -- Stieger sessions 2 and 3, HELD OUT from E172's session-1 cohort
    for k in 0 1 2 3; do
      python bsde/scripts/extract_stieger_trials.py --sessions-per-subject 3 --min-session 2 \
             --shard $k --of 4 --out bsde/results/stieger_holdout_trials.s$k.csv &
    done; wait

    # E175 -- eegmmidb per-trial pre-cue features, the external replication
    for k in 0 1 2 3; do
      python bsde/scripts/extract_eegmmidb_pretrial.py --shard $k --of 4 \
             --out bsde/results/eegmmidb_pretrial.s$k.csv &
    done; wait

**The filename prefix is load-bearing and is not cosmetic.** E172's loader globs `stieger_trials*.csv`;
the held-out shards are named `stieger_holdout_trials*` precisely so that they CANNOT be picked up by it,
and E174 asserts that no session-1 row reached its table. If either name changes, E172's recorded cohort
silently changes with it.

**E174 refuses below 60 held-out sessions and E175 below 60 subjects with >= 20 pairs**, so neither can
mistake a part-finished stream for a result. E175 additionally refuses if its decoder is at chance, because
"correctly decoded" would then be a coin flip (rule 53).
