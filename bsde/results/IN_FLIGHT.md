# Streams in flight — and a local git flag you must undo

Two feature tables were being written when this note was committed. They grow a row every few seconds with
an fsync each, which means the working tree goes dirty again between `git add` and `git status` and can never
be left clean while the streams run.

| table | experiment | target |
|---|---|---|
| `sleep_edfx_five_stage.csv` | E13 (REM position) | 710 windows, 142 recordings x 5 stages |
| `ds005620_tms.csv` | E15 (50-90 Hz band) | 55 recordings, acq=tms stratum |

To stop that churn, both paths were marked locally with:

```
git update-index --assume-unchanged bsde/results/sleep_edfx_five_stage.csv bsde/results/ds005620_tms.csv
```

**THIS IS A LOCAL FLAG, IT IS INVISIBLE IN THE DIFF, AND IT WILL SILENTLY DISCARD NEW ROWS IF YOU FORGET IT.**
Undo it before committing either table again:

```
git update-index --no-assume-unchanged bsde/results/sleep_edfx_five_stage.csv bsde/results/ds005620_tms.csv
git add bsde/results/ && git commit
```

Check whether it is still set with `git ls-files -v bsde/results/ | grep '^[a-z]'` — lowercase status letters
mark assume-unchanged files.

The committed version of each table is a valid partial checkpoint, consistent with the policy in
`.gitignore` here: partial tables are committed deliberately because incompleteness is machine-checkable from
the manifest sidecar and the row count, whereas a table destroyed by a container rollback cannot be read at
all. The flag risks only the rows added after the last checkpoint, not the table.

Delete this file once both streams have completed and their tables are committed in full.
