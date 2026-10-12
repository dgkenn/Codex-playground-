# Data request — per-awakening experience reports for OpenNeuro ds005620

**Status: drafted 2026-07-31, NOT SENT.** To: Imad J. Bajwa (`imadjb@uio.no`) and Bjørn E. Juel
(`Bjorneju@gmail.com`), whose addresses are printed in the deposit's own `README.txt`.

**What is being asked for and why it is small.** The EEG is already public and already downloaded. The ask
is a single table: for each subject and each awakening, whether an experience was reported. No raw data
transfer, no identifiers, healthy volunteers rather than patients, and the deposit is CC0/CC-BY.

**The verification behind the request**, so that it is not asking for something already published: the
deposit was listed directly from `s3.amazonaws.com/openneuro.org/ds005620/` and read file by file.
`participants.tsv` carries an `awakenings` count (0–3) and no report column; `events.tsv` for a sedation
rest run contains one `New Segment` row; there is no `_beh` file, no phenotype directory, and six files at
the top level. `README.txt` documents `task-sed2` as "One-minute resting EEG recorded just before an
awakening" and `run-1..3` as "different awakenings in sedation" — so the recordings are labelled by
awakening, and only the outcome of each awakening is missing.

---

## Draft

> **Subject:** Request for per-awakening report labels accompanying OpenNeuro ds005620
>
> Dear Dr Bajwa and Dr Juel,
>
> I am working with your repeated-awakening propofol dataset on OpenNeuro (ds005620, "A repeated awakening
> study exploring the capacity of complexity measures to capture dreaming during propofol sedation"), and I
> am writing to ask whether the per-awakening report labels could be shared alongside it.
>
> **What I am asking for.** One table: for each subject and each awakening — the ones the recordings index
> as `task-sed run-1..3`, each preceded by its `task-sed2` minute — whether the participant reported an
> experience on being woken, and, if you are willing, a coarse content classification. Nothing beyond that.
> I am not asking for report text, for anything identifiable, or for any additional recordings.
>
> **Why.** I am testing whether measures computed from spontaneous, task-free EEG can distinguish
> unresponsiveness *with* subsequent reported experience from unresponsiveness *without* it — that is,
> whether resting activity separates arousal from cognitive processing rather than conflating them. Your
> design is unusually well suited to it, because `task-sed2` gives a clean one-minute resting window
> immediately before each awakening, so the EEG that would carry the signal is recorded before the report
> is elicited and cannot be contaminated by it. As far as I have been able to establish, no other public
> deposit pairs task-free EEG with a per-awakening report label in the same subjects.
>
> **What I would do with it.** Analysis only, no re-identification attempted, no onward sharing, and I am
> glad to work under whatever conditions you prefer. I would be happy to share the analysis code and any
> derived per-subject table back to you before anything is written up, and to have you review how the data
> and the study are described. If you would rather this were a collaboration than a data transfer, I would
> welcome that; if you would prefer acknowledgement, or co-authorship, or simply to be cited, please say
> which and I will follow it.
>
> **Two things I should be straightforward about.** This is exploratory methodological work rather than a
> funded clinical study, and I would rather say so than dress it up. And if the labels are being held back
> because they are part of work you have not yet published, please just tell me — I will wait, or drop it,
> and either is fine.
>
> With thanks for depositing the recordings in the first place; the design is what makes the question
> askable at all.
>
> [name, affiliation, contact]

---

## If this is declined, or goes unanswered

The dissociation test does not become available elsewhere, and that should be stated rather than worked
around. The fallbacks are all weaker and each is weaker than the last:

1. **E28's healthy-BCI substitution**, already running on `eegmmidb`. Motor imagery is command-following
   that produces no movement, which is structurally the right shape — but a healthy subject who cannot drive
   a BCI is not unconscious and has no reported experience at stake. It tests a different dissociation.
2. **The Chennu propofol cohort** (`chennu_features_v3.csv`, 20 subjects, four levels) has behavioural
   performance at each level but no experience report, so it separates responsiveness from drug level and
   not experience from arousal. That is E05's contrast, already run.
3. **Nothing in the anaesthesia deposits currently held carries a report label.** VitalDB, DOSE-I, the
   Krause deposit and ds004541 are all responsiveness-labelled at best. This is worth stating plainly in any
   write-up that touches Brief 01's separation of arousal from cognitive processing: the separation has not
   been tested here, and the reason is a missing column rather than a missing analysis.
