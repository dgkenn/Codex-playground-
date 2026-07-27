# Credentials — how to make them durable across Claude sessions

*The short version: set them once in the **Claude Code web environment's environment-variable settings**, and
`scripts/bdsp_bootstrap.sh` materializes them at the start of every session. **Never commit a credential to
this repository.***

---

## Why this is needed

Containers are ephemeral. Anything written to `~/.aws` or `~/.ssh` can vanish when a container is reclaimed,
and a new session then reports "no access" for what is really a missing file. The **environment** — not the
session, and not the container — is the durable layer: variables set there are re-injected into every new
session, including sessions driven by a different Claude.

## What to set

In the Claude Code web environment settings, under environment variables:

| variable | value | grants |
|---|---|---|
| `BDSP_AWS_ACCESS_KEY_ID` | `AKIA…` | HEEDB, I-CARE, MORGOTH label sets (all on S3 access points) |
| `BDSP_AWS_SECRET_ACCESS_KEY` | the 40-character secret | ” |
| `NEDC_SSH_KEY_B64` | base64 of the NEDC-registered private key | TUH transport — **optional, see the scope warning below** |
| `NEDC_SSH_USER` | `nedc-tuh-eeg` | optional; this is the default |

Produce the base64 on your own machine:

```bash
base64 -w0 ~/.ssh/id_ed25519            # Linux
base64 -i ~/.ssh/id_ed25519 | tr -d '\n'  # macOS
```

Base64 is required because environment variables do not carry multi-line values reliably.

## Why the AWS variables have non-standard names

The container ships `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as 14-character **agent-proxy
placeholders**. boto3 puts environment variables *ahead of* profiles in its resolution chain, so real
credentials stored under those names get shadowed and every call returns 403 — which reads exactly like an
expired key and is not. `BDSP_AWS_*` avoids the collision entirely.

**This is why every analysis must run through the wrapper:**

```bash
scripts/heedb_run.sh python analysis/<script>.py
```

It unsets the two placeholders for the child process and leaves `AWS_CA_BUNDLE`/`HTTPS_PROXY` alone.

## What the bootstrap does

`scripts/bdsp_bootstrap.sh` runs as a `SessionStart` hook (wired in `.claude/settings.json`). It:

1. Writes `~/.aws/credentials` (profiles `default` and `physionet`) and `~/.aws/config`, mode 600.
2. **Probes the BDSP access point** and reports whether the credential actually works.
3. If `BDSP_AWS_*` is absent, **probes the existing `~/.aws/credentials` before declaring failure** — a
   surviving file from an earlier session is often still valid. Announcing "unavailable" without probing cost
   a full session's work once.
4. Materializes `~/.ssh/id_ed25519` from `NEDC_SSH_KEY_B64` if present, verifies it decodes to a private key,
   and reports whether `rsync`/`ssh` exist in the container.
5. **Never prints a secret** — only presence and whether it works.

It exits 0 in every path: missing credentials are non-fatal, because cached-data and VitalDB work continue.

---

## TUH: access approved 2026-07-27, and what that does and does not unlock

The NEDC application was **approved**. The registered key is
`SHA256:rBwGl4h45Em0QYRxAKdF/P3ResO2nk3SZkdeUtHT9Qw` (ed25519, comment `dgkenn@bu.edu`). The **private** half
must never leave the user's own machine and must never be pasted into a session; only
`NEDC_SSH_KEY_B64` in the environment settings, which the bootstrap materializes.

**TUH CANNOT BE PULLED FROM THE CLOUD SANDBOX. This was measured, not assumed:**

| check | result |
|---|---|
| `rsync` / `ssh` binaries | **absent**, and `apt-get` 404s on the Ubuntu mirrors from here |
| `paramiko` (pure-Python SSH, an rsync alternative) | installs fine — so the missing binaries are *not* the blocker |
| TCP to `www.isip.piconepress.com:22` | **BLOCKED — connection times out** |
| TCP to `www.isip.piconepress.com:443` | open |

The environment's network policy permits HTTPS and not SSH, so **no SSH client of any kind can reach NEDC
from here.** TUH transport must run from a machine with unrestricted outbound network — the user's own
desktop — or the environment's network policy must be changed when the environment is created.

## Scope warning on TUH: access does not change what TUH can answer

**The TUH EEG Corpus carries no linked outcome data.** Its manifest schema — in this repository's own
`config.yaml` — is `recording_id, patient_id, edf_path, sfreq, age, sex`. There is no outcome field and no
diagnosis field.

Consequences, established in the ledger at **R321** and easy to forget:

- **No outcome association can be replicated on TUH at any effort.** That includes the burden→mortality
  finding and the aetiology reversal (R389–R396), which additionally needs a diagnosis TUH does not carry.
- TUH can validate a **measurement** — a quantitative feature against a clinician label at a different health
  system. That is a real but lesser claim.
- **Approval does not change any of this.** The constraint is the dataset's contents, not permission to read
  it. What TUH *can* do is validate a **measurement** — e.g. our quantitative suppression burden or slowing
  measure against a clinician label recorded at a different health system. That is a genuine, publishable
  but lesser claim, and it is the right use of the access.
- Once connected from a capable host, **enumerate the corpus before planning** rather than assuming which
  sub-corpora exist and what labels they carry.

## Access points currently in use

| dataset | access point | prefix |
|---|---|---|
| HEEDB clinical | `arn:aws:s3:us-east-1:184438910517:accesspoint/bdsp-credentialed-access-point` | `EEG/HEEDB_Metadata/` |
| I-CARE | `…/bdsp-restricted-access-point` | `ICARE_train/training/` |
| MORGOTH label sets | `…/bdsp-credentialed-projects-ap` | `morgoth1/data/internal_dataset/` |

AWS profile: `physionet` (identical to `default`; both are written by the bootstrap).

## If access breaks

Diagnose **per credential source**, not globally — catalogue rule 8:

```bash
scripts/heedb_run.sh python -c "import boto3; print(boto3.Session(profile_name='physionet').client('sts').get_caller_identity()['Arn'])"
```

A 403 with the wrapper is a real credential problem. A 403 *without* it is almost always the placeholder
collision described above.
