"""
btc_deep_box.py -- Channel B (box-improvement) + robustness for the BTC signal.

Box bar is LOWER than a taker: we don't need to beat the mid on EV, only to use the
signal to (i) avoid opening before adverse moves (strand-avoidance) or (ii) skew side.

We don't have the full box sim here, so we test the *necessary condition*: at an early
decision minute (k=2,3), does the signal predict the SETTLEMENT-RELATIVE adverse move
better than chance, AND does conditioning reduce a strand-proxy rate?

Strand proxy: a box opened symmetrically near minute k gets stranded when spot moves
hard one way by settle. We use |settle move| and direction. If the signal can flag
"about to move adversely" it should raise directional accuracy on the subset it acts on.

Also: walk-forward robustness of dAUC_clean (3 folds) to confirm the negative is stable.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
import warnings
warnings.filterwarnings("ignore")
from btc_deep_model import load, load_cex, clean, cex_window_close, build_features


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))


def main():
    d = load(); cexraw = load_cex(); cex = dict(cexraw)
    for name in ["coinbase_1m", "okx_1m"]:
        cex[f"_{name}"] = cex_window_close(cexraw.get(name), d["ws"])
    res = d["res"]; MID = clean(d["MID"]); SP = clean(d["SP"]); SPP = clean(d["SPP"])
    N = len(res); order = np.argsort(d["ws"])

    # ---------- ROBUSTNESS: walk-forward dAUC_clean over 3 expanding folds ----------
    print("ROBUSTNESS: walk-forward dAUC_clean (AUC[mid+sig]-AUC[mid]) at k=6 and k=9")
    print(f"{'fold':>5} {'k':>2} {'n_oos':>6} {'mid_AUC':>8} {'ms_AUC':>8} {'dAUC':>8}")
    for k in [6, 9]:
        X = build_features(d, cex, k)
        for fi, (lo, hi) in enumerate([(0.40, 0.60), (0.60, 0.80), (0.80, 1.00)]):
            tr = order[: int(N * lo)]
            te = order[int(N * lo):int(N * hi)]
            if len(te) < 50:
                continue
            gbm = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05,
                                                 l2_regularization=1.0, min_samples_leaf=40, random_state=0)
            gbm.fit(X.iloc[tr], res[tr])
            ps_tr = gbm.predict_proba(X.iloc[tr])[:, 1]
            ps_te = gbm.predict_proba(X.iloc[te])[:, 1]
            lm_tr = logit(MID[tr, k]).reshape(-1, 1); lm_te = logit(MID[te, k]).reshape(-1, 1)
            am = roc_auc_score(res[te], lm_te.ravel())
            Z_tr = np.hstack([lm_tr, logit(ps_tr).reshape(-1, 1)])
            Z_te = np.hstack([lm_te, logit(ps_te).reshape(-1, 1)])
            lr = LogisticRegression(C=1.0, max_iter=2000).fit(Z_tr, res[tr])
            ams = roc_auc_score(res[te], lr.predict_proba(Z_te)[:, 1])
            print(f"{fi:>5} {k:>2} {len(te):>6} {am:>8.4f} {ams:>8.4f} {ams-am:>+8.4f}")

    # ---------- CHANNEL B: strand-avoidance / skew at early minute ----------
    # At minute k=3, box opens. "Adverse" = settle moves against the side opened.
    # Test: does signal direction at k=3 predict settle direction better than mid,
    # specifically on the HIGH-CONFIDENCE subset (where a box would skip/skew)?
    print("\nCHANNEL B: signal as strand-avoidance / skew filter (k=3 open)")
    k = 3
    X = build_features(d, cex, k)
    cut = int(N * 0.65); tr = order[:cut]; te = order[cut:]
    gbm = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05,
                                         l2_regularization=1.0, min_samples_leaf=40, random_state=0)
    gbm.fit(X.iloc[tr], res[tr])
    ps = gbm.predict_proba(X.iloc[te])[:, 1]
    midk = MID[te, k]; y = res[te]
    # strand proxy: a symmetric box stranded when |settle moved a lot|.
    # settle-relative move magnitude proxy = |res - 0.5| won't do; use mid distance from 0.5
    # Better: define "adverse for the box" as the side that ends up deep ITM/OTM.
    # Box strand rate ~ rate at which one side gets run over = rate of large directional settle.
    # We test: if box only opens when signal is UNCERTAIN (|ps-.5| small) -> avoids strong moves?
    # And whether conditioning on AGREEMENT(signal,mid) lowers wrong-side rate.
    base_dir_acc_mid = ((midk > 0.5).astype(int) == y).mean()
    base_dir_acc_sig = ((ps > 0.5).astype(int) == y).mean()
    print(f"  base directional acc: mid={base_dir_acc_mid:.3f} sig={base_dir_acc_sig:.3f}")
    agree = ((ps > 0.5) == (midk > 0.5))
    # On the AGREE subset, is wrong-side (strand) rate lower than overall?
    wrong_all = ((midk > 0.5).astype(int) != y).mean()
    wrong_agree = ((midk > 0.5).astype(int)[agree] != y[agree]).mean()
    wrong_disagree = ((midk > 0.5).astype(int)[~agree] != y[~agree]).mean()
    print(f"  wrong-side(strand-proxy) rate: all={wrong_all:.3f} | agree={wrong_agree:.3f} (n={agree.sum()}) | disagree={wrong_disagree:.3f} (n={(~agree).sum()})")
    # Skew value: when signal is confident (|ps-.5|>q), does opening only the favored side cut wrong-side?
    for q in [0.10, 0.15, 0.20]:
        conf = np.abs(ps - 0.5) > q
        if conf.sum() < 20:
            print(f"  conf>{q}: n={conf.sum()} too few"); continue
        wrong_conf = ((ps > 0.5).astype(int)[conf] != y[conf]).mean()
        print(f"  signal-confident |p-.5|>{q}: n={conf.sum()} wrong-side(open favored side)={wrong_conf:.3f}")
    # The honest comparison: mid-confident subset wrong-side (what the box already keys off)
    for q in [0.10, 0.15, 0.20]:
        confm = np.abs(midk - 0.5) > q
        if confm.sum() < 20: continue
        wrong_confm = ((midk > 0.5).astype(int)[confm] != y[confm]).mean()
        print(f"  mid-confident   |mid-.5|>{q}: n={confm.sum()} wrong-side={wrong_confm:.3f}")


if __name__ == "__main__":
    main()
