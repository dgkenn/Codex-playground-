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
    # composite (_gated)
    "micro_spot", "gross_max", "graded",
}
KNOWN_SIZE_MODES = {"flat", "fv", "markout"}


# The roster. Order here = order in the leaderboard's variant set (cosmetic only).
REGISTRY: list[Strat] = [
    Strat("baseline", note="no gate -- the LOSING control (-0.6/win); the bar every gate must beat"),
    # capacity / inventory frontier (winners run tiny inventory): tighter is better
    Strat("cap25", cap=25, note="tighter inventory cap"),
    Strat("skew15", skew=0.15, note="tighter inventory skew"),
    Strat("dneutral", skew=0.08, note="delta-neutral extreme (round2 #7): kills edge"),
    Strat("fv_size", size_mode="fv", note="fair-value-weighted size -> directional inventory = resolution cost"),
    # toxicity gating on the token's OWN book (the PROVEN edge, t=+5.4)
    Strat("micro_gate", gate="micro", note="microprice toxicity gate -- THE deployed edge (+4.8/win)"),
    Strat("micro_skew15", skew=0.15, gate="micro", note="micro + tight inventory (combined winner)"),
    Strat("micro_marg", gate="micro_marg", note="micro + edge MARGIN (separate2 refinement)"),
    Strat("tox_gate", gate="tox", note="composite: edge-margin OR bid-heavy extreme"),
    Strat("deplete_gate", gate="deplete", note="shed the side whose best queue is depleting (#2)"),
    Strat("gross_max", gate="gross_max", note="union of all toxicity gates -> maximize non-rebate GROSS"),
    Strat("flow_gate", gate="flow", note="pull the side a recent same-side taker burst is hitting"),
    Strat("late_gate", tau_guard=120, note="pull all quotes in the last 2min (late flow = informed)"),
    # principled inventory control (Avellaneda-Stoikov)
    Strat("av_stoikov", skew=0.99, gate="as", note="A-S: add inventory only if edge clears variance penalty"),
    # BTC-lag defense (on the fast WS feed)
    Strat("spot_react", gate="spot", note="pull the side BTC just moved against (lead-lag), pre-reprice"),
    Strat("micro_react", gate="micro_react", note="same via the FAST signal (own microprice leads spot)"),
    Strat("micro_spot", gate="micro_spot", note="cause+symptom: pull if book-imbalance OR BTC-lag flags"),
    # MAKEREDGE.md expansions
    Strat("mo_size", size_mode="markout", note="#3 markout-weighted sizing (continuous micro_gate)"),
    # MAKER_CHANGES2 micro-gate refinements
    Strat("micro_soft", gate="micro_soft", note="MC2 #3: gate only strongly-toxic (keep more rebate)"),
    Strat("micro_ufat", gate="micro_ufat", note="MC2 #4: strict at p~0.5, loose at the extremes"),
    # gate_lab.py winners -- validated on 56k fills (short-horizon mo5 = adverse selection); live A/B confirms deployable net
    Strat("micro_strict", gate="micro_strict", note="gate_lab: micro edge>=0.003 in our favor (t=+6.2 vs micro)"),
    Strat("micro_asym", gate="micro_asym", note="gate_lab: SELL side stricter than BUY (t=+7.5, highest)"),
    Strat("lead30", gate="lead30", note="gate_lab: pull side BTC moved against over 30s (t=+6.2)"),
    Strat("micro_cal", gate="micro_cal", note="gate_lab #10: calibrated ensemble -- keep iff pred markout+rebate>0 (OOS winner)"),

    # --- PRUNED from live (significantly unprofitable; kept for record + offline study) ---
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
