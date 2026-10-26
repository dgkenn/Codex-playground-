# Ceiling and floor: what the evidence says about heart-rate targets for run/walk

Written 26 October 2026, after a run where the 165 ceiling cut six of eight blocks at about 90 s and
the walks waited on a 133 floor. Every citation was located in PubMed; the list is at the end.

**The athlete's numbers:**
- resting heart rate 67, age-predicted maximum 187 (Tanaka), so heart-rate reserve (HRR) = 120;
- the current ceiling, 165, is about **82% HRR** (88% of predicted maximum);
- the current floor, 133, is about **55% HRR** (71%).

## The ceiling

**Age-predicted maximum is a group statistic.** Every common formula has wide individual limits of
agreement (Shookster 2020), about ±10 bpm in Esco 2015. Any %HRmax target can be 10 bpm wrong for one
person.

**Fixed percentages put different people in different physiological zones.**
- At the same %HRmax, people sit on either side of their thresholds (Meyer 1999; Scharhag-Rosenberger
  2010).
- The lactate threshold fell anywhere from 60% to 90% of HRmax across 100 adults (Iannetta 2020).
- %HRR tracks oxygen uptake better than %HRmax (Swain & Leutholtz 1997), but it inherits the same
  scatter.
- In low-fitness adults, 77% HRR sat above the first ventilatory threshold (Goldberg 1988).

**The better anchor is the first ventilatory threshold (VT1, the aerobic threshold), measured, not
predicted.**
- In sedentary adults, prescribing from thresholds beat %HRR prescription: 12 of 12 responded, against
  5 of 12 (Wolpern 2015, a small randomised trial).
- Without a lab, the field measures are:
  - **The talk test.** The last stage where reciting a passage is comfortable sits at VT1 on average
    (Persinger 2004; Foster 2008; reviews Reed & Pipe 2014, Bok 2022). For one person it is
    imprecise: some studies place it nearer the lactate threshold (Quinn & Coons 2011), and the
    individual limits are wide (Sørensen 2020).
  - **Breathing and effort.** RPE 10–11 on the 6–20 scale maps to VT1 (Bok 2022).
  - **Efficiency roll-off.** The heart rate at which speed per heartbeat stops holding. This app
    already reads it from sessions (`threshold.js`); on 5 September it put his VT1 near **150**.
- **DFA-alpha1** (a heart-rate-variability marker of VT1) needs ECG-grade beat intervals: a chest
  strap, not the Verity Sense in motion (Rogers 2021; Gilgen-Ammann 2019; Schäfer & Vagedes 2013).

**Not evidence:**
- **Maffetone (180 − age = 150).** Never validated against VT1; its own authors say so (Maffetone &
  Laursen 2020).
- **The plan's 150.** It agrees with the measurements above by coincidence, not by method.

**Intensity distribution.** Mostly-easy ("polarised") training beats threshold-heavy training in
*trained* athletes (Stöggl & Sperlich 2014; Rosenblat 2019). In recreational runners the results are
mixed (Muñoz 2014; Festa 2020). There is no trial in true novices, so "mostly below VT1, a little
above it" is an extrapolation.

**For this athlete:** 165 every session is very likely above VT1, so these are threshold sessions, not
easy ones. The evidence-backed way to set an easy ceiling is to **measure VT1 with a talk-test ramp**
and use it. Keep a higher ceiling (about 160–169, the "unsure" stage of the same test) for one harder
session a week, after a few weeks of base.

## The floor (when a walk ends)

**No trial supports "walk until heart rate reaches X" for any population.** What exists points
elsewhere:
- **Recovery length matters less than it seems.** 1, 2 or 4 min of recovery changed interval
  performance little, and self-chosen recovery averaged about 2 min (Seiler & Hetlelid 2005,
  trained runners). Recovery length had limited effect on physiological strain (Schoenmakers & Reed
  2019).
- **Self-chosen and fixed recovery differ little.** A 2026 meta-analysis of 16 studies found no
  difference in performance, heart rate or lactate (Lv 2026).
- **Harder work recovers more slowly after the first 30 s.** The first 30 s of heart-rate decay is
  nearly independent of effort; the 2-minute decay is slower after harder work (Imai 1994; Buchheit
  2014). So a fixed floor takes longer to reach after harder blocks.
- **Cardiac drift raises heart rate as a session goes on** (Coyle & González-Alonso 2001; Wingo 2012).
  A fixed floor therefore gets harder to reach late in a session. That is exactly the 134–138 plateau
  above 133 on 26 October.

**A better-reasoned rule** (still physiology, not outcome trials). End the walk, after at least
45 s, at the first of:
1. the floor;
2. a drop of about 25 bpm from the walk's own peak;
3. a plateau, meaning less than 2–3 bpm of change over 20–30 s (added 26 October);
4. a time cap of about 150 s.

