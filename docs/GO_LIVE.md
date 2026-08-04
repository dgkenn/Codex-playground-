# Go-live checklist — HEEDB/BDSP pilot in Claude Code on the web

DUA cleared. Remaining steps are environment configuration; they take effect in a
**new session** (env vars, network access, and the setup script are not applied
to an already-running session).

## You configure (claude.ai/code → Configure environment)
1. **Setup script** field ← paste `scripts/setup_cloud.sh`.
2. **Environment variables** field ← paste `docs/go-live.env.template`, filled
   with **short-lived, read-only STS** keys registered with BDSP. (No secrets
   store exists; these are visible to environment editors — rotate after.)
3. **Network access → Custom** (keep defaults) and add:
   ```
   *.s3.amazonaws.com
   s3.us-east-1.amazonaws.com
   *.s3-accesspoint.us-east-1.amazonaws.com
   sts.amazonaws.com
   ```
4. Confirm the **catalog** location in `config.yaml::data.s3` (`catalog_key`,
   `catalog_format`, `catalog_columns`) against the real bucket — or tell me to
   discover it.
5. **Start a new session** and say "go".

## I run (in the new session)
```bash
python cli.py preflight          # deps + AWS identity + S3 reach + catalog + checkpoint
# (I pin model.checkpoint_sha256 by downloading CBraMod and hashing it)
python cli.py validate
python cli.py pass1 --limit 500  # PILOT: 500 recordings, resumable
python cli.py phase1 --tables artifacts
#   -> review artifacts/phase1_report.json (site gate, phenotype bar, neg control)
# Pin phase2.primary_phenotype from the report; register on OSF; then:
python cli.py freeze
# (set phase: 2; build held-out tables + outcome.json) then:
python cli.py phase2 --tables artifacts_heldout/ --outcome outcome.json
```

`preflight` must print **READY** before `pass1`. Scale past the 500-recording
pilot only on durable compute (this environment is ephemeral) — see
`docs/RUNBOOK.md`. TUH external replication cannot run in this HTTP/HTTPS-only
sandbox; run it in your own environment.
