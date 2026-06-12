"""
freeze_combo_tox.py
Fit a frozen logistic regression for the combo_tox gate on ALL historical data.
Features: vpin, take_n, d1_maxrun, d2_lambda, d1_nruns, d4_roundfrac, d5_sweep
Only rows where ALL features + vpin are non-NaN are used for fitting.
THRESH: calibrated to match vpin<=0.40 keep-fraction on OOS (last 40% by time).
Prints ONLY the numbers needed to freeze the model.
"""
import numpy as np, pandas as pd, sys, os
os.chdir("/home/user/Codex-playground-")
sys.path.insert(0, '/home/user/Codex-playground-')
from informed_detectors import build, ASSETS
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

COMBO_FEATS = ["vpin", "take_n", "d1_maxrun", "d2_lambda", "d1_nruns", "d4_roundfrac", "d5_sweep"]

# 1. Build all windows for all 4 assets
print("Building windows...", flush=True)
dfs = []
for a in ASSETS:
    df_a = build(a)
    print(f"  {a}: {len(df_a)} windows", flush=True)
    dfs.append(df_a)

df = pd.concat(dfs, ignore_index=True).sort_values("ws").reset_index(drop=True)
print(f"Total windows: {len(df)}, strand rate: {df.stranded.mean():.3f}", flush=True)

# 2. Drop rows with any NaN in features (all 7 features must be present)
mask_clean = df[COMBO_FEATS].notna().all(axis=1)
df_clean = df[mask_clean].reset_index(drop=True)
n_clean = len(df_clean)
print(f"Clean rows (all 7 feats non-NaN): {n_clean} / {len(df)}", flush=True)

X_all = df_clean[COMBO_FEATS].values.astype(float)
y_all = df_clean["stranded"].values.astype(float)

# 3. OOS = last 40% by time (on clean rows, already sorted by ws)
oos_start = int(n_clean * 0.6)
is_mask  = np.zeros(n_clean, dtype=bool); is_mask[:oos_start] = True
oos_mask = ~is_mask

# 4. Compute vpin<=0.40 keep fraction on OOS (only rows where vpin is non-NaN --
#    since we already required all features non-NaN, vpin is always present here)
vpin_oos = df_clean.loc[oos_mask, "vpin"].values
t32_keep_frac = float(np.mean(vpin_oos <= 0.40))
print(f"\nOOS n={oos_mask.sum()} | vpin<=0.40 keep fraction: {t32_keep_frac:.4f}", flush=True)

# 5. Fit logistic on ALL clean rows (frozen model)
sc = StandardScaler()
X_scaled = sc.fit_transform(X_all)
lr = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")
lr.fit(X_scaled, y_all)

intercept = float(lr.intercept_[0])
coefs = lr.coef_[0].tolist()
means = sc.mean_.tolist()
stds  = sc.scale_.tolist()

# 6. Find combo score threshold that keeps the same fraction on OOS
scores_all = lr.predict_proba(X_scaled)[:, 1]
scores_oos = scores_all[oos_mask]
y_oos = y_all[oos_mask]

# keep LOW-score windows (low toxicity probability); threshold = quantile at keep_frac
THRESH = float(np.quantile(scores_oos, t32_keep_frac))
kept_combo = scores_oos <= THRESH
kept_vpin  = vpin_oos <= 0.40

# ---- OUTPUT ----
print("\n========== FROZEN COMBO_TOX LOGISTIC ==========")
print(f"\nFeatures:  {COMBO_FEATS}")
print(f"Fit rows:  {n_clean}  (all 7 features non-NaN)")
print(f"OOS rows:  {oos_mask.sum()}")

print(f"\nINTERCEPT:  {intercept:.6f}")

print(f"\nCOEFFICIENTS (standardized):")
for f, c in zip(COMBO_FEATS, coefs):
    print(f"  {f:16s}: {c:+.6f}")

print(f"\nSTANDARDIZATION MEANS:")
for f, m in zip(COMBO_FEATS, means):
    print(f"  {f:16s}: {m:.6f}")

print(f"\nSTANDARDIZATION STDS:")
for f, s in zip(COMBO_FEATS, stds):
    print(f"  {f:16s}: {s:.6f}")

print(f"\nTHRESHOLD:  {THRESH:.6f}")
print(f"  (vpin<=0.40 OOS keep fraction = {t32_keep_frac:.4f})")
print(f"  combo gate actual keep = {kept_combo.mean():.4f}")

print(f"\nSANITY (OOS):")
print(f"  baseline strand              = {y_oos.mean():.4f}")
print(f"  vpin gate strand (kept={kept_vpin.mean():.3f})  = {y_oos[kept_vpin].mean():.4f}")
print(f"  combo gate strand (kept={kept_combo.mean():.3f}) = {y_oos[kept_combo].mean():.4f}")

print(f"\n=== COPY-PASTE BLOCK ===")
print(f'COMBO_INTERCEPT = {intercept:.6f}')
print("COMBO_COEFS = {")
for f, c in zip(COMBO_FEATS, coefs):
    print(f'    "{f}": {c:.6f},')
print("}")
print("COMBO_MEANS = {")
for f, m in zip(COMBO_FEATS, means):
    print(f'    "{f}": {m:.6f},')
print("}")
print("COMBO_STDS = {")
for f, s in zip(COMBO_FEATS, stds):
    print(f'    "{f}": {s:.6f},')
print("}")
print(f'COMBO_THRESH = {THRESH:.6f}')
