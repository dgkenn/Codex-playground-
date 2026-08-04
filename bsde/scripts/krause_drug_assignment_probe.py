#!/usr/bin/env python3
"""One-off audit script for PROBE_2026_08_02_CHALLENGE_A_STATE_LABELS.md, OPUS VERIFICATION follow-up.

Does NOT correlate any feature with anything. Only: (1) locate the drug assignment, (2) split 34
patients into propofol/dex/sleep, (3) find drug patients whose sequence returns from U, (4) report the
time gaps for any such patient so the "~100x" dismissal of 625L can be checked rather than trusted.
"""
import csv
import os
from collections import defaultdict, Counter

PATH = "bsde/results/krause_dexprosleep_allData.csv"
assert os.path.exists(PATH), f"MISSING: {PATH}"

rows = list(csv.DictReader(open(PATH)))
print(f"n rows = {len(rows)}")
print(f"columns = {list(rows[0].keys())[:6]} ... ({len(rows[0].keys())} total, no drug/condition column)")

PROP_LABELS = {"WA", "S", "U"}
DEX_LABELS = {"WA_dex", "S_dex", "U_dex"}
SLEEP_LABELS = {"WS", "N1", "N2", "N3", "R"}

by_pid = defaultdict(list)
for r in rows:
    by_pid[r["patientID"]].append(r)

print(f"n unique patientID = {len(by_pid)}")

groups = {"propofol_only": [], "dex_only": [], "both_drugs": [], "sleep_only": [], "OTHER": []}
for pid, prs in by_pid.items():
    labs = set(r["label"] for r in prs)
    has_prop = bool(labs & PROP_LABELS)
    has_dex = bool(labs & DEX_LABELS)
    has_sleep_only_no_drug = bool(labs & SLEEP_LABELS) and not has_prop and not has_dex
    if has_prop and has_dex:
        groups["both_drugs"].append(pid)
    elif has_prop:
        groups["propofol_only"].append(pid)
    elif has_dex:
        groups["dex_only"].append(pid)
    elif has_sleep_only_no_drug:
        groups["sleep_only"].append(pid)
    else:
        groups["OTHER"].append(pid)

print("\n--- THREE-WAY SPLIT (by presence of WA/S/U vs WA_dex/S_dex/U_dex vs sleep-only labels in `label` column) ---")
total = 0
for k, v in groups.items():
    print(f"{k}: {len(v)}  -> {sorted(v)}")
    total += len(v)
print(f"total = {total}")

n_drug = len(groups["propofol_only"]) + len(groups["dex_only"]) + len(groups["both_drugs"])
print(f"\nreconciliation vs probe's reported 19 propofol + 10 dex = 29 drug patients: computed drug patients = {n_drug}")
print(f"  propofol_only = {len(groups['propofol_only'])} (probe said 19)")
print(f"  dex_only = {len(groups['dex_only'])} (probe said 10)")
print(f"  both_drugs = {len(groups['both_drugs'])} (probe said 0)")

# --- Part 3: recovery among DRUG patients only ---
print("\n--- PER-DRUG-PATIENT STATE SEQUENCE (ordered by refTime, drug-arm labels only) ---")
drug_pids = groups["propofol_only"] + groups["dex_only"]
recoveries = []
for pid in sorted(drug_pids):
    prs = by_pid[pid]
    is_dex = pid in groups["dex_only"]
    arm_labels = DEX_LABELS if is_dex else PROP_LABELS
    drug_rows = [r for r in prs if r["label"] in arm_labels]
    drug_rows_sorted = sorted(drug_rows, key=lambda r: float(r["refTime"]))
    seq = [r["label"] for r in drug_rows_sorted]
    times = [float(r["refTime"]) for r in drug_rows_sorted]
    # collapse consecutive duplicate labels into blocks, keep first time of each block
    blocks = []
    for lab, t in zip(seq, times):
        if blocks and blocks[-1][0] == lab:
            continue
        blocks.append((lab, t))
    block_seq = [b[0] for b in blocks]
    # unresponsive token for this arm
    u_tok = "U_dex" if is_dex else "U"
    light_toks = {"WA_dex", "S_dex"} if is_dex else {"WA", "S"}
    recovers = False
    if u_tok in block_seq:
        u_idx = block_seq.index(u_tok)
        if any(block_seq[i] in light_toks for i in range(u_idx + 1, len(block_seq))):
            recovers = True
    if recovers:
        recoveries.append(pid)
    print(f"{pid} ({'dex' if is_dex else 'prop'}, n_rows={len(drug_rows)}): "
          f"block_seq={block_seq}  block_times={[round(b[1],4) for b in blocks]}  recovers_from_U={recovers}")

print(f"\ndrug patients total = {len(drug_pids)}")
print(f"drug patients whose block sequence returns from U to a lighter state = {len(recoveries)}: {recoveries}")

# --- Part 4: gap structure for any recovering patient ---
print("\n--- TIME-GAP AUDIT for recovering patient(s) ---")
# First: gaps between ALL consecutive block transitions across ALL drug patients (for a reference distribution)
all_gaps = []
for pid in drug_pids:
    prs = by_pid[pid]
    is_dex = pid in groups["dex_only"]
    arm_labels = DEX_LABELS if is_dex else PROP_LABELS
    drug_rows = sorted([r for r in prs if r["label"] in arm_labels], key=lambda r: float(r["refTime"]))
    seq = [(r["label"], float(r["refTime"])) for r in drug_rows]
    blocks = []
    for lab, t in seq:
        if blocks and blocks[-1][0] == lab:
            continue
        blocks.append((lab, t))
    for i in range(1, len(blocks)):
        gap = blocks[i][1] - blocks[i-1][1]
        all_gaps.append((pid, blocks[i-1][0], blocks[i][0], gap))

all_gaps_sorted = sorted(all_gaps, key=lambda x: x[3])
print(f"n block-to-block transitions across all {len(drug_pids)} drug patients = {len(all_gaps)}")
print("full distribution (pid, from, to, gap in refTime units), sorted ascending:")
for g in all_gaps_sorted:
    print(f"  {g[0]:6s} {g[1]:>7s} -> {g[2]:<7s} gap={g[3]:.6f}")

if all_gaps:
    vals = sorted(g[3] for g in all_gaps)
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    print(f"\nmedian gap (excluding nothing) = {median:.6f}, min = {vals[0]:.6f}, max = {vals[-1]:.6f}")

print("\n--- specifically 625L, since the probe singled it out ---")
if "625L" in by_pid:
    prs = by_pid["625L"]
    is_dex = "625L" in groups["dex_only"]
    print(f"625L classified as: {'dex' if is_dex else ('prop' if '625L' in groups['propofol_only'] else 'OTHER/sleep')}")
    all_labs_625 = sorted(set(r["label"] for r in prs))
    print(f"625L all labels present: {all_labs_625}")
    for r in sorted(prs, key=lambda r: float(r["refTime"])):
        pass
else:
    print("625L not present in this deposit's patientID set.")
