# F14 Fractional-Flatten Bug: Root Cause Analysis

## Root Cause

**NOT-WIRED-FLAG ISSUE** (not a logic bug).

The `--flatten-fractional 0.1` flag is **missing from the bot branch's live.yml** and therefore never passed to the trader process.

**Location:**
- **Bot branch live.yml:** `.github/workflows/live.yml` on `origin/claude/polymarket-bot-live-ready-vw7ut5`
- **Main branch live.yml:** `.github/workflows/live.yml` on `origin/main`

**Evidence:**

Main branch command line (has the flag):
```
python -u kalshi_trader.py --asset "$ASSET" --live --gate as --size-mode markout ... 
--close-force-s 45 --chase-unpaired-s 120 --dispose-max-give 0.25 --flatten-fractional 0.1 
--post-complete-freeze 1.5 --duration 2760
```

Bot branch command line (flag is missing):
```
python -u kalshi_trader.py --asset "$ASSET" --live --gate as --size-mode markout ... 
--close-force-s 45 --chase-unpaired-s 15 --dispose-max-give 0.25 
--post-complete-freeze 1.5 --duration 2760
```

The flag `--flatten-fractional 0.1` does not appear in the bot branch's workflow.

## Why It Never Fires

**kalshi_trader.py lines 3789–3796:**
```python
if (a.flatten_fractional > 0 and ybb is not None and yba is not None
        and tau_left < a.close_force_s
        and abs(net_delta) > a.flatten_fractional
        # genuine fractional residual only -- an exact-integer net is already fully
        # handled by the int-sized close-force/dispose-cross machinery above.
        and abs(net_delta - round(net_delta)) > 1e-9
        and not winrec.get("frac_flatten_used", False)):
```

The first guard clause requires `a.flatten_fractional > 0`.

**kalshi_trader.py line 1415–1416** (flag definition):
```python
ap.add_argument("--flatten-fractional", type=float, default=0.0,
```

Because the flag is not passed on the command line, `a.flatten_fractional` defaults to 0.0. The condition `a.flatten_fractional > 0` is always **False**, so the entire if-block never executes, and `frac_flatten_count` is never incremented.

## The Code Logic is Correct

The flatten logic in kalshi_trader.py is **not buggy**—it correctly:
- Detects fractional residuals via `abs(net_delta - round(net_delta)) > 1e-9` (line 3795)
- Thresholds by absolute magnitude: `abs(net_delta) > a.flatten_fractional` (line 3792)
- Runs only in the final `close_force_s` window (line 3791)
- Fires exactly once per window via `frac_flatten_used` flag (line 3796)
- Places a single `count_fp` taker order sized to the exact fractional position (line 3801)
- Increments telemetry: `winrec["frac_flatten_count"] = fcount_fp` (line 3803)

## PROPOSED FIX

Add `--flatten-fractional 0.1` back to the bot branch's live.yml kalshi_trader invocation.

**File:** `.github/workflows/live.yml` on branch `origin/claude/polymarket-bot-live-ready-vw7ut5`

**Change:** In the `python -u kalshi_trader.py` command line, after `--dispose-max-give 0.25`, add:

```diff
--dispose-cross --dispose-cross-s 15 --close-force-s 45 --chase-unpaired-s 15 --dispose-max-give 0.25 
+--flatten-fractional 0.1 
--post-complete-freeze 1.5 --duration 2760 \
```

This restores the flag and allows the flatten logic to execute when a fractional residual >= 0.1 lot exists in the final 45 seconds before settlement.
