"""dashboard.py -- renders gha_data/DASHBOARD.html: a single self-contained (inline CSS, no external
assets, no JS chart libs -- hand-rolled inline SVG), dark-friendly ops snapshot of the shadow A/B.

Sections:
  (a) 30-day trend of daily edge-vs-baseline for the top arms (inline SVG line chart)
  (b) latest day-clustered leaderboard, parsed from the newest gha_data/<date>/SUMMARY.txt
  (c) decay-watch status line (same SUMMARY.txt)
  (d) live-recon summary, if gha_data/live_recon_*.jsonl(.gz) rows exist (schema not finalized yet --
      parsed leniently; absent gracefully)
  (e) verdict-ledger stats (verdict_ledger.compute_stats)

Every section is independently try/except-guarded: a bug or missing input in one section renders a
"not available" note instead of failing the whole page, per the "must run green with whatever subset
of data exists" requirement.

    python dashboard.py     # writes gha_data/DASHBOARD.html
"""
from __future__ import annotations

import glob
import html
import math
import os
import re
from datetime import datetime, timezone

from dataio import jl_glob, jl_lines

OUT_PATH = "gha_data/DASHBOARD.html"
BASELINE = "baseline"
ANCHOR_VARIANTS = ["av_stoikov", "mo_size", "micro_gate"]     # always-shown context arms, if present
MAX_SERIES = 6
TREND_DAYS = 30

# Categorical palette (validated: dataviz skill reference palette; fixed hue order = identity, never
# reassigned by rank). Light / dark pair per slot.
SERIES_COLORS = [
    ("#2a78d6", "#3987e5"),   # 1 blue
    ("#1baf7a", "#199e70"),   # 2 aqua
    ("#eda100", "#c98500"),   # 3 yellow
    ("#008300", "#008300"),   # 4 green
    ("#4a3aa7", "#9085e9"),   # 5 violet
    ("#e34948", "#e66767"),   # 6 red
]


def _utc_date(ws: float) -> str:
    return datetime.fromtimestamp(ws, timezone.utc).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------
# (a) 30-day trend
# ------------------------------------------------------------------------------------------------

def load_windows() -> dict:
    """Same de-dupe scheme as aggregate_shadow.py / promotion_check.py: (asset,tenor,ws) -> {variant: net}."""
    by_ws: dict = {}
    for fp in jl_glob("gha_data/shadow_windows_*.jsonl"):
        for row in jl_lines(fp):
            ws = row.get("ws")
            if ws is None or row.get("resolved_up") is None:
                continue
            slot = by_ws.setdefault((row.get("asset", "btc"), row.get("tenor_min", 15), ws), {})
            for k, v in row.items():
                if isinstance(v, dict) and "net" in v:
                    slot.setdefault(k, v["net"])
    return by_ws


def day_means_by_variant(by_ws: dict, base: str = BASELINE) -> tuple[dict[str, dict[str, float]], list[str]]:
    """variant -> {date: mean(variant.net - base.net)}, plus the sorted list of all UTC dates seen."""
    day_deltas: dict[str, dict[str, list[float]]] = {}
    all_days: set[str] = set()
    for (_a, _t, ws), s in by_ws.items():
        d = _utc_date(ws)
        all_days.add(d)
        if base not in s:
            continue
        for v, net in s.items():
            if v == base:
                continue
            day_deltas.setdefault(v, {}).setdefault(d, []).append(net - s[base])
    out = {v: {d: sum(xs) / len(xs) for d, xs in dd.items()} for v, dd in day_deltas.items()}
    return out, sorted(all_days)


def pick_series(day_means: dict[str, dict[str, float]], trend_days: list[str]) -> list[str]:
    """ANCHOR_VARIANTS first (if present), then remaining slots filled by |mean edge over trend_days|
    descending, up to MAX_SERIES -- fixed identity ordering (anchors), not re-ranked run to run."""
    present = [v for v in ANCHOR_VARIANTS if v in day_means]
    scored = []
    for v, dm in day_means.items():
        if v in present:
            continue
        vals = [dm[d] for d in trend_days if d in dm]
        if not vals:
            continue
        scored.append((abs(sum(vals) / len(vals)), v))
    scored.sort(reverse=True)
    for _, v in scored:
        if len(present) >= MAX_SERIES:
            break
        present.append(v)
    return present[:MAX_SERIES]


