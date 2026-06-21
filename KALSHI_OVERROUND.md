# Multi-outcome event OVERROUND (Dutch-book) — tested, ARTIFACT not an edge (2026-06-21)

Re-examined with the larger settled universe, testing a NEW structure: harvest a multi-leg event's
overround (sell every "who-wins-X" YES leg when they sum to >$1). `kalshi_overround_scan.py`.

## Result: the spectacular overrounds are a GROUPING ARTIFACT, not an arbitrage
- Open multi-leg soft events showed median sum(YES_bid)=1.21 and headline "overrounds" up to +1129%
  (KXB200Q), Waymo +366%, FDA-approve +150–198%, SuperBowl-headline +134%.
- **These are NOT mutually-exclusive single-winner partitions.** They are INDEPENDENT yes/no questions
  grouped under one event: "will FDA approve drug A / drug B / drug C" (many can be YES), "will Waymo
  operate in city X" (many YES), "will person X testify" (many YES), price/quantity thresholds (nested
  YES). sum(YES)>1 is legitimate and **un-harvestable** — selling all YES loses on every leg that hits,
  and many do.
- **Clean confirmation:** filtering SETTLED multi-leg events to *exactly one* YES result (a real partition)
  returned **0** usable events — the buy-all-NO basket has no exploitable population here.

## Why it's not a new edge even where partitions exist
Genuine single-winner events (elections/awards/championships) carry an overround = the same
favorite-longshot bias (`KALSHI_MAKER_VERDICT.md`) expressed at the event level. Buying-all-NO is that
bias portfolio-wrapped: same EV per dollar, LOWER variance, but the SAME thin-market capacity cap (you
must fill every leg in thin books) and no higher EV. No capacity or edge gain over single-longshot selling.

**Verdict:** not a new tradable edge. The headline overrounds are the classic non-exclusive-legs trap.
The one real Kalshi edge remains the longshot-maker harvest (~$30–150/mo, capacity-capped), now being
validated forward by `kalshi_longshot_paper.py`.
