# Retention Log

Automated rows appended by .github/workflows/archive.yml. Each row is one archive-and-prune run: day-dirs older than RETENTION_DAYS (14) moved from a hot git branch into a GitHub Release asset (verified byte-for-byte before any deletion), then pruned from the branch.

| run_date (UTC) | branch | days_archived | bytes_freed | release_tag(s) | status |
|---|---|---|---|---|---|