def render_trend_svg(day_means: dict[str, dict[str, float]], all_days: list[str]) -> str:
    trend_days = all_days[-TREND_DAYS:]
    if not trend_days:
        return '<p class="muted">no shadow-window data yet -- trend chart pending.</p>'
    series = pick_series(day_means, trend_days)
    if not series:
        return '<p class="muted">no variant has paired data with baseline yet -- trend chart pending.</p>'

    W, H = 720, 260
    ML, MR, MT, MB = 46, 12, 14, 28
    plot_w, plot_h = W - ML - MR, H - MT - MB

    all_vals = [v for name in series for d, v in day_means[name].items() if d in trend_days]
    lo, hi = min(all_vals + [0.0]), max(all_vals + [0.0])
    pad = (hi - lo) * 0.1 or 1.0
    lo, hi = lo - pad, hi + pad

    def x_of(i: int) -> float:
        return ML + (i / max(len(trend_days) - 1, 1)) * plot_w

    def y_of(v: float) -> float:
        return MT + (1 - (v - lo) / (hi - lo)) * plot_h

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="30-day trend of daily edge vs baseline" '
             f'class="viz-root" xmlns="http://www.w3.org/2000/svg">']
    # gridlines (recessive) + zero baseline (bolder)
    n_grid = 4
    for i in range(n_grid + 1):
        gy = MT + i * plot_h / n_grid
        parts.append(f'<line x1="{ML}" y1="{gy:.1f}" x2="{ML+plot_w}" y2="{gy:.1f}" class="grid"/>')
    zy = y_of(0.0)
    parts.append(f'<line x1="{ML}" y1="{zy:.1f}" x2="{ML+plot_w}" y2="{zy:.1f}" class="axis"/>')
    parts.append(f'<text x="{ML-6}" y="{zy+3:.1f}" text-anchor="end" class="tick">0</text>')
    parts.append(f'<text x="{ML-6}" y="{MT+4}" text-anchor="end" class="tick">{hi:.1f}</text>')
    parts.append(f'<text x="{ML-6}" y="{MT+plot_h}" text-anchor="end" class="tick">{lo:.1f}</text>')
    # x-axis date labels: first, middle, last only (dense chart, avoid label collision)
    for i in (0, len(trend_days) // 2, len(trend_days) - 1):
        parts.append(f'<text x="{x_of(i):.1f}" y="{H-6}" text-anchor="middle" class="tick">{trend_days[i][5:]}</text>')

    for si, name in enumerate(series):
        light, dark = SERIES_COLORS[si % len(SERIES_COLORS)]
        dm = day_means[name]
        pts = [(i, dm[d]) for i, d in enumerate(trend_days) if d in dm]
        if not pts:
            continue
        poly = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in pts)
        parts.append(f'<polyline points="{poly}" fill="none" stroke="var(--s{si})" stroke-width="2" '
                      f'stroke-linecap="round" stroke-linejoin="round"/>')
        lx, ly = x_of(pts[-1][0]), y_of(pts[-1][1])
        parts.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="var(--s{si})"/>')
    parts.append("</svg>")

    style_vars = "".join(f"--s{i}:{light};" for i, (light, _dark) in enumerate(SERIES_COLORS))
    dark_vars = "".join(f"--s{i}:{dark};" for i, (_light, dark) in enumerate(SERIES_COLORS))
    legend = "".join(
        f'<span class="legend-item"><i style="background:var(--s{si})"></i>{html.escape(name)}'
        f'<span class="muted"> ({day_means[name].get(trend_days[-1], float("nan")):+.2f}/day latest)</span></span>'
        for si, name in enumerate(series))
    return (f'<div class="viz-root" style="{style_vars}">'
            f'<style>@media (prefers-color-scheme: dark) {{ .viz-root {{ {dark_vars} }} }}</style>'
            f'{"".join(parts)}<div class="legend">{legend}</div></div>')


# ------------------------------------------------------------------------------------------------
# (b) + (c) latest SUMMARY.txt: day-clustered leaderboard + decay-watch
# ------------------------------------------------------------------------------------------------

