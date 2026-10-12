# Failure analysis of the small CPU pilot — why AUC was ~0.5–0.62 and what it teaches

Diagnostic on the frozen-CBraMod pilot (S0001, n=89, abnormal-EEG label, 12 windows/recording, µV scaling,
mean+std pooling → 400-d, linear probe). Goal: learn *why* the AUC is low, not just report it.

## Findings
| Probe | Result | Meaning |
|---|---|---|
| OOF 5-fold AUC | **0.51** | at chance |
| In-sample AUC (reg 3 / reg 0.1) | **0.98 / 1.00** | embedding trivially memorizes n=89 |
| OOF AUC across PCA dims k=2…400 | **0.46–0.53** (flat) | reducing dimensionality does NOT rescue it |
| OOF AUC across reg=1…200 | **0.51→0.475** | shrinkage does NOT rescue it |
| Amplitude-alone / duration-alone AUC | 0.52 / 0.51 | not confounds |
| Error vs metadata (dur, n_ch, amplitude, size) | identical for correct vs wrong | errors are not artifact/confound driven |
| PC1 share of embedding variance | **67.2%**; corr(PC1, amplitude) **−0.51** | embedding dominated by ONE amplitude-linked axis |
| PCs for 90% variance | **3 of 89** | the pooled embedding is very low-rank |
| High-confidence labels | 62/89 | label quality is fine |

## Diagnosis (the lesson)
It is **not** small-n variance alone (PCA + regularization don't help), **not** amplitude/artifact confounding,
**not** label noise. The frozen **mean-pooled** CBraMod embedding is **low-rank and amplitude-dominated**
(one axis = 67% of variance, ~amplitude; 3 axes = 90%). Averaging 19 channels × 30 patches × many windows
into a 400-d mean+std vector **collapses the representation onto gross signal scale and washes out the
localized/transient graphoelements** (focal slowing, epileptiform discharges, asymmetries) that define an
abnormal EEG. So the pooled vector simply doesn't carry the discriminative structure — no probe can recover
what pooling destroyed.

## What this implies for reaching published-grade AUC (~0.88–0.92, CBraMod/TUAB)
1. **Do not mean-pool the frozen tokens.** Keep the full token sequence (channels × patches × windows) and
   learn an **attention / multiple-instance head** over it (transient abnormalities are sparse-in-time → MIL).
2. **Fine-tune the encoder** end-to-end on the task — this is where CBraMod's 0.90 comes from; frozen
   features are a lower ceiling by construction.
3. **Scale n** (S0001 alone has ~34k labeled EEGs) to stabilize training and the estimate.
4. All three require **GPU** — confirming GPU is necessary, not optional: the frozen mean-pool CPU path
   discards the signal and cannot reach the target no matter how it's probed.

## Net
The pilot's job was to de-risk the pipeline and find the bottleneck. It did: pipeline + preprocessing are
correct (µV scaling validated), but the *representation* (frozen mean-pool) is the ceiling. The high-impact
finding needs the GPU training path (full-token attention/MIL head + encoder fine-tuning + large n), which
the repo's `pass1`/handoff already targets.
