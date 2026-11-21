---
title: "Methodology — how these challenges were approached"
category: Misc
tags: [methodology, recon, checklist]
technique: "how these challenges were approached"
status: reference
---

# Methodology

A short, honest description of the loop that produced the writeups in this repo.

## 1. Recon before exploitation
* **Enumerate the target surface.** Certificate Transparency (`crt.sh`, `certspotter`) plus a
  subdomain wordlist found the whole estate — the vhosts are per-challenge, and unknown names answer
  with a 301 to a wildcard, so response *shape* is the discriminator, not DNS.
* **Fingerprint the stack.** `Server:` headers, cookie names, error formats (`{"message":"Not Found"}`
  = Echo, `werkzeug` debug page = Flask, verbose SQL errors = SQLite). The framework tells you which
  classes of bug are idiomatic.

## 2. Read the app, not the payload list
For each target: fetch every route, dump every form (field names!), and diff behaviour anonymous vs
authenticated. Most of the wins here came from *one* overlooked parameter (`dns-server` next to
`command`, `names[].OID` next to `CN`, `progress` next to `score`).

## 3. Measure, don't assume
* Blind XXE → out-of-band DTD.
* Blind SSRF/bot → unique beacon URLs (and a fresh query string every time; bots deduplicate).
* Unknown redirect behaviour → timing oracle, `redirect:"error"` semantics, or a first-party
  navigation whose *absence* of a post-submit beacon proves the navigation happened.

## 4. When a hypothesis fails, falsify it properly
"We sent a CSRF and the password did not change" is not evidence that CSRF is impossible. The
evidence is: the same payload changes *our* password; the server accepts any `Origin`; a
top-level form POST really navigates. Only then does the conclusion "the browser carries no session"
become defensible.

## 5. Offline beats online
Anything computable locally should be: forging a MAC against a known cookie (14 M candidates/s),
GF(2) linear solving instead of deobfuscating 18 KB of OLLVM dispatcher, TLS record decryption with a
recovered master secret.

## 6. Write it down while it is fresh
Every writeup here lists: the sink, the minimal proof, the flag-bearing step (redacted) and the fix.
Flags are deliberately omitted; the reasoning is the deliverable.

## 7. Verify your instruments first

Four hours on the `cats` challenge were spent chasing a target that was behaving perfectly; the
measuring equipment was broken. Every one of these mistakes is easy to repeat.

| Instrument | What it told us | What was actually true |
|---|---|---|
| `webhook.site` beacon | "the bot stopped visiting" | webhook.site had silently stopped recording; the bot was fine |
| `new Image().src = url` | "the bot no longer runs JavaScript" | the object was garbage-collected before the request was issued; a DOM-attached `<img>` fired immediately |
| timing `POST /settings` from the bot | "15 ms vs 11 ms ⇒ anonymous" | the app hashes **fast** (153 ms authenticated vs 154 ms anonymous on warm connections); the oracle could not distinguish anything |
| resubmitting `page.html?v=1…v=9` | "the bot ignores new URLs" | dedup is by path; a genuinely new path was fetched within 12 s |

The rules that follow:

1. **Send one request you control through your sink** before you trust any silence.
2. **Beacons must be attached to the document** (or use `navigator.sendBeacon`, which also survives
   navigation). Anything that can be collected is not a beacon.
3. **Calibrate an oracle on both branches from your own machine**, with warm connections, before you
   read anything into the target's numbers.
4. **One variable per experiment.** When a page is destroyed in 150 ms, a `setTimeout` test measures the
   timeout, not the browser.

## 8. Negative results are deliverables

If the last hypothesis dies, write down *why*: the exact payload, the exact observation, and what would
have to change for the attack to work. The `cats` page is that kind of document — it is more useful to
the organisers than a lucky flag would have been, and it stops the next person from repeating the same
six hours.
