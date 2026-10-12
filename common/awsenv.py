"""Drop the container's placeholder AWS_* environment credentials so the real profile is reachable.

WHY THIS FILE EXISTS. The sandbox exports `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` for the outbound
agent proxy. They are not AWS credentials — the key id is 14 characters and begins `prox` — but boto3's
resolution chain checks the environment BEFORE `~/.aws/credentials`, so they shadow the real BDSP keys and
every S3 call fails with `InvalidAccessKeyId`. That reads exactly like credential expiry and has now cost
this project time twice (error catalogue rule 8, and again on 2026-07-28).

WHY IT IS NOT FIXED IN THE SHELL. `~/.bashrc` is only sourced for INTERACTIVE shells; the shells that run
these scripts are non-interactive, so an `unset` there silently does nothing. It was tried and did not work.

WHAT THIS DOES, AND WHAT IT REFUSES TO DO. It removes the ambient AWS_* variables only when ALL of:
  * a shared credentials file exists (so there is something to fall back to), and
  * the ambient key id does NOT look like an AWS key id — real ones are 20 characters and start AKIA/ASIA.
A plausibly-real key is therefore never touched, and the fallback is never to "no credentials". If you
genuinely want to pass real credentials under the standard names, this leaves them alone. The project's
durable answer remains BDSP_AWS_* in the environment settings (see docs/CREDENTIALS.md).

Import it for its side effect, before the first boto3 client is built:

    from common.awsenv import sanitize; sanitize()

It is idempotent and safe to call repeatedly.
"""
import os
import sys

_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
_done = False


def looks_like_aws_key(k):
    """AWS access key ids are 20 uppercase alphanumerics beginning AKIA (long-lived) or ASIA (session)."""
    return len(k) == 20 and k[:4] in ("AKIA", "ASIA") and k.isalnum() and k.isupper()


def sanitize(verbose=True):
    """Remove shadowing non-AWS placeholders from os.environ. Returns True if anything was removed."""
    global _done
    if _done:
        return False
    _done = True
    key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    if not key or looks_like_aws_key(key):
        return False
    shared = os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or os.path.expanduser("~/.aws/credentials")
    if not os.path.exists(shared):
        # Removing them here would leave nothing at all, which is worse than a clear failure.
        if verbose:
            print(f"[awsenv] ambient AWS_ACCESS_KEY_ID is not an AWS key id and {shared} does not exist; "
                  f"leaving the environment alone.", file=sys.stderr)
        return False
    for v in _VARS:
        os.environ.pop(v, None)
    if verbose:
        print(f"[awsenv] dropped placeholder AWS_* from the environment (key id was {len(key)} chars, "
              f"not an AWS key); boto3 will use {shared}.", file=sys.stderr)
    return True
