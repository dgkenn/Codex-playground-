# Band — hosted pace coach

Published here so it can be opened on a phone without a local server, a laptop, or a sign-in.

**Open this — no sign-in, no setup, always the newest build:**

```
https://raw.githack.com/dgkenn/Codex-playground-/claude/iphone-marathon-training-app-d2xxuc/docs/index.html
```

On an iPhone, open it in **Bluefy** rather than Safari. Safari has no Web Bluetooth and is not
getting it, so it cannot read the armband; everything else works there.

## Two files, and why

`index.html` is a 5 kB loader that never changes. `pace-coach.html` is the app, rebuilt constantly.
The loader fetches the app from `raw.githubusercontent` and replaces itself with it.

That split exists because no single host does both halves of the job:

| host | renders as a page | serves the newest push |
|---|---|---|
| `raw.githack.com` | yes | **no** — caches hard, and ignores query strings |
| `raw.githubusercontent.com` | no — `text/plain` | yes |
| jsDelivr | no — `text/plain` | yes |
| GitHub Pages | yes | yes — but needs a one-time settings change |

githack's caching is what made this necessary: a fix pushed here could take hours to reach the
phone, which turns every fix into "reload and try again" — a guess, not a debugging loop. Caching a
file that never changes costs nothing, so the loader sits at the stable URL and the app it retrieves
is always current.

It hands over with `document.open()`/`write()`/`close()` rather than an iframe, because Web
Bluetooth and geolocation are gated by Permissions Policy and delegating them into a frame is
unreliable in exactly the third-party WebViews that can reach the armband at all.

GitHub Pages would drop the third party and the loader both, at the cost of a one-time settings
change: **Settings → Pages → Deploy from a branch → `claude/iphone-marathon-training-app-d2xxuc`
→ `/docs` → Save**, then <https://dgkenn.github.io/Codex-playground-/>. The loader works there too,
so nothing needs to change if you do it.

## Confirming which build you have

The footer carries a build id and time. After a fix is pushed, that is how "reload and try again"
gets confirmed rather than assumed. **Copy diagnostics** at the bottom of the page puts that id,
every capability, the tone and sensor state and the last forty log lines on the clipboard — or on
the page as selectable text if the browser has no clipboard API.

Note that this makes the page publicly readable. It contains no personal data — the athlete's
profile, sessions and recordings all stay local, in `~/.marathon-coach` and on the phone. Nothing in
it phones home; the only external request is a non-blocking one to Google Fonts.
