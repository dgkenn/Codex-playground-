# Band — hosted pace coach

`index.html` is the single-file build of `marathon/tools/pace-coach.html`, published here so it can
be opened on a phone without a local server, a laptop, or a sign-in.

**Open it here — no sign-in, no setup:**

```
https://raw.githack.com/dgkenn/Codex-playground-/claude/iphone-marathon-training-app-d2xxuc/marathon/docs/index.html
```

githack serves raw GitHub files as `text/html`. `raw.githubusercontent` sends `text/plain`, so a
browser shows source rather than a page, and jsDelivr does the same. githack also sends
`must-revalidate`, so a push reaches the phone on the next reload — which is what makes the loop
work: fixed in one place, reloaded in the other.

GitHub Pages would give a tidier URL and drop the third party, at the cost of a one-time settings
change: **Settings → Pages → Deploy from a branch → `claude/iphone-marathon-training-app-d2xxuc`
→ `/docs` → Save**, then <https://dgkenn.github.io/Codex-playground-/>. Worth doing eventually, not
worth doing at a trailhead. The build writes to both folders so either route serves the same build.

The footer carries a build id. After a fix is pushed, that is how "reload and try again" gets
confirmed rather than assumed.

Note that this makes the page publicly readable. It contains no personal data — the athlete's
profile, sessions and recordings all stay local, in `~/.marathon-coach` and on the phone. Nothing in
this file phones home; the only network request it makes is to Google Fonts.
