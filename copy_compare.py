"""copy_compare.py -- weave it together: for each top-10% wallet, fit a RUNNABLE algo to its observed
behaviour, then COMPARE the algo's decisions to the bot's actual trades via false-neg / (bounded)
false-pos, and report the correlation + how to refine toward 95%.

Inputs: copy_multi_capture.jsonl (per-fill inside_tk = ticks inside our quote, from the live validator)
+ strategy_models.json (learned per-wallet params). Per wallet:
  RECALL (= 1 - false-negative rate) : fraction of the bot's fills our fitted-depth ladder would cover.
    This is fully observable (their fills are public) and is what we drive to >=95%.
  ARCHETYPE : touch-MM (recall hits 95% at a sane ladder depth) vs momentum/directional (it doesn't --
    a big share of fills sit far from touch, so a touch-ladder algo structurally cannot reach 95%; those
    need a momentum/entry component added).
  FALSE-POSITIVES : HONEST BOUND ONLY. The bot's resting/unfilled quotes are private (off-chain), so we
    cannot verify our extra quotes match theirs; FP can't be measured per-wallet from public data
    (orderflow_probe sees aggregate place/cancel, not attributed). We report recall + distributional
    fidelity, not a true precision.
  REFINE : if momentum (recall caps <95%), the fix is to add a momentum-entry rule; if touch-MM, set the
    ladder depth = the wallet's p95 inside_tk. python copy_compare.py
"""
from __future__ import annotations
import collections, json

DEPTHS = [1, 2, 3, 5, 7, 10, 14, 20]; SANE = 20


def main():
    W = collections.defaultdict(list)
    try:
        for ln in open("copy_multi_capture.jsonl"):
            r = json.loads(ln); W[r["w"]].append(r["inside_tk"])
    except FileNotFoundError:
        print("no copy_multi_capture.jsonl yet"); return
    models = json.load(open("strategy_models.json")) if __import__("os").path.exists("strategy_models.json") else {}
    m10 = {k[:10]: v for k, v in models.items()}
    print(f"{'wallet':>12}{'fills':>6}{'recall@fit':>11}{'fitdepth':>9}{'archetype':>16}  refine")
    copyable = 0; seen = 0
    for w, ins in sorted(W.items(), key=lambda kv: -len(kv[1])):
        n = len(ins)
        if n < 15:
            continue
        seen += 1
        cap = {d: 100 * sum(1 for x in ins if -1 <= x <= d) / n for d in DEPTHS}
        fit = next((d for d in DEPTHS if d <= SANE and cap[d] >= 95), None)
        # p95 inside depth (their ladder); recall there
        ds = sorted(x for x in ins if x >= -1)
        p95 = ds[min(len(ds) - 1, int(0.95 * len(ds)))] if ds else None
        if fit:
            arch = "touch-MM"; refine = f"set ladder depth = {fit}tk -> copyable"; copyable += 1
            recall = cap[fit]
        else:
            arch = "momentum/direct"; recall = cap[SANE]
            farc = 100 * sum(1 for x in ins if x > SANE or x < -1) / n
            refine = f"{farc:.0f}% of fills are far/wrong-side -> ADD momentum-entry rule (touch-ladder caps at {cap[SANE]:.0f}%)"
        setd = (m10.get(w, {}) or {}).get("set_discount_c")
        print(f"{w:>12}{n:>6}{recall:>10.0f}%{(fit or '>20'):>9}{arch:>16}  {refine}")
    print(f"\n{copyable}/{seen} wallets (with >=15 live fills) are touch-MM copyable to >=95% at a sane "
          f"ladder; the rest are momentum/directional (touch-ladder caps below 95% -> need a momentum "
          f"component). Pool more fills (overnight) for the idle long tail. FALSE-POSITIVES are a bound "
          f"only: the bots' resting quotes are private, so true precision isn't measurable from public data.")


if __name__ == "__main__":
    main()