## Sensor lag

- **Accuracy.** The Verity Sense agrees closely with chest straps in steady exercise (upper arm mean
  absolute error 1.4 bpm, Schweizer & Gilgen-Ammann 2025). Agreement drops in intervals and above
  80% of maximum (Liu 2025; Yang 2025).
- **The post-block rise is probably mostly the device.**
  - True heart rate starts falling within seconds of stopping (Imai 1994).
  - So a 5–14 bpm rise 15–20 s after a block ends is probably mostly device smoothing and latency.
  - If so, the true heart rate at a block's end was higher than 165, and the measured "maximum" of
    179 is a lagged figure.
- **What would confirm it:** one session wearing a chest strap (Polar H10) at the same time as the
  armband.
- **If confirmed,** the block should end on the *predicted* heart rate, the current value plus its
  slope over the last 10 s × the lag, not on the displayed value.

## Progression and injury

- **Novices get injured more.** About 18 injuries per 1000 h of running for novices, 8 for
  recreational runners (Videbæk 2015).
- **The 10% rule is not supported.** A graded programme based on it did not reduce injuries (Buist
  2008).
- **Fast increases may raise risk.** Novices who raised weekly distance more than 30% over two weeks
  trended toward more injuries, but the result was not statistically significant (Nielsen 2014).
- **Intensity versus volume made no difference** to injury risk (Ramskov 2018).
- **Run/walk gave similar finish times** with less muscle pain (Hottenrott 2016).
- **What this means for the app's ladder:** its 2- and 3-day spacing and its 1.3× spike cap are
  inside this evidence.

## Citations

Bok 2022 Sports Med PMID 35507232 · Buchheit 2014 Front Physiol PMID 24578692 · Buist 2008 Am J
Sports Med PMID 17940147 · Coyle & González-Alonso 2001 Exerc Sport Sci Rev PMID 11337829 · Esco 2015
J Strength Cond Res PMID 25932986 · Festa 2020 Front Sports Act Living PMID 33344993 · Foster 2008 J
Cardiopulm Rehabil Prev PMID 18277826 · Gilgen-Ammann 2019 Eur J Appl Physiol PMID 31004219 ·
Goldberg 1988 Chest PMID 3383662 · Hottenrott 2016 J Sci Med Sport PMID 25467199 · Iannetta 2020 Med
Sci Sports Exerc PMID 31479001 · Imai 1994 J Am Coll Cardiol PMID 7930286 · Liu 2025 J Sports Sci
PMID 40227137 · Lv 2026 PLoS One PMID 42497167 · Maffetone & Laursen 2020 Front Physiol PMID 32300310
· Meyer 1999 Med Sci Sports Exerc PMID 10487378 · Muñoz 2014 Int J Sports Physiol Perform PMID
23752040 · Nielsen 2014 J Orthop Sports Phys Ther PMID 25155475 · Persinger 2004 Med Sci Sports
Exerc PMID 15354048 · Quinn & Coons 2011 J Sports Sci PMID 21774751 · Ramskov 2018 J Orthop Sports
Phys Ther PMID 29895234 · Reed & Pipe 2014 Curr Opin Cardiol PMID 25010379 · Rogers 2021 Front
Physiol PMID 33519504 · Rosenblat 2019 J Strength Cond Res PMID 29863593 · Schäfer & Vagedes 2013 Int
J Cardiol PMID 22809539 · Scharhag-Rosenberger 2010 J Sci Med Sport PMID 19230766 · Schoenmakers &
Reed 2019 J Sci Med Sport PMID 30297216 · Schweizer & Gilgen-Ammann 2025 JMIR Cardio PMID 40116771 ·
Seiler & Hetlelid 2005 Med Sci Sports Exerc PMID 16177614 · Shookster 2020 Int J Exerc Sci PMID
33042384 · Sørensen 2020 J Cardiopulm Rehabil Prev PMID 32604216 · Stöggl & Sperlich 2014 Front
Physiol PMID 24550842 · Swain & Leutholtz 1997 Med Sci Sports Exerc PMID 9139182 · Videbæk 2015
Sports Med PMID 25951917 · Wingo 2012 Exerc Sport Sci Rev PMID 22410803 · Wolpern 2015 BMC Sports Sci
Med Rehabil PMID 26146564 · Yang 2025 Sci Rep PMID 40335520

**Could not be verified:**
- any measurement of the Verity Sense's internal delay;
- any validation of Verity Sense beat intervals for DFA-alpha1 during exercise;
- any trial comparing heart-rate-guided and pace-guided beginner programmes.
