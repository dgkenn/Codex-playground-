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
