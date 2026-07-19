"""strategies.py -- SINGLE SOURCE OF TRUTH for the live shadow strategy roster.

Why this file exists: we are constantly adding/tweaking/retiring strategies. Defining them inline in
shadow_compare.configs() meant every change edited the validated core file, and "pruning" meant DELETING
the definition (losing the params + the reason it failed). Here each strategy is pure DATA:

  * ADD a strategy      -> append one Strat(...) line (+ a gate branch in Variant._gate_one if it's a
                           brand-new gate type; existing gate strings need nothing else).
  * REMOVE from live    -> flip `enabled=False` (keeps the definition + `note` for re-enabling / offline
                           study; it simply drops out of the live A/B).
  * RE-ENABLE later     -> flip it back. No core edits, no lost history.

Everything downstream (leaderboard.py, aggregate_shadow.py, breadth_*.py) DISCOVERS variant names from the
captured data, so the roster can change freely without touching any analysis code.

`KNOWN_GATES` must stay in sync with Variant._gate_one / _gated in shadow_compare.py (validate() enforces
that every enabled gate is listed here, so an unknown gate -- which would silently behave like baseline --
is caught before a run). Run `python strategies.py` to print + validate the roster (used as a CI preflight).

KALSHI GEARING: no rebate -> Insight-10 reverses (without per-fill rebate subsidy, stricter gates likely win:
micro_strict/micro_asym are first-line candidates); queue replay shows back-of-queue fills are toxic at depth
(q>=500 -> negative) so the deployable expression is sub-cent price-improvement to the FRONT + gate; the live
A/B on kalshi_collect data decides.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Strat:
    name: str
    cap: float = 50.0
    skew: float = 0.25
    size_mode: str = "flat"           # flat | fv | markout
    gate: str | None = None           # None = no toxicity gate (baseline mechanics)
    tau_guard: int = 0                # pull ALL quotes when < tau_guard s to close (late = informed)
    short_skew: float | None = None   # asymmetric inventory leash (None = symmetric = skew)
    enabled: bool = True
    note: str = ""


# Atomic gates implemented in Variant._gate_one, plus the composites in Variant._gated.
# Keep this list in lockstep with that dispatch (validate() checks membership).
KNOWN_GATES = {
    # atomic (_gate_one)
    "band", "vol", "as_full", "micro", "micro_soft", "micro_ufat", "micro_marg", "tox",
    "deplete", "predict", "flow", "spot", "micro_react", "as",
    # gate_lab.py winners (validated on 56k fills / 141 windows; GATING.md)
    "micro_strict", "micro_asym", "lead30", "micro_cal",
    # combo_lab.py best overall composite (INSIGHTS_4DAY)
    "ufat_band",
    # composite (_gated)
    "micro_spot", "gross_max", "graded",
}
KNOWN_SIZE_MODES = {"flat", "fv", "markout"}


# The roster. Order here = order in the leaderboard's variant set (cosmetic only).
REGISTRY: list[Strat] = [
    Strat("baseline", note="no gate -- the control; the bar every variant must beat"),

    # === 32-DAY FORWARD VERDICT (live A/B 2026-06-10..07-11, n=32 daily rollups; WINNING_STRATEGY.md) ===
    # Only TWO variants were month-positive; every gate-family variant lost or was inert. All notes
    # below carry their forward verdict: "32d: <meanDelta>/win t=<day-clustered t> <days positive>".

    # -- WINNERS (kept live) --
    Strat("av_stoikov", skew=0.99, gate="as",
          note="A-S: add inventory only if edge clears variance penalty | 32d: +4.67/win t=+7.68 "
               "29/32 days+, gross+ 32/32, top variant 25/32 days -- THE month winner"),
    Strat("mo_size", size_mode="markout",
          note="markout-weighted sizing (continuous micro_gate) | 32d: +1.88/win t=+5.76 29/32 days+, "
               "gross+ 32/32 -- winner #2; corr +0.38 w/ av_stoikov, positive on all 3 of its down-days"),

    # -- ENSEMBLE + ABLATION arms (added off the month verdict; av_stoikov differs from baseline in
    #    BOTH skew 0.25->0.99 AND the AS gate, so the 2x2 below separates the knobs).
    #    PRE-REGISTERED promotion bar (declared BEFORE any data): >=14 forward days, day-clustered
    #    t>=3, gross-positive >=80% of days, mean edge >= max(av_stoikov, mo_size) same-days.
    Strat("as_markout", skew=0.99, gate="as", size_mode="markout",
          note="THE candidate: A-S inventory gate + markout-weighted size (both month winners combined)"),
    Strat("mo_skew99", skew=0.99, size_mode="markout",
          note="ablation: markout size + loose leash, NO gate (is the AS gate additive?)"),
    Strat("skew99", skew=0.99,
          note="ablation: loose leash alone (how much of av_stoikov is just skew 0.99?)"),
    Strat("as_cap100", cap=100, skew=0.99, gate="as",
          note="capacity probe: winner config at 2x inventory cap -- does the edge survive the "
               "inventory needed to scale size? (cap was only ever tested DOWN; cap25 lost -7.86t)"),

    # -- WATCH (operational purpose) --
    Strat("micro_gate", gate="micro",
          note="microprice toxicity gate -- WAS 'THE deployed edge (+4.8/win)' | 32d: Delta=+0.000 on "
               "EVERY day -- the gate never fires on this venue = the deployed strategy is a NO-OP. "
               "Kept enabled as the deployed-twin decay watch; deployment should move to the winner"),

    # -- PRUNED by the 32d forward verdict (month t <= -3, n=32 = decisive; defs kept for record) --
    Strat("fv_size", size_mode="fv", enabled=False,
          note="fair-value-weighted size | PRUNED 32d: -0.36/win t=-1.61 11/32 days+ -- not decisive "
               "but negative after a full month and dominated by markout sizing; slot -> as_cap100"),
    Strat("cap25", cap=25, enabled=False,
          note="tighter inventory cap | PRUNED 32d: -2.87/win t=-7.86 2/32 days+"),
    Strat("skew15", skew=0.15, enabled=False,
          note="tighter inventory skew | PRUNED 32d: -2.02/win t=-7.44 4/32 days+ (loose leash wins this regime)"),
    Strat("dneutral", skew=0.08, enabled=False,
          note="delta-neutral extreme (round2 #7) | PRUNED 32d: -3.91/win t=-9.33 1/32 days+ -- worst-in-class"),
    Strat("micro_skew15", skew=0.15, gate="micro", enabled=False,
          note="micro + tight inventory | PRUNED 32d: -2.02/win t=-7.44 4/32 (identical to skew15: micro inert)"),
    Strat("micro_marg", gate="micro_marg", enabled=False,
          note="micro + edge MARGIN | PRUNED 32d: -3.21/win t=-6.02 2/32 days+"),
    Strat("tox_gate", gate="tox", enabled=False,
          note="edge-margin OR bid-heavy extreme | PRUNED 32d: -3.35/win t=-6.54 1/32 days+"),
    Strat("deplete_gate", gate="deplete", enabled=False,
          note="shed the depleting-queue side | PRUNED 32d: -1.25/win t=-5.72 5/32 days+"),
    Strat("gross_max", gate="gross_max", enabled=False,
          note="union of all toxicity gates | PRUNED 32d: -1.67/win t=-7.71 2/32 days+"),
    Strat("flow_gate", gate="flow", enabled=False,
          note="pull the taker-burst side | PRUNED 32d: -1.50/win t=-6.98 3/32 days+"),
    Strat("late_gate", tau_guard=120, enabled=False,
          note="pull all quotes last 2min | PRUNED 32d: -1.27/win t=-3.77 6/32 days+"),
    Strat("spot_react", gate="spot", enabled=False,
          note="pull the side BTC moved against | PRUNED 32d: -0.68/win t=-3.80 8/32 days+"),
    Strat("micro_react", gate="micro_react", enabled=False,
          note="BTC-lag via fast microprice | PRUNED 32d: -1.04/win t=-5.18 7/32 days+"),
    Strat("micro_spot", gate="micro_spot", enabled=False,
          note="book-imbalance OR BTC-lag | PRUNED 32d: -0.68/win t=-3.80 8/32 (== spot_react: micro leg inert)"),
    Strat("micro_soft", gate="micro_soft", enabled=False,
          note="MC2 #3 gate only strongly-toxic | PRUNED 32d: Delta=+0.000 all 32 days -- INERT (never fires)"),
    Strat("micro_ufat", gate="micro_ufat", enabled=False,
          note="MC2 #4 strict at p~0.5 | PRUNED 32d: -2.16/win t=-4.35 6/32 days+"),
    Strat("ufat_skew15", gate="micro_ufat", skew=0.15, enabled=False,
          note="metrics_hypo H1: ufat gate + tight skew (replay holdout Calmar 40.6 vs 31.0) | "
               "PRUNED 32d: -3.81/win t=-7.07 2/32 days+ -- replay result did NOT reproduce forward"),
    Strat("micro_strict", gate="micro_strict", enabled=False,
          note="gate_lab: micro edge>=0.003 (lab t=+6.2) | PRUNED 32d: -4.47/win t=-8.36 0/32 days+ -- "
               "dead last; REFUTES the 'stricter gates win' hypothesis, over-gating sheds too much flow"),
    Strat("micro_asym", gate="micro_asym", enabled=False,
          note="gate_lab: SELL stricter than BUY (lab t=+7.5) | PRUNED 32d: -0.52/win t=-3.09 9/32 days+"),
    Strat("lead30", gate="lead30", enabled=False,
          note="PRUNED (lookahead artifact): its only support was gate_lab scoring on `dspot30`, which is "
               "the spot move AFTER the fill; the honest past-30s backtest (strategy_opt/gate_lab fixed) "
               "is NEGATIVE on both deployable net and mo5 (t=-5.6 vs micro)"),
    Strat("micro_cal", gate="micro_cal", enabled=False,
          note="gate_lab #10 calibrated ensemble (lab OOS winner) | PRUNED 32d: -4.07/win t=-7.70 2/32 days+"),
    Strat("ufat_band", gate="ufat_band", enabled=False,
          note="combo_lab BEST IS+OOS (ufat + skip P(up) 0.30-0.55) | PRUNED 32d: -3.47/win t=-6.10 "
               "6/32 days+ -- another lab winner that did not survive forward"),

    # --- PRUNED earlier (significantly unprofitable; kept for record + offline study) ---
    Strat("as_full", skew=0.99, gate="as_full", enabled=False,
          note="PRUNED -8.3/win (gross -14.6): vol-adaptive A-S over-gates (WINNER_TWEAKS #3)"),
    Strat("vol_gate", gate="vol", enabled=False,
          note="PRUNED -7.9/win (gross -13.2): pull-both-in-vol-burst sheds too much rebate"),
    Strat("band_p", gate="band", enabled=False,
          note="PRUNED -9.2/win (gross -13.7): restricting to mid-prob band quotes the MOST toxic zone (#10)"),
    Strat("graded", cap=25, skew=0.15, gate="graded", enabled=False,
          note="PRUNED -2.4/win: with-move-pull + band + tight clip over-gates (composite of failures)"),
]


def enabled() -> list[Strat]:
    """The live roster (what the shadow collector actually runs)."""
    return [s for s in REGISTRY if s.enabled]


def validate(strats: list[Strat] | None = None) -> list[str]:
    """Return a list of problems (empty = OK). Catches the mistakes that would silently corrupt a run:
    duplicate names, unknown gate/size_mode (an unknown gate behaves like baseline -> a silent no-op),
    out-of-range params."""
    strats = REGISTRY if strats is None else strats
    errs: list[str] = []
    seen: set[str] = set()
    for s in strats:
        if not s.name or not s.name.replace("_", "").isalnum():
            errs.append(f"bad name: {s.name!r}")
        if s.name in seen:
            errs.append(f"duplicate name: {s.name!r}")
        seen.add(s.name)
        if s.gate is not None and s.gate not in KNOWN_GATES:
            errs.append(f"{s.name}: unknown gate {s.gate!r} (add it to KNOWN_GATES + Variant._gate_one)")
        if s.size_mode not in KNOWN_SIZE_MODES:
            errs.append(f"{s.name}: unknown size_mode {s.size_mode!r}")
        if not (0 < s.cap <= 1000):
            errs.append(f"{s.name}: cap out of range: {s.cap}")
        if not (0 < s.skew <= 1.0):
            errs.append(f"{s.name}: skew out of range: {s.skew}")
        if s.tau_guard < 0:
            errs.append(f"{s.name}: negative tau_guard: {s.tau_guard}")
    return errs


def snapshot() -> dict:
    """Self-describing record of the live roster, written into the data dir each run."""
    return {"n_enabled": len(enabled()),
            "enabled": [s.name for s in enabled()],
            "disabled": [s.name for s in REGISTRY if not s.enabled],
            "roster": [{"name": s.name, "cap": s.cap, "skew": s.skew, "size_mode": s.size_mode,
                        "gate": s.gate, "tau_guard": s.tau_guard, "enabled": s.enabled} for s in REGISTRY]}


def main():
    import sys
    errs = validate()
    print(f"=== strategy roster: {len(enabled())} live / {len(REGISTRY)} total ===")
    for s in REGISTRY:
        flag = " " if s.enabled else "x"
        g = s.gate or "-"
        print(f" [{flag}] {s.name:<14} cap={s.cap:<5g} skew={s.skew:<5g} size={s.size_mode:<7} gate={g:<11} {s.note}")
    if errs:
        print("\nVALIDATION FAILED:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print(f"\nvalidation OK ({len(enabled())} enabled, {len(REGISTRY) - len(enabled())} pruned)")


if __name__ == "__main__":
    main()
