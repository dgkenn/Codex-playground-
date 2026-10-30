# Go live in about ten minutes, with no hosting

The deploy step is gone. Both pages are already live at claude.ai URLs; the only thing the pages
needed from a web host was somewhere to put an email address, and a form service does that.

## The five steps

**1. Make a form (3 min).** [Tally](https://tally.so) or a Google Form. One field: email. Title it
*On-Call Deck — waitlist*. Copy its public URL.

**2. Paste the URL into the page (1 min).** In `oncall-recall/index.html` there is exactly one
placeholder:

```html
<a class="btn" id="joinlink" href="https://REPLACE-WITH-YOUR-FORM-URL">Join the waitlist →</a>
```

Replace that href. Then republish — or send me the URL and I'll do it in one call.

**3. Share both artifacts (1 min).** They are **private by default**, so this is not optional:
- landing page → https://claude.ai/artifact/49R2MzpWQoSaAYUqwVN6b4
- demo (31 cards) → https://claude.ai/artifact/UZmXKHyRwy7nFnTbEZTz8Q

Open each, Share, make the link viewable by anyone. **Test both in a private browser window before
posting.** A dead link in a Reddit post costs you the whole test.

**4. Fix the cross-link (1 min).** The two pages reference each other as `demo.html` and
`index.html`, which works when they sit in one folder but not as separate artifacts. Once the demo's
share link exists, send it to me and I'll replace the relative hrefs with the real URLs. *(Or host
the whole `oncall-recall/` folder on Netlify Drop and the relative links work as-is — but that is the
hosting step this document exists to avoid.)*

**5. Post it (5 min).** Copy from `DEMAND_TEST.md` — the revised version leads with the demo. Program
Discord or GroupMe first, then r/anesthesiology and r/Residency.

## Then stop touching it for 30 days

The rule is frozen: **signups = (4000 / price) / 0.35**, which at $29 is **394**.

| signups in 30 days | action |
|---|---|
| ≥ 394 | build the 60 hours |
| 150–393 | real interest, smaller business — build only if a few hundred a month justifies it |
| 40–149 | niche, not a $4,000/month path |
| < 40 | stop |

Record three things weekly: **signups, source, and the most common objection.** Also watch
**demo-opens vs signups** — high opens with few signups means the price or promise is wrong; low opens
means the post failed and the product was never tested. Those look identical in a signup count and
need opposite fixes.

## What is genuinely left for me

Two one-call jobs, both needing a URL from you: paste the form link, and swap the relative hrefs for
real share URLs. Send either and it is done in a single call.

Everything else needs a human: a Share click, a form, and a post. That is the whole remaining
distance between a built test and a measured number.
