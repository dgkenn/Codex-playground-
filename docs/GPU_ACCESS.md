# GPU access — how to run the GPU-gated work (found in the user's Drive)

## What you used before: Google Colab
Your Drive contains **`RUN_IN_COLAB.ipynb`** (folder-shared) and **`check_gpu.py`** (a `torch.cuda.is_available()`
probe) — so the prior GPU runs were on **Google Colab**. That's the accessible path.

- **Free tier:** T4 (16 GB) — enough for frozen-embedding + MIL-head fine-tuning and small encoder work.
- **Colab Pro / Pro+ (~$10–50/mo):** A100 (40 GB) / V100 — enough for real CBraMod/MORGOTH encoder fine-tuning.
- Setup: open the notebook in Colab → Runtime → Change runtime type → GPU → run `check_gpu.py` to confirm CUDA.

**Constraint I can't get around:** Colab is an *interactive browser* runtime — I cannot drive it from this
container. The working division of labor: **I write and test the training code here (CPU), push it to your Drive
/ this repo; you paste it into the Colab notebook and run it on GPU; results land back in Drive/GCS** for me to
analyze. This is exactly the CPU-feasibility → GPU-scale boundary the `vitaldb_aki/deep/README.md` already
documents.

## The other path: your GCP project `solid-sun-478318-c5`
`MOVER_CLOUD_AI_REFERENCE.md` (Drive) documents project **`solid-sun-478318-c5`**, region **`us-central1`**,
bucket `gs://mover-research-data-dean/`. Your `cloud_processor.py` scripts already deploy **Cloud Run Jobs**
(`gcloud run jobs deploy --region us-central1`), so the project can run GPU workloads via **Vertex AI custom
jobs** or a **Compute Engine GPU VM** (n1 + T4/V100, or a2 + A100). But this needs `gcloud` auth, and **this
container has no gcloud creds** (no `~/.config/gcloud`, no service-account key — confirmed). To let me drive GPU
jobs *programmatically* you'd need to either (a) drop a **service-account-key JSON** somewhere I can read (repo
or a small Drive file), or (b) run `gcloud auth application-default login` yourself and hand me an access path.
Absent that, Colab (manual) is the pragmatic route.

## Recommendation
For the EEG-FM flagship: **Colab Pro (A100) is the fastest unlock.** I build the frozen-embedding + MIL-head
pipeline CPU-side (runs end-to-end small-scale here), you run the full-scale GPU version in Colab. If you'd
rather I run GPU jobs autonomously, put a GCP service-account key where I can read it and I'll use Vertex AI in
`solid-sun-478318-c5`.

(Note: the EEG-FM flagship also needs HEEDB EEG+outcome pairing, which is credentialed-access-blocked — see
`docs/MOVER_ACCESS_AND_EXISTING_WORK.md`. GPU is necessary but not sufficient; the data-pairing wall is separate.)
