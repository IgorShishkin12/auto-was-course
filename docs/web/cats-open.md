---
title: "cats — CSPRNG session, robots and dead ends (open)"
category: Web
host: cats.is-course.ru
tags: [csrf, admin-bot, securecookie, sameSite, methodology]
---

# cats — analysis (unsolved)

> This challenge is **not solved**. The page documents the full analysis, the falsified hypotheses and
> the exact blocker, because negative results are results.

Status: **not solved**. Everything below is reproducible; the blocker is stated explicitly at the end.

## 1. Application
Go + Echo (`{"message":"Not Found"}` for unknown routes), `gorilla/sessions` client-side session,
nginx/1.28.3, no client-side JavaScript at all (0 inline, 0 `src` on every page).

| Route | Method | Behaviour |
|---|---|---|
| `/` | GET | `Welcome, <login>!`; renders the flag **only** when session login == `admin` |
| `/login` | POST | `login`+`password`; 302 on success, 401 on failure, no rate limit |
| `/register` | POST | `login` must be `^[a-z]+$`; password ≥14 chars with digit+upper+lower+special; logs you in |
| `/settings` | POST | changes the **current session user's** password; no old-password check; no CSRF token; no Origin/Referer check |
| `/feedback` | POST | rate-limited to 1 message / ~4s; the first http(s) URL in the text is handed to an admin bot |
| `/logout` | GET | 302 → `/` |

Session cookie: `base64url(ts|base64url(gob{login})|HMAC-SHA256(key, "session|ts|payload"))`,
`HttpOnly; Secure; SameSite=None`, Max-Age 604800. Key is random — verified by trying all 14.3 M
rockyou candidates against a live cookie at ~345 k/s.

## 2. The admin bot
* Fires 8–12 s after a feedback POST, from `45.76.93.18`, UA Chrome/114/macOS, **one navigation per URL**.
* **Deduplicates URLs** — resubmitting the same URL is never revisited. Always append `?x=<random>`.
* Runs JavaScript and loads images on our page (`insecure.github.io` page → beacons arrive with
  `Sec-Fetch-Mode: no-cors`).
* Does **not** render feedback as HTML: a `<script src>` payload, an `<img onerror>` payload and a
  protocol-relative `//host/img` probe (which a real renderer would fetch but a URL-extractor would not)
  all produced zero subresource requests.

## 3. What is proven about cookies
| Test | Result | Conclusion |
|---|---|---|
| `fetch('/register', {credentials:'include'})` from our page | user created | cross-site POSTs **reach** the app |
| same trick for `/settings` with our own credentials | password unchanged | the request is unauthenticated |
| `/login` then `/settings` **from the bot's own page** (self-login) | unchanged | the browser does not keep/send cookies cross-site |
| top-level form POST to `/settings` (page destroyed ⇒ navigation happened, post-submit beacon never fired) | unchanged | even a first-party POST changes nothing |
| timing: `GET /settings` vs `GET /login` on the bot (20 samples) | +2–4 ms on `/settings` | consistent with a 302→`/login` hop ⇒ anonymous |

Server side is *not* the problem: `/settings` accepts `Origin: https://evil.example`, `Origin: null`
and no `Origin` at all, and still changes the password for a valid session.

## 4. Dead ends (do not retry)
stored XSS through feedback · reflected XSS (`/?message`, `/?error` are Go-escaped) · GET-based CSRF ·
mass assignment on `/settings` and `/register` · `admin` homoglyph/whitespace/case collisions on
register · SQLi on login · session key brute force · `/posts`, `/api`, `/admin`, ~110 route words ·
admin password lists (top-10 k + themed generator, 10 537 tries, ~46 req/s, no lockout).

## 5. Blocker
Since 01:29 UTC the admin bot has not visited any submitted URL at all — not our pages, not a plain
`webhook.site` URL, and not from a freshly registered account. While that is the case the last open
experiment cannot run: a **bcrypt timing oracle** on `POST /settings` from the bot's page
(authenticated ⇒ the app must hash, ~100–300 ms; anonymous ⇒ early 302, ~5 ms), which would settle
whether the bot carries a session at all, followed by an immediate CSRF if it does.

## 6. Next actions when the bot is back
1. Submit a page that: POSTs `/settings` and reports the fetch duration → authenticated or not.
2. If authenticated: same page retries the password change every 3 s for 60 s (in case the session is
   established mid-visit), then log in as `admin` with the new password.
3. If not authenticated: the challenge instance is broken for everyone (the bot's login is failing);
   report it rather than keep hammering.