def newest_summary_path() -> str | None:
    dated = sorted(glob.glob("gha_data/*/SUMMARY.txt"))
    if dated:
        return dated[-1]
    return "gha_data/SUMMARY.txt" if os.path.exists("gha_data/SUMMARY.txt") else None


def parse_leaderboard(text: str) -> tuple[str, list[dict]]:
    """Prefer the day-clustered section if present (variant/n_days/mean-delta/clust-t/days+); else
    fall back to the window-level leaderboard (variant/net/delta/paired-t/gross/gross-t). Returns
    (kind, rows)."""
    lines = text.splitlines()
    # day-clustered section: header line contains "clust t"
    for i, ln in enumerate(lines):
        if "clust t" in ln and "variant" in ln:
            rows = []
            for ln2 in lines[i + 1:]:
                if not ln2.strip():
                    break
                toks = ln2.split()
                if len(toks) < 4:
                    continue
                name = toks[0]
                nums = toks[1:]
                try:
                    n_days = int(nums[0]); mean_d = float(nums[1])
                    t = nums[2] if nums[2] == "n/a" else float(nums[2])
                    pos = nums[3] if len(nums) > 3 else ""
                except Exception:
                    continue
                rows.append({"name": name, "n_days": n_days, "mean_delta": mean_d, "t": t, "pos": pos})
            if rows:
                return "day-clustered", rows
    # fallback: main window-level table (header line starts with "variant")
    for i, ln in enumerate(lines):
        if ln.split()[:1] == ["variant"]:
            rows = []
            for ln2 in lines[i + 1:]:
                if not ln2.strip():
                    break
                edge = ln2.strip().endswith("<edge>")
                toks = ln2.replace("<edge>", "").split()
                if len(toks) < 2:
                    continue
                name = toks[0]
                nums = toks[1:]
                try:
                    fnums = [float(x) if x != "n/a" else float("nan") for x in nums]
                except Exception:
                    continue
                row = {"name": name, "net": fnums[0], "edge": edge}
                if len(fnums) >= 5:
                    row["delta"], row["t"], row["gross"], row["gross_t"] = fnums[1:5]
                elif len(fnums) >= 3:
                    row["gross"], row["gross_t"] = fnums[1], fnums[2]
                rows.append(row)
            if rows:
                return "window-level (day-clustered section not present in this SUMMARY.txt)", rows
    return "none", []


def render_leaderboard() -> str:
    path = newest_summary_path()
    if not path:
        return '<p class="muted">no SUMMARY.txt found yet.</p>'
    try:
        with open(path) as fh:
            text = fh.read()
    except Exception as e:
        return f'<p class="muted">could not read {html.escape(path)}: {html.escape(str(e))}</p>'
    kind, rows = parse_leaderboard(text)
    header = f'<p class="muted">source: {html.escape(path)} &middot; kind: {html.escape(kind)}</p>'
    if not rows:
        return header + '<p class="muted">leaderboard table not parseable from this SUMMARY.txt.</p>'
    if kind == "day-clustered":
        row_htmls = []
        for r in rows[:15]:
            t_s = r["t"] if r["t"] == "n/a" else f'{r["t"]:+.2f}'
            row_htmls.append(
                f'<tr><td>{html.escape(r["name"])}</td><td class="num">{r["n_days"]}</td>'
                f'<td class="num">{r["mean_delta"]:+.3f}</td>'
                f'<td class="num">{t_s}</td>'
                f'<td class="num">{html.escape(str(r["pos"]))}</td></tr>')
        body = "".join(row_htmls)
        table = (f'<table><thead><tr><th>variant</th><th>n_days</th><th>mean &Delta;/day</th>'
                 f'<th>clust t</th><th>days+</th></tr></thead><tbody>{body}</tbody></table>')
    else:
        body = []
        for r in rows[:20]:
            delta = r.get("delta"); t = r.get("t")
            delta_s = "" if delta is None or delta != delta else f"{delta:+.3f}"
            t_s = "" if t is None or t != t else f"{t:+.2f}"
            gross = r.get("gross", float("nan")); gross_t = r.get("gross_t", float("nan"))
            flag = ' class="edge-flag"' if r.get("edge") else ""
            body.append(f'<tr{flag}><td>{html.escape(r["name"])}</td><td class="num">{r["net"]:+.3f}</td>'
                        f'<td class="num">{delta_s}</td><td class="num">{t_s}</td>'
                        f'<td class="num">{gross:+.3f}</td><td class="num">{gross_t:+.2f}</td></tr>')
        table = (f'<table><thead><tr><th>variant</th><th>net/win</th><th>&Delta; vs base</th>'
                 f'<th>paired t</th><th>GROSS/win</th><th>gross t</th></tr></thead>'
                 f'<tbody>{"".join(body)}</tbody></table>')
    return header + table


