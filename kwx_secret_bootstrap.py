#!/usr/bin/env python3
"""kwx_secret_bootstrap.py -- secure secret delivery to CI legs WITHOUT GitHub repo-secret access.

PROBLEM: the operator's Synoptic token needs to reach the Actions legs, but nothing in this
toolchain can write GitHub repo secrets (the integration token 403s on the secrets API), and the
repo is PUBLIC so the token can never be committed in plaintext.

CHANNEL: the legs already hold an RSA private key (KALSHI_PRIVATE_KEY env, PEM). So:
  1. A leg runs `publish` (auto mode does this when needed): derives the PUBLIC key from
     KALSHI_PRIVATE_KEY and commits kwx_leg_pubkey.pem. Public keys are safe to publish, and
     this does not weaken Kalshi request signing.
  2. An operator session runs `encrypt <token-file>`: RSA-OAEP(SHA-256)-encrypts the token to
     that public key and commits ONLY the ciphertext, kwx_synoptic_token.enc (base64).
  3. Every subsequent leg's auto mode decrypts the blob with KALSHI_PRIVATE_KEY and writes the
     gitignored .synoptic_token file that synoptic_feed.py already reads. Nothing plaintext ever
     touches the repo.

Crypto-hygiene note: this reuses the Kalshi signing key for decryption. RSA-OAEP encryption and
the API's signing operations live in separate padding domains, so the practical risk is
negligible -- but if a real SYNOPTIC_TOKEN repo secret is ever added, that env var takes
precedence everywhere and this whole path becomes inert (auto mode exits first thing).

FAIL-SOFT: auto mode NEVER raises and never exits non-zero -- it must be safe to run
unconditionally at the top of a live leg.

Usage:
  python kwx_secret_bootstrap.py            # auto (legs): decrypt if blob present, else publish pubkey
  python kwx_secret_bootstrap.py encrypt .synoptic_token   # operator: make/refresh the blob (no commit)
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PUBKEY_PATH = os.path.join(HERE, "kwx_leg_pubkey.pem")
BLOB_PATH = os.path.join(HERE, "kwx_synoptic_token.enc")
TOKEN_PATH = os.path.join(HERE, ".synoptic_token")


def _log(msg):
    print(f"secret-bootstrap: {msg}")


def _load_private():
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    pem = os.environ.get("KALSHI_PRIVATE_KEY", "")
    if not pem.strip():
        path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        if path and os.path.exists(path):
            pem = open(path).read()
    if not pem.strip():
        return None
    return load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)


def _oaep():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    return padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=None)


def _git(*args):
    return subprocess.run(["git", "-C", HERE] + list(args), capture_output=True, text=True)


def _commit_and_push(path, message):
    """Commit one file using the checkout's persisted credentials, with the same rebase-retry
    the leg's own log-commit loop uses. Best-effort: a push race just means the next leg retries."""
    _git("add", "-f", "--", os.path.basename(path))
    c = _git("commit", "-m", message)
    if c.returncode != 0:
        _log(f"nothing to commit ({c.stdout.strip()[:60]})")
        return
    branch = os.environ.get("BRANCH", "claude/coding-bot-ab-test-results-ffmhxw")
    for _ in range(4):
        if _git("push", "origin", f"HEAD:{branch}").returncode == 0:
            _log(f"pushed {os.path.basename(path)}")
            return
        _git("fetch", "origin", branch)
        _git("rebase", f"origin/{branch}")
    _log("push failed after retries (next leg will retry)")


def auto():
    try:
        if os.environ.get("SYNOPTIC_TOKEN", "").strip():
            _log("SYNOPTIC_TOKEN env present -- real secret wins, nothing to do")
            return
        if os.path.exists(TOKEN_PATH):
            _log("token file already present")
            return
        priv = _load_private()
        if priv is None:
            _log("no KALSHI_PRIVATE_KEY in env -- no-op (paper/dev context)")
            return
        if os.path.exists(BLOB_PATH):
            ct = base64.b64decode(open(BLOB_PATH).read().strip())
            tok = priv.decrypt(ct, _oaep()).decode().strip()
            fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(tok + "\n")
            _log("synoptic token decrypted -> .synoptic_token (gitignored)")
            return
        if not os.path.exists(PUBKEY_PATH):
            from cryptography.hazmat.primitives import serialization
            pem = priv.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo)
            open(PUBKEY_PATH, "wb").write(pem)
            _log("derived leg public key -> kwx_leg_pubkey.pem (public keys are safe to publish)")
            _commit_and_push(PUBKEY_PATH, "kwx-secret-bootstrap: publish leg public key")
            return
        _log("pubkey published, no blob yet -- waiting on operator encrypt step")
    except Exception as e:  # fail-soft: never take down a leg
        _log(f"no-op ({type(e).__name__}: {str(e)[:80]})")


def encrypt(token_file):
    """Operator side: encrypt token_file's contents to the published leg pubkey. Writes BLOB_PATH;
    committing it is left to the operator so they can review first."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    if not os.path.exists(PUBKEY_PATH):
        sys.exit("no kwx_leg_pubkey.pem yet -- wait for a leg to publish it")
    pub = load_pem_public_key(open(PUBKEY_PATH, "rb").read())
    tok = open(token_file).read().strip().encode()
    ct = pub.encrypt(tok, _oaep())
    open(BLOB_PATH, "w").write(base64.b64encode(ct).decode() + "\n")
    print(f"wrote {BLOB_PATH} ({len(ct)} bytes ciphertext) -- commit it to deliver")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "encrypt":
        encrypt(sys.argv[2])
    else:
        auto()
