# Outreach drafts — copy, edit the brackets, send

The highest-EV action identified is "send the portfolio to three people." The friction in that is
writing it, so here it is written. Nothing below needs analysis; it needs your name and a send button.

Portfolio link: **https://claude.ai/artifact/UT9FpcswdpfpoHMSqt5EJ6** — **share it first** (it is
private; one click in the Share menu), or recipients get a dead link.

---

## 1. Warm network — ask for a referral, not a job

The highest-converting message is short, asks for a name rather than work, and makes it easy to say
no. Send three of these. Do not BCC.

> Subject: **odd question — anyone you know evaluating a model or a backtest?**
>
> Hi [name],
>
> I spent the last stretch running a pre-registered research program trying to find a tradeable edge
> in prediction markets — 56 studies, properly frozen specs, blind replication, an adversarial
> verifier. It found no edge, which was the honest answer, but the interesting part turned out to be
> the apparatus: four separate times it caught *my own* specification from producing a false positive.
> One frozen reading would have reported 8,194 arbitrage opportunities that did not exist.
>
> I wrote it up here: [link]
>
> I'm looking to do this for other people — auditing a quantitative claim before money or a decision
> goes behind it, and specifically building verification around AI-generated analysis, which is where
> most of my time went.
>
> Not asking you for work. Just: does anyone come to mind who's sitting on a result that looks too
> good, or a team whose findings keep not replicating? A name is all I need.
>
> [your name]

**Why it's shaped this way:** it leads with a negative result (credible, not salesy), carries one
concrete number, names a specific service rather than "consulting," and asks for a referral — a
question people can answer in ten seconds without committing anything.

---

## 2. Public post — the standalone piece

This is the one with reach. Post it where quantitative people read: Hacker News ("Show HN" is wrong
here; a plain submission of the write-up is right), r/algotrading, r/quant, LinkedIn if your network
is there. The story carries itself; do not frame it as marketing.

> **A frozen spec in my own study would have reported 8,194 arbitrages that didn't exist**
>
> I ran a pre-registered study looking for crossed quotes in a 188-strike options-style ladder. If you
> can buy the higher-probability contract below the price of the lower-probability one, the payoff is
> non-negative in every state — profit with no forecast required.
>
> The data were one-minute candles, which report bid and ask as open/high/low/close. Here is the trap:
> taking one strike's **bid high** against another strike's **ask low** inside the same minute compares
> two different instants. It is not a simultaneous observation, and a "crossing" built that way is an
> artifact.
>
> I had frozen the spec to forbid it and require the close price for every leg. The two readings:
>
> | reading | raw crossings | fee-clearing |
> |---|---|---|
> | close, same minute (eligible) | 6 | **0** |
> | high/low (non-simultaneous) | 18,036 | **8,194** |
>
> On the same minutes, 98.9% of the high/low "opportunities" were uncrossed by at least a cent at the
> close. All six real crossings were 1c against a 2c fee, so each one lost money.
>
> Then the microsecond trade tape showed what is actually there: in a seeded sample, 27 of 250
> apparent opportunities were taken by someone within 100ms — several at the *same microsecond with
> equal sizes*. The arbitrage is real. It is already harvested, three to six orders of magnitude below
> the latency an outside participant has.
>
> Without the simultaneity rule frozen in advance, this study reports eight thousand arbitrages that
> do not exist, with full confidence. It is the clearest case I have for pre-registration in
> backtesting, and the whole program's record is here: [link]

**Note:** check each venue's self-promotion rules, and post from an account with real history. A
removal teaches you nothing.

---

## 3. When someone bites — scope it small on purpose

Do not quote a retainer. Quote one small fixed-fee deliverable; it is easier to approve than an hourly
arrangement and it produces a reference.

> Thanks for the intro / for reaching out.
>
> The cleanest way to start is small and fixed-fee: pick one result you'd like checked — a backtest, a
> model's reported performance, an evaluation that looks surprising. I spend 10–15 hours on it and you
> get a written verdict: what the claim rests on, which parts survive adversarial checking, and
> specifically where it could be producing a false positive. Flat **$[2,000]**, no retainer, no
> commitment past it.
>
> If it's useful we can talk about an ongoing arrangement. If it isn't, you've spent $[2,000] to find
> out, which is cheaper than finding out later.
>
> What I'd need: the code or notebook, the data or a sample, and whatever was written down about the
> methodology before the result was known. That last one matters most and is usually missing.

**Rate maths:** $2,000 for 10–15 hours is $133–200/hour. Two such engagements a month is $4,000.
`TRACK_D.md` has the full table; the short version is that the target is two small audits a month, not
a full-time practice.

---

## What to do with a "no"

Record the objection, not the rejection. The useful signals, in order:

- *"We don't have anything like that"* → wrong audience; stop asking that part of the network.
- *"We do this in-house"* → right audience, wrong buyer; ask who they'd call when in-house disagrees.
- *"Interesting but no budget"* → right audience, right need, wrong timing; ask to follow up in a quarter.
- **Silence** → the message was too long or too much like a pitch. Cut it in half and lead with the
  8,194 number.