def render_decay_watch() -> str:
    path = newest_summary_path()
    if not path:
        return '<p class="muted">no SUMMARY.txt found yet.</p>'
    try:
        with open(path) as fh:
            text = fh.read()
    except Exception as e:
        return f'<p class="muted">could not read {html.escape(path)}: {html.escape(str(e))}</p>'
    m = re.search(r"^(DECAY-ALERT.*|deploy-watch:.*)$", text, re.MULTILINE)
    if not m:
        return ('<p class="muted">no decay-watch line in the latest SUMMARY.txt (older collector run, '
                 'or insufficient trailing-14-day data).</p>')
    line = m.group(1).strip()
    cls = "status-critical" if line.startswith("DECAY-ALERT") else "status-good"
    return f'<p class="{cls}">{html.escape(line)}</p>'


# ------------------------------------------------------------------------------------------------
# (d) live-recon summary (schema not finalized -- lenient, absence-safe)
# ------------------------------------------------------------------------------------------------

def render_live_recon() -> str:
    files = jl_glob("gha_data/live_recon_*.jsonl")
    if not files:
        return '<p class="muted">no gha_data/live_recon_*.jsonl yet -- live fills reconciliation pending.</p>'
    rows = [r for fp in files for r in jl_lines(fp)]
    if not rows:
        return '<p class="muted">live_recon files present but no parseable rows yet.</p>'

    n = len(rows)
    fill_flags = [bool(r[k]) for r in rows for k in r if k.lower() in ("filled", "is_filled")
                  and isinstance(r[k], bool)]
    fill_rate_vals = [r[k] for r in rows for k in r if "fill_rate" in k.lower() and isinstance(r[k], (int, float))]
    realized = [r[k] for r in rows for k in r if "realiz" in k.lower() and isinstance(r[k], (int, float))]
    shadow = [r[k] for r in rows for k in r if "shadow" in k.lower() and isinstance(r[k], (int, float))]

    lines = [f'<p>{n} live_recon row(s) across {len(files)} file(s).</p>']
    if fill_flags:
        lines.append(f'<p>fill rate: {sum(fill_flags) / len(fill_flags):.1%} ({sum(fill_flags)}/{len(fill_flags)})</p>')
    elif fill_rate_vals:
        lines.append(f'<p>fill rate: {sum(fill_rate_vals) / len(fill_rate_vals):.1%} (avg of {len(fill_rate_vals)} rows)</p>')
    else:
        lines.append('<p class="muted">fill-rate field not found in these rows (schema may differ; best-effort parse).</p>')
    if realized and shadow:
        lines.append(f'<p>realized net (mean): {sum(realized)/len(realized):+.3f} &middot; '
                      f'shadow net (mean): {sum(shadow)/len(shadow):+.3f} &middot; '
                      f'realized&minus;shadow: {sum(realized)/len(realized) - sum(shadow)/len(shadow):+.3f}</p>')
    else:
        lines.append('<p class="muted">realized-vs-shadow net fields not found in these rows yet.</p>')
    return "".join(lines)


# ------------------------------------------------------------------------------------------------
# (e) verdict-ledger stats
# ------------------------------------------------------------------------------------------------

