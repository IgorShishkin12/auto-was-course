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
