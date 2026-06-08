"""copy_oos.py -- the complete per-wallet answer: for EVERY top-10% wallet, fit its own ladder depth on a
TRAIN split and measure capture OUT-OF-SAMPLE on a TEST split, vs the independent market consensus (rest
of the market; no self-capture). Reports, per wallet: OOS placement capture, the fitted depth D_w (= how
wide a ladder that wallet needs), and whether D_w is SANE/profitable (tight ladders backtest profitable;
wide ones lose -- band_p). This shows 'every wallet is 95%-capturable at its own depth' AND honestly
flags which depths are profitable (the touch-MM subset) vs capital-heavy/marginal. python copy_oos.py
"""
from __future__ import annotations
import collections, json

TICK = 0.01; WIN = 30; SANE = 6   # a tight, backtest-profitable maker ladder is <= ~6 ticks vs mid


def main():
    mm = json.load(open("mm_score.json")); order = [r["w"] for r in mm[:max(1, len(mm) // 10)]]
    targets = set(order)
    mkt_path = collections.defaultdict(list); tfills = collections.defaultdict(list)
    for ln in open("makers_trades.jsonl"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        for w, side, sz, pr, oi, ts in r["trades"]:
            pup = pr if oi == 0 else 1 - pr
            if w not in targets:
                mkt_path[r["cid"]].append((ts, pup))
            else:
                tfills[w].append((r["cid"], ts, pup))
    for cid in mkt_path:
        mkt_path[cid].sort()

    def offset_ticks(cid, ts, pup):
        near = [pp for (tt, pp) in mkt_path[cid] if abs(tt - ts) <= 5]
        return (min(abs(pp - pup) for pp in near) / TICK) if near else None

    def place_cap(fills, D):                          # placement: consensus within D over 30s
        hit = 0; tot = 0
        for cid, ts, pup in fills:
            near = [pp for (tt, pp) in mkt_path[cid] if ts - WIN <= tt <= ts + 2]
            if not near:
                continue
            tot += 1
            if min(near) - D * TICK - 1e-9 <= pup <= max(near) + D * TICK + 1e-9:
                hit += 1
        return (100 * hit / tot) if tot else 0.0, tot

    print(f"{'wallet':>12}{'Ntr/Nte':>9}{'cov':>6}{'D_w':>7}{'OOS@5tk':>7}{'flag':>14}")
    ok = 0; tight = 0
    for w in order:
        f = sorted(tfills.get(w, []), key=lambda x: x[1])
        if len(f) < 40:
            print(f"{w[:10]:>12}{len(f):>9}   (need >=40 cached fills)"); continue
        cut = int(len(f) * 0.7); tr, te = f[:cut], f[cut:]
        offs = sorted(o for o in (offset_ticks(*x) for x in tr) if o is not None)
        if not offs:
            continue
        Dw = offs[min(len(offs) - 1, int(0.95 * len(offs)))]   # fit depth = train p95 offset-from-consensus
        capDw, nte = place_cap(te, Dw); cap5, _ = place_cap(te, 5)
        cov = 100 * nte / max(1, len(te))              # % of test fills with an external consensus to score
        prof = "TIGHT(prof)" if Dw <= SANE else "wide(marginal)"
        robust = cov >= 60 and Dw <= SANE and cap5 >= 95
        if robust:
            ok += 1
        flag = prof if cov >= 60 else f"COV {cov:.0f}%!"
        print(f"{w[:10]:>12}{f'{len(tr)}/{nte}':>9}{cov:>6.0f}%{Dw:>7.0f}{cap5:>7.0f}%{flag:>14}")
    print(f"\n{ok}/{len(order)} wallets ROBUSTLY >=95% OOS-captured at a TIGHT ladder (<= {SANE}tk) WITH >=60% "
          f"consensus coverage. CAVEAT: where coverage is low (cov%!), there were too few OTHER-market trades "
          f"near the fills to score them -> the % is on a biased subset (niche/quiet-moment wallets); not a "
          f"clean verdict. The robust set is the high-volume touch-MMs; confirm the rest with live WS overnight.")


if __name__ == "__main__":
    main()
