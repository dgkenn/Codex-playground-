"""Promotion watch: decide when the new candidate variants (micro_skew15, flow_gate) have
accumulated enough shared windows to evaluate, so they can be promoted into the per-fill
audit set (LOG_FILLS) for decision-grade root-causing.

Prints a single line: "READY ..." once either candidate has >= THRESH shared windows vs
baseline (with paired t), else "WAIT ..." (to stderr, so a monitor only notifies on READY).
"""
import glob, json, math, sys
from collections import defaultdict

THRESH = 15
CANDS = ["micro_skew15", "av_stoikov", "micro_react", "spot_react"]


def main():
    wins = {}
    for f in glob.glob("gha_data/shadow_windows_r*.jsonl"):
        for ln in open(f):
            ln = ln.strip()
            if ln:
                try:
                    w = json.loads(ln); wins[w["ws"]] = w
                except Exception:
                    pass
    rows = list(wins.values())
    parts = []
    ready = False
    for v in CANDS:
        pairs = [w[v]["net"] - w["baseline"]["net"]
                 for w in rows if v in w and "baseline" in w and "net" in w.get(v, {})]
        n = len(pairs)
        if n >= 2:
            m = sum(pairs) / n
            sd = (sum((x - m) ** 2 for x in pairs) / (n - 1)) ** 0.5
            t = m / (sd / math.sqrt(n)) if sd > 0 else float("nan")
        else:
            m = t = float("nan")
        parts.append(f"{v}: n={n} dNet/win={m:+.2f} t={t:+.2f}")
        if n >= THRESH:
            ready = True
    line = ("READY " if ready else "WAIT ") + " | ".join(parts)
    if ready:
        print(line)                 # stdout -> monitor notifies
    else:
        print(line, file=sys.stderr)  # stderr -> silent (output file only)


if __name__ == "__main__":
    main()
