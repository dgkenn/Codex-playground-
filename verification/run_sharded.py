#!/usr/bin/env python3
"""Sharded full-range verification: low chunk via main-mode Turing
certificate, then certified segments with overlapping anchors. Each shard
is an independent certificate; their composition (adjacent anchors chain)
is the production architecture in miniature."""
import contextlib
import io
import json
import sys
import time

sys.path.insert(0, "verification")
import rs_verify

BOUNDS = [700, 10500, 20500, 30500, 40500, 50500, 60500, 70500, 74920]
OUT = "verification/results/sharded_74920.json"

out = {"shards": [], "started": time.time()}
sys.argv = ["rs_verify", "700"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rs_verify.main()
out["shards"].append(json.loads(buf.getvalue()))
for a, b in zip(BOUNDS[:-1], BOUNDS[1:]):
    r = rs_verify.segment_verify(a - 100 if a > 700 else a, b)
    out["shards"].append(r)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
ok = all(s.get("segment_certified") or s.get("rh_certified_to_endpoint")
         for s in out["shards"])
out["all_certified"] = ok
out["elapsed_sec"] = round(time.time() - out["started"], 1)
with open(OUT, "w") as f:
    json.dump(out, f, indent=1)
print("ALL CERTIFIED" if ok else "SEE SHARDS")
