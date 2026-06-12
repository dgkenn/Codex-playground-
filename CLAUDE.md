# CLAUDE.md — operating guide for the Kalshi maker-box bot

## Token discipline (READ FIRST — the standing constraint)

The expensive resource is the **main agent's context window**. Every large tool result,
file dump, and exploratory read stays there for the rest of the session. The operator has
flagged token burn explicitly. Default to delegation and compact helpers.

### Delegate to a subagent (`Agent` tool, `model: "haiku"` or `"sonnet"`) when the task is:
- **Token-heavy but conclusion-light**: tape replays, parquet scans, log greps, `box_lab.py`
  sweeps — anything whose raw output is large but where you only need the numbers back.
  Tell the subagent to return ONLY the summary table / verdict, not the dumps.
- **Broad search / exploration**: "where is X handled", "find all callers of Y" → `Explore`
  or a `general-purpose` subagent on haiku. Don't read 5 files into main context to find one.
- **Mechanical multi-file edits** with a clear spec: rename, signature change, repetitive patch.
- **CI / GitHub run inspection**: NEVER pull `mcp__github__actions_list` into main context —
  its results have run 120–135 KB (and were read twice). Use `python watch_continuity.py`
  (git-based, no auth, compact) for collector freshness. If you truly need run-level detail,
  delegate the MCP call to a subagent and have it report back the 3 fields you need.

### Keep on the main (expensive) model — judgment that shouldn't be re-derived:
- Money-path decisions: sizing, gates, risk caps, anything touching live order placement.
- Strategy synthesis and the final written answer to the operator.
- Git commit/push of trader code, and the go/no-go to arm live trading.

### Cheap-path defaults (use these instead of the heavy version):
- Collector alive? → `python watch_continuity.py` (NOT the GHA MCP blob).
- Live fill stats / scorecard → `python kalshi_scorecard.py btc` (pre-aggregated).
- Reading a 1000+ line file → `Grep` for the symbol, then `Read` with `offset/limit` on the
  hit. Don't read whole files to find one function.
- Big analysis scripts already print COMPACT summaries by design — keep them that way; never
  `print(df)` a full frame into stdout.

## What this bot is

A settlement-hedged **maker-box harvester** on Kalshi 15-min crypto binaries (KXBTC15M).
Rests YES and NO bids; when both fill (`b_y + b_n < $1`) the pair pays $1 at expiry,
risk-free. The boxes ARE the profit; unpaired inventory is the only real risk.

- Strategy verdicts + mechanism evidence: `BOX_PLAYBOOK.md`
- Loss post-mortem + the fixes: `LIVE_POSTMORTEM.md`
- Master fee/queue/sizing doc: `KALSHI.md`
- Live dashboard: `kalshi_scorecard.py`

## Key invariants (don't relearn these the hard way)
- CRYPTO15M maker fee = **$0** (confirmed on every live fill). `--fee-mult` machinery is for
  other series only.
- Stop-loss exits LOSE (tested on 20,318 fills); risk control is SIZE/pairing, never exits.
- `--max-net 1` (strict pairing), `--min-lock 0`, `--min-spread 0.01`, `--max-fills-side 4`
  are the deployed defaults, each tape-backed in `BOX_PLAYBOOK.md`.
- Live trading is controlled by the LIGHT SWITCH (`SWITCH.md`): the `LIVE_SWITCH` file (on|off),
  honored by `.github/workflows/live.yml` (cloud, always-on) and `live_supervisor.sh` (VM). Toggle
  with `./live_switch.sh on|off`. Re-arm after a kill = `./live_switch.sh on` (clears the sentinel).
  Never auto-rearm after a loss-limit/toxic kill; the operator flips the switch.
- SINGLE-TRADER INVARIANT: exactly one trader per account, ever. Start local trading ONLY via
  `./live_loop.sh`; kill by PID (never `pkill -f` — it matches your own shell); verify with
  `./bot_status.sh` after any restart. Full control stack: CONTROLS.md (L0-L6).
- This container is ephemeral; the durable home is an always-free VM (Oracle us-east).
