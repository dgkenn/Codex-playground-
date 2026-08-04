# License Table — Summary Notes (2026-07-29)

## 1. Verification counts (12 datasets)

- **Fully verified** (primary license text read; commercial terms determined): **7** —
  figshare_doc_rest (CC BY 4.0), icare (CC BY-NC-SA 4.0), openneuro_ds005620 (CC0),
  chennu_propofol (CC BY 2.0 UK), physionet_eegmmidb (ODC-BY 1.0), openneuro_ds007554 (CC0),
  physionet_sleep_edfx (ODC-BY 1.0).
- **Partly verified** (primary text read, material caveats remain): **2** —
  bath_pdoc_mi (redistribution/access-request confirmed; commercial use never addressed by
  the source), vitaldb (Registration Agreement read, but the linked full Data Use Agreement
  could not be fetched — moderate, not high, confidence).
- **Entirely unverified** (no primary source text obtained): **3** —
  ebrains_tmseeg_doc (Knowledge Graph is a JS SPA; static fetch returns nothing),
  shhs and mesa_sleep (sleepdata.org returned HTTP 503 on every attempt).

## 2. Datasets BLOCKED for commercial use

- **icare** — CC BY-NC-SA 4.0 explicitly prohibits commercial use (read directly). The one
  unambiguous commercial blocker in the registry.
- **vitaldb** — moderate-confidence reading of the Registration Agreement shows a CC
  BY-NC-SA 4.0 base plus a bespoke "research and development purposes only" clause and a
  redistribution restriction. Conservative reading: blocked pending legal confirmation.
- **bath_pdoc_mi, ebrains_tmseeg_doc, shhs, mesa_sleep** — not proven permissive. Under this
  project's governing rule, unverified commercial terms mean these four are **effectively
  blocked by default**, regardless of whether a real restriction exists.

Confirmed CLEAR for commercial use (explicit, no field-of-use restriction): figshare_doc_rest,
openneuro_ds005620, chennu_propofol, physionet_eegmmidb, openneuro_ds007554, physionet_sleep_edfx.

## 3. Questions that need a lawyer, not more web fetching

1. **vitaldb**: read agreement cites CC BY-NC-SA 4.0 plus bespoke Section 5 clauses; a lawyer
   must read the *executed* Registration Agreement and the linked DUA (unreachable here) and
   decide whether a trained *model* counts as a restricted "Derivative."
2. **icare**: does a model trained on I-CARE count as "Adapted Material" under CC BY-NC-SA's
   ShareAlike clause, forcing the resulting model to be released non-commercially?
3. **bath_pdoc_mi**: access requires agreeing to unspecified "data use conditions" by request —
   need the actual agreement text from Bath's data custodians before assessing commercial use.
4. **shhs / mesa_sleep**: NSRR's DAUA reportedly handles commercial use per-dataset, and MESA
   per-subject-consent — needs an NSRR account holder plus legal review of platform-wide rights.
5. **ebrains_tmseeg_doc**: license field was never actually read (JS-rendered page); needs a
   human in a browser or the authenticated KG API.

## 4. Not legal advice

This table is **engineering due diligence only** — a record of which license/DUA texts were
actually read and what they say, so no biomarker gets promoted on an unverified license by
accident. It is **not a legal opinion**, was not prepared by an attorney, and does not account
for jurisdiction, IRB/human-subjects terms layered atop the license, or whether trained model
weights count as a "derivative" of training data. Every BLOCKED/UNVERIFIED row, and every row's
clinical-use and model-weight column, needs real legal sign-off before commercial shipping.

## Correction 2026-07-31 — openneuro_ds005620 states TWO different licences inside the same deposit

`LICENSE_TABLE.csv` records `CC0 1.0`, verified on 2026-07-29 by reading the deposit's own
`dataset_description.json` from the OpenNeuroDatasets GitHub mirror. That reading is correct and the file
does say `"License": "CC0"`. **But `README.txt` in the same deposit says "This dataset is licensed under
CC-BY-4.0."** Both were fetched directly from `s3.amazonaws.com/openneuro.org/ds005620/` with `curl` and
read in full — not summarised by a fetch tool (rules 25 and 39).

The verification note in `LICENSE_TABLE.csv` claims the licence was "read directly from the dataset's own
BIDS metadata, not inferred". That remains true, and it is now also incomplete: **one file in the deposit
was read and the other was not, and they disagree.** The row is left as it is rather than rewritten, because
the evidence it cites is real; this note is where a reader relying on the claim will find the rest of it
(rule 3).

**Operational consequence: treat ds005620 as CC-BY-4.0, the stricter of the two.** Attribution satisfies
CC-BY and is permitted (though not required) under CC0, so honouring the stricter reading is compatible with
either being the true licence and costs nothing. Do not rely on the CC0 public-domain dedication for
anything — in particular not for any claim that attribution can be dropped from a derived artefact.

**The general lesson, which belongs in every licence verification from here on: read every file in a deposit
that could carry a licence statement, not the first one that answers the question.** `dataset_description.json`
looked authoritative because it is machine-readable and BIDS-canonical, and that is exactly why the README
was never opened.