def render_verdict_stats() -> str:
    try:
        import verdict_ledger
        fams = verdict_ledger.compute_stats()
    except Exception as e:
        return f'<p class="muted">verdict_ledger unavailable: {html.escape(str(e))}</p>'
    if not fams:
        return '<p class="muted">verdicts.jsonl is empty -- run `python verdict_ledger.py --seed`.</p>'
    body = []
    for fam in sorted(fams, key=lambda f: -fams[f]["tested"]):
        b = fams[fam]
        body.append(f'<tr><td>{html.escape(fam)}</td><td class="num">{b["tested"]}</td>'
                     f'<td class="num">{b["winner"]}</td><td class="num">{b["pruned"]}</td>'
                     f'<td class="num">{b["watch"]}</td><td class="num">{b["testing"]}</td></tr>')
    total_tested = sum(b["tested"] for b in fams.values())
    total_won = sum(b["winner"] for b in fams.values())
    table = (f'<table><thead><tr><th>family</th><th>tested</th><th>winner</th><th>pruned</th>'
             f'<th>watch</th><th>testing</th></tr></thead><tbody>{"".join(body)}</tbody></table>')
    foot = (f'<p class="muted">{total_won}/{total_tested} arms tested are current winners (excl. baseline) '
            f'-- the multiple-testing denominator.</p>')
    return table + foot


# ------------------------------------------------------------------------------------------------
# page assembly
# ------------------------------------------------------------------------------------------------

PAGE_TMPL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shadow A/B Dashboard</title>
<style>
  :root {{
    --surface-1: #fcfcfb; --page: #f9f9f7; --text-primary: #0b0b0b; --text-secondary: #52514e;
    --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
    --good: #0ca30c; --critical: #d03b3b;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface-1: #1a1a19; --page: #0d0d0d; --text-primary: #ffffff; --text-secondary: #c3c2b7;
      --muted: #898781; --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
      --good: #0ca30c; --critical: #e66767;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--page); color: var(--text-primary);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 0 0 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: .04em; }}
  .generated {{ color: var(--muted); font-size: 13px; margin: 0 0 24px; }}
  section {{
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
    padding: 18px 20px; margin-bottom: 18px; max-width: 900px; overflow-x: auto;
  }}
  .muted {{ color: var(--muted); }}
  .status-good {{ color: var(--good); font-weight: 600; }}
  .status-critical {{ color: var(--critical); font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: 13.5px; }}
  th, td {{ text-align: left; padding: 5px 10px; border-bottom: 1px solid var(--grid); white-space: nowrap; }}
  th {{ color: var(--text-secondary); font-weight: 600; }}
  td.num, th.num {{ text-align: right; }}
  tr.edge-flag td:first-child {{ font-weight: 600; }}
  .viz-root svg {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .axis {{ stroke: var(--axis); stroke-width: 1; }}
  .tick {{ fill: var(--muted); font-size: 10px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; font-size: 12.5px; color: var(--text-secondary); }}
  .legend-item {{ display: inline-flex; align-items: center; gap: 5px; }}
  .legend-item i {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
</style>
</head><body>
<h1>Kalshi maker-box shadow A/B -- dashboard</h1>
<p class="generated">generated {generated} UTC</p>

<section><h2>30-day trend: daily edge vs baseline (top arms)</h2>{trend}</section>
<section><h2>Latest leaderboard</h2>{leaderboard}</section>
<section><h2>Decay watch</h2>{decay}</section>
<section><h2>Live-recon (real fills vs shadow)</h2>{live_recon}</section>
<section><h2>Verdict ledger -- family-wise tested/won/lost</h2>{verdicts}</section>

</body></html>
"""


def _safe(label: str, fn) -> str:
    try:
        return fn()
    except Exception as e:
        return f'<p class="muted">{html.escape(label)} unavailable: {html.escape(str(e))}</p>'


def build() -> str:
    by_ws = _safe_load()
    trend = _safe("trend chart", lambda: render_trend_svg(*day_means_by_variant(by_ws)) if by_ws
                   else '<p class="muted">no shadow-window data under gha_data/ yet.</p>')
    leaderboard = _safe("leaderboard", render_leaderboard)
    decay = _safe("decay watch", render_decay_watch)
    live_recon = _safe("live-recon", render_live_recon)
    verdicts = _safe("verdict ledger", render_verdict_stats)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return PAGE_TMPL.format(generated=generated, trend=trend, leaderboard=leaderboard,
                             decay=decay, live_recon=live_recon, verdicts=verdicts)


def _safe_load() -> dict:
    try:
        return load_windows()
    except Exception:
        return {}


def main() -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    html_out = build()
    with open(OUT_PATH, "w") as fh:
        fh.write(html_out)
    print(f"dashboard.py: wrote {OUT_PATH} ({len(html_out)} bytes)")


if __name__ == "__main__":
    main()
