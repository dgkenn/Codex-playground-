#!/usr/bin/env python3
"""
COMPONENT: AUTH + REQUEST HOT PATH (fully local, proxy-free benchmark)

Measures the CPU cost of the Kalshi RSA-PSS-SHA256 request-signing hot path
on this machine, with a synthetic 2048-bit key (no real Kalshi credentials
are used or required -- this is a pure CPU-cost measurement).

All numbers in this script are LOCAL / CPU-bound and therefore NOT subject to
the agent-proxy network pollution caveat that applies to venue latency
measurements elsewhere in this study. They ARE machine-dependent (this
container: 4 vCPU Intel Xeon @ 2.10GHz, Python 3.11.15 CPython, OpenSSL
3.0.13, cryptography 41.0.7) -- treat absolute ms as "this class of hardware"
figures, not universal constants, but the *relative* gaps (naive vs warm vs
native) are the load-bearing result and should generalize.

Sections:
  1. cryptography RSA-PSS sign latency, warm asyncio-style single process (N>=1000)
  2. subprocess-per-call ("naive cron pattern") vs warm-process amortized cost
  3. Full request assembly cost (timestamp + sign + headers + JSON body) for
     a create-order and a batch-cancel payload
  4. Native comparison: pure-Rust `rsa` crate (cargo, built separately) and
     openssl(1) CLI floor estimate, with process-spawn overhead isolated
  5. orjson vs stdlib json serialization for a typical order payload
"""

import json
import os
import statistics
import subprocess
import sys
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

try:
    import orjson
    HAVE_ORJSON = True
except ImportError:
    HAVE_ORJSON = False

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
OUT_PATH = os.path.join(OUT_DIR, "bench_signing.json")
SCRATCH_KEY_PATH = "/tmp/claude-0/-home-user-Codex-playground-/3f613eca-224e-56c2-8c01-c756f2181186/scratchpad/rsakey.pem"
SCRATCH_MSG_PATH = "/tmp/claude-0/-home-user-Codex-playground-/3f613eca-224e-56c2-8c01-c756f2181186/scratchpad/msg.txt"
RUST_BIN_PATH = "/tmp/claude-0/-home-user-Codex-playground-/3f613eca-224e-56c2-8c01-c756f2181186/scratchpad/rsabench/target/release/rsabench"

CAVEAT = (
    "Local CPU-bound benchmark, no network path involved -- NOT subject to the "
    "agent-proxy pollution caveat. Absolute ms are specific to this container's "
    "hardware (4 vCPU Intel Xeon @ 2.10GHz); relative gaps are the portable result."
)


def stats_ms(samples_s):
    ms = sorted(x * 1000.0 for x in samples_s)
    n = len(ms)
    return {
        "n": n,
        "median_ms": round(statistics.median(ms), 4),
        "mean_ms": round(sum(ms) / n, 4),
        "p99_ms": round(ms[min(n - 1, int(n * 0.99))], 4),
        "min_ms": round(ms[0], 4),
        "max_ms": round(ms[-1], 4),
    }


def gen_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def pss_sign(private_key, message: bytes) -> bytes:
    return private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


# ---------------------------------------------------------------------------
# 1. cryptography RSA-PSS sign latency, warm process
# ---------------------------------------------------------------------------
def bench_warm_sign(private_key, n=2000):
    msg = b"1732900000123POST/trade-api/v2/portfolio/orders"
    # warmup
    for _ in range(50):
        pss_sign(private_key, msg)
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        pss_sign(private_key, msg)
        samples.append(time.perf_counter() - t0)
    return stats_ms(samples)


# ---------------------------------------------------------------------------
# 2. subprocess-per-call ("naive cron") vs warm process
# ---------------------------------------------------------------------------
_SUBPROC_SCRIPT = """
import time, sys
t_start = time.perf_counter()
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
t_import = time.perf_counter()
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
t_keygen = time.perf_counter()
msg = b"1732900000123POST/trade-api/v2/portfolio/orders"
sig = key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
t_sign = time.perf_counter()
print(t_import - t_start, t_keygen - t_import, t_sign - t_keygen)
"""


