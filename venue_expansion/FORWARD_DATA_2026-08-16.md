# Forward review 2026-08-10 — the counterfactual was confirmed forward; one hazard closed

Ten days on from applying the fixes. **No change to any verdict.** Two things worth recording: the
corrected forecast model was validated by genuine out-of-sample forward data, and a residual
phantom-record hazard the fix had not cleared is now closed.

## State check — the fixes held

| | |
|---|---|
| `KWX_SWITCH` | **off** (held since 08-06) |
| v2 endpoint / `_is_scoreable` present on live | yes (4 / 5 refs) |
| Order attempts | **still 4** — the bot is correctly inert |
| Near-misses | 1,206 → **1,213** (+7 in 10 days; the live runner is off, as intended) |
| Early-lock settled | 3 → 4 (gate needs 30) |

## The forecast sleeve: counterfactual confirmed by forward data

The bracket fix landed 2026-08-06, so rows dated 08-07 onward were **selected by the corrected
`bracket_prob`**. That makes them a true out-of-sample forward test of the counterfactual I ran
post-hoc on 08-06, which had predicted −0.0363/ct.

| arm | n | days | win | EV/contract | day-clustered t |
|---|---:|---:|---:|---:|---:|
| Pre-fix (buggy model) | 839 | 18 | 40.2% | −0.0387 | **−4.70** |
| **Post-fix (corrected, forward)** | **161** | **3** | 33.5% | **−0.0416** | −1.27 |
| All | 1,000 | 21 | 39.1% | −0.0392 | **−4.88** |

**The forward result (−0.0416) lands right on the counterfactual's prediction (−0.0363).** The
post-fix arm's own t is −1.27 on only 3 days — underpowered in isolation, and I am not claiming
significance from it. What it does is confirm the point estimate out of sample: fixing the model did
not move the sign, exactly as the counterfactual said.

**The bracket fix itself demonstrably worked**: rows scored against the wrong outcome fell from
**25.9% → 13.0%**. Not to zero — consistent with the IEM revision-lag residual noted in
`EDGE_SIZING_RESULT.md`.

Model skill post-fix is unchanged in character: Brier **model 0.2864** vs **market 0.1452**, against
a constant-base-rate 0.1928. **The corrected model is still worse than a constant.** Fourth
independent confirmation; the axis stays closed.

## Hazard closed: the gate was still advertising the phantom record

The `_is_scoreable` fix stops *new* rejections being scored as wins, but it never purged the two
already sitting in `kwx_forward_settled.jsonl`. Ten days later the gate still read:

```
settled fires : 2   win rate : 100.0%   EV/contract : +0.240
```

— from zero fills, already 2/30 of the way to a PASS that authorizes capital, on fabricated
evidence. Both rows are HTTP 410 rejections (`status=live_error`, `filled=null`).

Moved verbatim to `kwx_forward_phantom_quarantine.jsonl` with a reason field rather than deleted, so
the record survives for audit. The gate now reads honestly:

```
no settled paper fires yet
plan log : 0 attempted with a real fill, 0 zero-fill (empty book), 4 rejected/blocked
```

**Lesson worth generalising: fixing the code that writes bad data does not fix the bad data already
written.** Any future scoring-logic fix in this repo should be paired with a sweep of the ledger it
feeds.

## One open piece of housekeeping

The forecast sleeve's own workflow is **still running on cron** and has added 202 rows to a sleeve
that has now been killed four independent ways. It costs nothing but noise and repo churn. Disabling
`.github/workflows/kwx-forecast.yml` is the tidy end; flagged rather than done, since it is a
separate workflow from the ones already disarmed.
