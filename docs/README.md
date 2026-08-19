# Band — hosted pace coach

`index.html` is the single-file build of `marathon/tools/pace-coach.html`, published here so it can
be opened on a phone without a local server, a laptop, or a sign-in.

To serve it: **Settings → Pages → Source: Deploy from a branch →
`claude/iphone-marathon-training-app-d2xxuc` / `/docs` → Save.**

It then lives at <https://dgkenn.github.io/Codex-playground-/>.

Note that this makes the page publicly readable. It contains no personal data — the athlete's
profile, sessions and recordings all stay local, in `~/.marathon-coach` and on the phone. Nothing in
this file phones home; the only network request it makes is to Google Fonts.