def bench_subprocess_per_call(n=30):
    """Simulates a naive `python3 sign_and_post.py` cron-style leg: fresh
    interpreter + fresh import + (worst case) fresh keygen + sign, every call.
    n is small (30, not 1000) because each iteration pays full interpreter
    startup (~50-150ms) -- representative sample, not a hot-path count."""
    wall_times = []
    import_times = []
    keygen_times = []
    sign_times = []
    for _ in range(n):
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-c", _SUBPROC_SCRIPT],
            capture_output=True, text=True, check=True,
        )
        wall = time.perf_counter() - t0
        wall_times.append(wall)
        parts = proc.stdout.strip().split()
        import_times.append(float(parts[0]))
        keygen_times.append(float(parts[1]))
        sign_times.append(float(parts[2]))

    # baseline: bare interpreter spawn overhead with no imports, for reference
    baseline = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], capture_output=True, check=True)
        baseline.append(time.perf_counter() - t0)

    return {
        "note": (
            "Naive cron pattern = fresh `python3 -c ...` process per signed request "
            "(fresh interpreter, fresh `cryptography` import, key already held fixed "
            "cost excluded from 'per-call' framing below by isolating sign_s alone). "
            "wall_s = full observed process wall time including exec/fork."
        ),
        "full_process_wall": stats_ms(wall_times),
        "bare_interpreter_spawn_baseline": stats_ms(baseline),
        "cryptography_import_cost": stats_ms(import_times),
        "rsa_2048_keygen_cost": stats_ms(keygen_times),
        "sign_op_cost_within_subprocess": stats_ms(sign_times),
    }


# ---------------------------------------------------------------------------
# 3. Full request assembly: timestamp + sign + headers + JSON body
# ---------------------------------------------------------------------------
def build_create_order_payload():
    return {
        "ticker": "KXBTC-25JUL30-T65000",
        "action": "buy",
        "side": "yes",
        "count": 25,
        "type": "limit",
        "yes_price": 47,
        "client_order_id": "co_" + "a" * 32,
        "post_only": True,
        "time_in_force": "gtc",
    }


def build_batch_cancel_payload(n_orders=10):
    return {
        "order_ids": [f"ord_{i:08d}{'b'*24}" for i in range(n_orders)],
    }


def assemble_request(private_key, method, path, body_dict, json_dumps=json.dumps):
    ts_ms = str(int(time.time() * 1000))
    msg = (ts_ms + method + path).encode()
    sig = pss_sign(private_key, msg)
    import base64
    sig_b64 = base64.b64encode(sig).decode()
    headers = {
        "KALSHI-ACCESS-KEY": "synthetic-key-id-for-benchmark-0000",
        "KALSHI-ACCESS-SIGNATURE": sig_b64,
        "KALSHI-ACCESS-TIMESTAMP": ts_ms,
        "Content-Type": "application/json",
    }
    body_bytes = json_dumps(body_dict)
    if isinstance(body_bytes, str):
        body_bytes = body_bytes.encode()
    return headers, body_bytes


def bench_request_assembly(private_key, n=1000):
    create_order_body = build_create_order_payload()
    batch_cancel_body = build_batch_cancel_payload()

    def run(method, path, body, json_dumps):
        for _ in range(20):  # warmup
            assemble_request(private_key, method, path, body, json_dumps)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            assemble_request(private_key, method, path, body, json_dumps)
            samples.append(time.perf_counter() - t0)
        return stats_ms(samples)

    return {
        "create_order_stdlib_json": run(
            "POST", "/trade-api/v2/portfolio/orders", create_order_body, json.dumps
        ),
        "batch_cancel_stdlib_json": run(
            "DELETE", "/trade-api/v2/portfolio/orders/batched", batch_cancel_body, json.dumps
        ),
    }


