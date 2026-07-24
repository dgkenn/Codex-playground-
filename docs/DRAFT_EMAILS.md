# Draft Contact Emails (Hurdle H4 — for the user to review, adapt, and send)

These are drafts. They disclose AI assistance plainly, ask narrow questions, and make the smallest possible claim. Send from your own account; adjust anything that misstates your situation. Do not send both to the same thread — they are independent contacts.

---

## Email 1 — To Dave Platt (dave.platt@bris.ac.uk), cc Tim Trudgian if desired

**Subject:** RH verification beyond 3·10^12 — is an extension already underway?

Dear Dr. Platt,

I am exploring the feasibility of extending your 2021 verification (Bull. LMS 53, with Trudgian) from 3·10^12 to slightly beyond 10^13 — the height that, per Table 1 of the Polymath15 paper and your own Corollary 2 mechanism, would establish Λ ≤ 0.19 for the de Bruijn–Newman constant.

Before investing further, I have three questions I hope you can answer briefly:

1. Are you, or anyone you know of, already running or planning such an extension? I have no wish to duplicate work, and every reason to defer to or join an existing effort.
2. Is the Arb-based verification code from the 2021 computation available in any form? I understand from your 2017 Math. Comp. paper that reconstruction from the published algorithm is feasible, but the original implementation would obviously be preferable for reproducibility (my plan gates any large computation behind bit-level reproduction of a published segment first).
3. If neither of the above, would you have any interest in advising or collaborating on such an extension?

For full transparency: my planning to date has been heavily AI-assisted (literature reconstruction, source auditing, and a small working ball-arithmetic prototype via python-flint — sign certification plus a Lehman–Brent/Trudgian completeness certificate, validated against Odlyzko's tables at low height). I am aware this changes nothing about the standards the actual computation must meet, which is why I am writing to the people whose pipeline and standards these are.

With thanks for your time,
[name, affiliation]

---

## Email 2 — To Polymath15 contacts (Terence Tao; and/or via the dbn_upper_bound repository maintainers)

**Subject:** Polymath15 Table 1, row Λ ≤ 0.19 — toolchain question for the barrier computation

Dear Professor Tao,

A short provenance question about the Polymath15 paper (Res. Math. Sci. 6 (2019)), specifically Table 1's conditional row X = 2·10^13 + 131,252 (t₀ = 0.180, y₀ = 0.14142, Λ ≤ 0.19).

Section 8.4 documents the barrier computation for the unconditional Λ ≤ 0.22 result and points to the repository's Arb directory, and §10 records that all Table 1 barrier runs produced winding number 0 with 20-digit mesh accuracy (10 for the two highest rows). What I could not determine from the paper or wiki is whether the *conditional* rows' barrier and asymptotic verifications — row Λ ≤ 0.19 in particular — were run with the Arb ball-arithmetic implementation, or with the Pari/GP scripts, or a mixture.

The context: I am scoping an RH verification extension to X/2 ≈ 10^13 that would discharge that row's hypothesis (i) and yield Λ ≤ 0.19, and I want the resulting chain of evidence to meet a uniform interval-arithmetic standard end to end. If the row-3 computations were not fully ball-arithmetic, I would plan a re-run of the barrier and asymptotic checks in Arb (archiving certificates) as part of the project rather than discovering the gap later.

If there is a better contact for this (Rudolph Dwars or the km-git-acc repository maintainer, perhaps), a pointer would be equally appreciated. For transparency, my planning has been heavily AI-assisted; the question above is exactly the kind of thing that auditing surfaced as unresolvable from the published record alone.

With thanks,
[name, affiliation]

---

**Send-checklist:** fill in name/affiliation · confirm current email addresses · attach nothing · if either recipient replies "already underway," the project pivots to offering help per `HURDLES.md` H9 and `PROPOSAL.md` §7's scooping-to-derisking conversion.
