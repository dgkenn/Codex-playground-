# Data request — dexmedetomidine/propofol EEG cohort (Turku, Kallionpää et al. 2020, NCT01889004)

**Status: drafted 2026-07-31, NOT SENT.** To the corresponding authors of Kallionpää RE, Valli K,
Scheinin A, Långsjö J, Maksimow A, et al., "Alpha band frontal connectivity is a state-specific
electroencephalographic correlate of unresponsiveness during exposure to dexmedetomidine and propofol,"
*Br J Anaesth* 2020;125(4):518-528, **PMID 32773216**, trial **NCT01889004**. The record was verified
through NCBI E-utilities and the abstract read in full; no fetch-tool summary was used (rules 25 and 39).

**Why this cohort and not another.** QUEUE.md Q8 records a search across PubMed, OpenNeuro, Dryad, Zenodo,
OSF, Figshare and PhysioNet for a deposit pairing EEG with two mechanistically distinct anaesthetics. None
was found, and that remains true of *deposits*. This is the cohort that has the design:

* **47 healthy volunteers, dexmedetomidine (n = 23) or propofol (n = 24)**, 64-channel EEG — an alpha-2
  agonist against a GABAergic agent, which is the adversarial contrast rather than another pair of
  GABAergics;
* **within-subject loss and return of responsiveness at constant dosing**. That is the part nothing else
  offers. It separates state from drug concentration inside one person, which is precisely the separation
  the only deposit we hold (Krause/Banks, intracranial, 10 dexmedetomidine patients) **structurally cannot
  make**: its two drug arms share 0 of 29 patients, and electrode type and data quality are constant within
  patient, so drug arm, montage and quality are nested inside patient identity and no method separates
  them there.

**What we would be checking, stated plainly because it is partly a check on ourselves.** Our own analyses on
the intracranial deposit found that phase-based coupling measures carry almost no information about *which*
agent produced a matched state, while power and complexity measures carry a lot. Kallionpää 2020 and Akeju
2014 (PMID 25187999) between them already imply that pattern; neither tests it with a single statistic, and
our contribution is methodological rather than a new phenomenon. We would like to run that test where the
design is sound rather than where the data happened to be available.

---

## Draft

> **Subject:** Data access enquiry — dexmedetomidine/propofol EEG cohort (Br J Anaesth 2020;125:518-528,
> NCT01889004)
>
> Dear Dr Kallionpää and colleagues,
>
> I am writing about the EEG recordings behind your 2020 *British Journal of Anaesthesia* paper on
> alpha-band frontal connectivity as a state-specific correlate of unresponsiveness under dexmedetomidine
> and propofol, and to ask whether the data can be made available for reanalysis.
>
> **What I would be asking for.** The 64-channel resting recordings from the 47 volunteers, or the epochs
> around each state transition, together with the per-recording state and drug-concentration labels you
> already report. If sharing recordings is not possible, per-subject per-state derived measures — band
> powers and connectivity estimates at the electrode or region level — would still answer most of the
> question, and I would rather have those than nothing.
>
> **Why this cohort specifically.** I have been testing whether EEG measures that track behavioural state
> also carry information about *which* anaesthetic produced that state — the concern being that a marker
> which identifies the drug is not a marker of the state. The only public dataset I have found with two
> mechanistically distinct agents is an intracranial one in epilepsy-surgery patients where the two drug
> arms share no patients at all, so drug identity, electrode montage and data quality are all confounded
> with each other and cannot be separated by any analysis. Your study has the design that resolves this:
> two agents with different mechanisms, and loss and return of responsiveness within subject at constant
> dosing, so state and concentration come apart in the same person. I have not found another cohort,
> published or deposited, where that is true.
>
> **What I would do with it.** Reanalysis only, no re-identification attempted, no onward sharing, deletion
> on completion or on request, and I am glad to work under whatever data transfer agreement, ethics review
> or local-processing arrangement you require — including running the analysis on your infrastructure if
> that is simpler than moving data. I would share the analysis code before running it and would want you to
> review any description of your data or study before it appeared anywhere.
>
> **Three things I should be straightforward about.** This is exploratory methodological work rather than a
> funded clinical study. Your published result and Akeju et al. 2014 together already imply most of what I
> would be testing, so I am seeking corroboration and a sharper statistical treatment rather than claiming a
> new finding — and I would say so in anything written up. And if the consent or ethics framework under
> which these volunteers participated does not admit reuse of this kind, I would be grateful simply to be
> told that, and I will not press.
>
> If a collaboration would suit you better than a data transfer, I would welcome that; you would know far
> better than I do what these recordings can and cannot support.
>
> With thanks for considering it,
>
> [name, affiliation, contact]

---

## If this is declined

Challenge A's structural blocker stands and should be stated rather than worked around: **every deposit we
can reach has its two anaesthetic agents in disjoint patients**, so agent identity is confounded with every
patient-level covariate. The consequences, in order:

1. **E35 and E36's finding stays unclaimed**, which is already its recorded status. It has external
   corroboration from Kallionpää 2020 and Akeju 2014 in the published literature — that is worth more than
   the internal placebo results and should lead any write-up — but no independent re-analysis by us.
2. **The rule-23 check is unavailable everywhere, not just here.** The Krause deposit ships no raw traces
   (215 entries enumerated, no EDF or iEEG), so the features cannot be recomputed with an independent
   implementation; a request to Krause/Banks for traces is a separate and larger ask than this one.
3. **Nothing else in the queue substitutes.** ds005620 and Chennu are propofol only; DOSE-I is propofol
   only; VitalDB has agents but no identified two-agent within-patient contrast. This is not a matter of
   looking harder — Q8 recorded the search, and Q9 records why the answer does not change.