# ---------------------------------------------------------------------------
# 4. Native comparison: pure-Rust `rsa` crate + openssl(1) CLI floor
# ---------------------------------------------------------------------------
def bench_native_rust():
    if not os.path.exists(RUST_BIN_PATH):
        return {"available": False, "note": "rust binary not found at expected path; skipped"}
    try:
        out = subprocess.run([RUST_BIN_PATH], capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(out.stdout.strip())
        return {
            "available": True,
            "implementation": "pure-Rust `rsa` crate v0.9.10 + `sha2` v0.10, RustCrypto stack, NO OpenSSL/ASM bignum backend",
            "n": data["n"],
            "median_ms": round(data["median_ns"] / 1e6, 4),
            "p99_ms": round(data["p99_ns"] / 1e6, 4),
            "mean_ms": round(data["mean_ns"] / 1e6, 4),
            "caveat": (
                "The RustCrypto `rsa` crate uses a portable/constant-time software "
                "bignum implementation with NO hardware/ASM modexp acceleration -- it "
                "is measurably SLOWER here than OpenSSL's native RSA engine (see "
                "openssl_speed_native below). Do not read this as 'native language "
                "floor'; it is 'safe pure-language floor'. For a true native floor use "
                "an OpenSSL-linked binding (e.g. openssl-sys) or the openssl CLI/`openssl "
                "speed` numbers, which do use the accelerated bignum path."
            ),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def bench_openssl_cli(n=30):
    """openssl(1) CLI, one process per sign -- floor estimate per instructions.
    Isolates process-spawn overhead from the actual signing cost by also timing
    a no-op openssl invocation the same number of times."""
    if not os.path.exists(SCRATCH_KEY_PATH):
        return {"available": False, "note": "no persisted openssl key found; regenerate to reproduce"}

    baseline = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(["openssl", "version"], capture_output=True, check=True)
        baseline.append(time.perf_counter() - t0)

    sign_wall = []
    sig_out = "/tmp/bench_sig_out.bin"
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign", SCRATCH_KEY_PATH,
                "-sigopt", "rsa_padding_mode:pss", "-sigopt", "rsa_pss_saltlen:32",
                "-out", sig_out, SCRATCH_MSG_PATH,
            ],
            capture_output=True, check=True,
        )
        sign_wall.append(time.perf_counter() - t0)

    baseline_stats = stats_ms(baseline)
    sign_stats = stats_ms(sign_wall)
    delta_median_ms = round(sign_stats["median_ms"] - baseline_stats["median_ms"], 4)

    return {
        "available": True,
        "n": n,
        "note": (
            "Each call = fresh `openssl` process: fork/exec + libssl/libcrypto init "
            "+ PEM key parse from disk + PSS sign + write signature to disk. "
            "process_spawn_overhead isolated via a no-op `openssl version` baseline "
            "run the same n times on the same machine in the same loop."
        ),
        "full_process_wall": sign_stats,
        "process_spawn_baseline_noop": baseline_stats,
        "estimated_sign_plus_keyio_delta_median_ms": delta_median_ms,
    }


def bench_openssl_speed_native():
    """`openssl speed rsa2048`: single warm process, internal loop, OpenSSL's
    real accelerated bignum/modexp path. This is the closest thing to a true
    'native floor' for RSA-2048 sign on this CPU."""
    try:
        out = subprocess.run(
            ["openssl", "speed", "-seconds", "2", "rsa2048"],
            capture_output=True, text=True, timeout=15,
        )
        text = out.stdout + out.stderr
        sign_line = None
        for line in text.splitlines():
            if line.strip().startswith("rsa 2048 bits"):
                sign_line = line
                break
        if not sign_line:
            return {"available": False, "raw": text[-2000:]}
        # format: "rsa 2048 bits 0.000351s 0.000018s   2850.5  55322.5"
        parts = sign_line.split()
        sign_s = float(parts[3].rstrip("s"))
        sign_per_s = float(parts[5])
        return {
            "available": True,
            "note": "OpenSSL 3.0.13 native engine, single warm process, PKCS1 private-key op timing (RSA-PSS sign cost is dominated by this modexp; PSS padding overhead itself is sub-microsecond). This is the true native-floor comparator.",
            "sign_ms": round(sign_s * 1000, 4),
            "sign_ops_per_sec": sign_per_s,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 5. orjson vs stdlib json
# ---------------------------------------------------------------------------
def bench_json_libs(n=5000):
    payload = build_create_order_payload()
    payload_batch = build_batch_cancel_payload()

    def bench_dumps(fn, obj, n):
        for _ in range(50):
            fn(obj)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn(obj)
            samples.append(time.perf_counter() - t0)
        return stats_ms(samples)

    result = {
        "stdlib_json_create_order": bench_dumps(json.dumps, payload, n),
        "stdlib_json_batch_cancel": bench_dumps(json.dumps, payload_batch, n),
    }
    if HAVE_ORJSON:
        result["orjson_create_order"] = bench_dumps(orjson.dumps, payload, n)
        result["orjson_batch_cancel"] = bench_dumps(orjson.dumps, payload_batch, n)
        result["orjson_version"] = orjson.__version__
    else:
        result["orjson"] = {"available": False, "note": "orjson not installed"}
    return result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {
        "caveat": CAVEAT,
        "machine": {
            "cpu": "Intel(R) Xeon(R) Processor @ 2.10GHz, 4 vCPU (container)",
            "python": sys.version,
            "cryptography_version": __import__("cryptography").__version__,
            "openssl_runtime": subprocess.run(["openssl", "version"], capture_output=True, text=True).stdout.strip(),
        },
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    print("Generating synthetic RSA-2048 key...", file=sys.stderr)
    key = gen_key()

    print("[1/5] warm-process cryptography RSA-PSS sign, N=2000...", file=sys.stderr)
    results["1_warm_process_sign"] = bench_warm_sign(key, n=2000)

    print("[2/5] subprocess-per-call vs warm process, N=30...", file=sys.stderr)
    results["2_subprocess_per_call_vs_warm"] = bench_subprocess_per_call(n=30)

    print("[3/5] full request assembly (create-order, batch-cancel), N=1000 each...", file=sys.stderr)
    results["3_full_request_assembly"] = bench_request_assembly(key, n=1000)

    print("[4/5] native comparison: rust crate + openssl CLI + openssl speed...", file=sys.stderr)
    results["4a_native_rust_crate"] = bench_native_rust()
    results["4b_openssl_cli_per_process"] = bench_openssl_cli(n=30)
    results["4c_openssl_speed_native_floor"] = bench_openssl_speed_native()

    print("[5/5] orjson vs stdlib json, N=5000...", file=sys.stderr)
    results["5_json_serialization"] = bench_json_libs(n=5000)

    # ---- summary budget table -------------------------------------------------
    warm_sign_ms = results["1_warm_process_sign"]["median_ms"]
    assembly_create_ms = results["3_full_request_assembly"]["create_order_stdlib_json"]["median_ms"]
    assembly_cancel_ms = results["3_full_request_assembly"]["batch_cancel_stdlib_json"]["median_ms"]
    naive_wall_ms = results["2_subprocess_per_call_vs_warm"]["full_process_wall"]["median_ms"]
    naive_import_ms = results["2_subprocess_per_call_vs_warm"]["cryptography_import_cost"]["median_ms"]
    naive_keygen_ms = results["2_subprocess_per_call_vs_warm"]["rsa_2048_keygen_cost"]["median_ms"]

    native_floor_ms = None
    if results["4c_openssl_speed_native_floor"].get("available"):
        native_floor_ms = results["4c_openssl_speed_native_floor"]["sign_ms"]
    rust_ms = None
    if results["4a_native_rust_crate"].get("available"):
        rust_ms = results["4a_native_rust_crate"]["median_ms"]

    results["summary_cpu_budget_table_ms"] = {
        "note": (
            "Per-request CPU budget for the sign+assemble hot path, median ms, "
            "this machine. 'naive_python_cron_leg' = worst case, fresh interpreter "
            "per request, key freshly generated each time (upper bound -- a real "
            "cron leg would load a persisted key, not regenerate it; keygen_only_ms "
            "broken out separately so that cost can be subtracted for a "
            "load-existing-key variant)."
        ),
        "naive_python_cron_leg_full_wall_ms": naive_wall_ms,
        "naive_python_cron_leg_breakdown": {
            "interpreter_startup_plus_misc_ms": round(naive_wall_ms - naive_import_ms - naive_keygen_ms - results["2_subprocess_per_call_vs_warm"]["sign_op_cost_within_subprocess"]["median_ms"], 4),
            "cryptography_import_ms": naive_import_ms,
            "rsa_2048_keygen_ms": naive_keygen_ms,
            "sign_ms": results["2_subprocess_per_call_vs_warm"]["sign_op_cost_within_subprocess"]["median_ms"],
        },
        "naive_python_cron_leg_with_persisted_key_estimate_ms": round(
            naive_wall_ms - naive_keygen_ms, 4
        ),
        "warm_asyncio_python_sign_only_ms": warm_sign_ms,
        "warm_asyncio_python_full_assembly_create_order_ms": assembly_create_ms,
        "warm_asyncio_python_full_assembly_batch_cancel_ms": assembly_cancel_ms,
        "native_pure_rust_crate_sign_only_ms": rust_ms,
        "native_openssl_engine_sign_only_ms_true_floor": native_floor_ms,
        "ratio_naive_cron_vs_warm_python": round(naive_wall_ms / assembly_create_ms, 1) if assembly_create_ms else None,
        "ratio_warm_python_vs_native_openssl_floor": round(warm_sign_ms / native_floor_ms, 1) if native_floor_ms else None,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    print(json.dumps(results["summary_cpu_budget_table_ms"], indent=2))


if __name__ == "__main__":
    main()
