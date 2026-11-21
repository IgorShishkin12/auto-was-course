---
title: "Reading (and attacking) gorilla/securecookie sessions"
category: Web
tags: [go, gorilla, securecookie, hmac, session-forgery]
technique: "reference: securecookie wire format & key space"
status: reference
---

# Reading gorilla/securecookie sessions

Several challenges on this course run the same Go/Echo + `gorilla/sessions` skeleton, so it is worth
knowing the cookie format cold.

<svg viewBox="0 0 720 210" width="100%" role="img" aria-label="gorilla/securecookie layout">
<rect x="0" y="0" width="720" height="210" fill="none"/>
<text x="0" y="16" fill="#8b949e" font-family="ui-monospace,monospace" font-size="12">SET-COOKIE: session=</text>
<g font-family="ui-monospace,monospace" font-size="12">
  <rect x="0" y="30" width="300" height="46" rx="8" fill="#141a23" stroke="#232c3a"/>
  <text x="12" y="50" fill="#d2a8ff">base64url(</text>
  <text x="86" y="50" fill="#e6edf3">ts</text><text x="112" y="50" fill="#6e7681">|</text>
  <text x="126" y="50" fill="#e6edf3">payload</text><text x="188" y="50" fill="#6e7681">|</text>
  <text x="202" y="50" fill="#7ee787">MAC</text><text x="236" y="50" fill="#d2a8ff">)</text>
  <text x="12" y="68" fill="#6e7681">one decode → three pipe-separated fields</text>

  <rect x="0" y="92" width="100" height="38" rx="8" fill="#1a2230" stroke="#232c3a"/>
  <text x="12" y="116" fill="#e6edf3">timestamp</text>
  <rect x="112" y="92" width="300" height="38" rx="8" fill="#1a2230" stroke="#232c3a"/>
  <text x="124" y="110" fill="#e6edf3">base64url(gob{"login":"…"})</text>
  <text x="124" y="124" fill="#6e7681">readable — no encryption without a block key</text>
  <rect x="424" y="92" width="120" height="38" rx="8" fill="#1a2230" stroke="#232c3a"/>
  <text x="436" y="116" fill="#7ee787">MAC (32 B)</text>

  <path d="M560 92 L560 60 L430 60" stroke="#7ee787" stroke-dasharray="4 3" fill="none"/>
  <text x="440" y="52" fill="#7ee787" font-size="11">HMAC-SHA256(key, "session|ts|payload")</text>
  <text x="0" y="170" fill="#8b949e" font-size="12">Attack surface: the payload is visible, so a guessable key ⇒ full forgery.</text>
  <text x="0" y="190" fill="#8b949e" font-size="12">cats: random key (rockyou × 14.3 M: no hit).   pillar: not securecookie at all (XOR, no MAC) ⇒ solved.</text>
</g></svg>

## Wire format
`SecureCookie.Encode` (v1.1.x) does:

```go
b = encode(gob_serialize(value))                    // base64url of the gob bytes
b = fmt.Sprintf("%s|%d|%s|", name, timestamp, b)    // "session|1795226492|DX8E...|"
mac = HMAC(hashKey, "session|1795226492|DX8E...")   // note: without the trailing '|'
b = append(b, mac...)[len(name)+1:]                 // drop "session|"
cookie = base64url(b)                               // "1795226492|DX8E...|<32 bytes>"
```

So after one `base64` decode you get three pipe-separated fields: **timestamp | payload | MAC**. The
payload is itself base64url of a gob-encoded map — readable with a plain `base64 -d`:

```
\x0f\x7f\x02\x01\x0c\x02\x01\x04\x01\x00\x04\x01\x00*\xff\x80\x00\x01\x04\x01\x06\x03\x04\x04\x08\x02
\tstring\x0c\x07\x00\x05login\x06string\x0c\x0d\x00\x0bsomenewuser
```

That is why "client-side session" challenges are so often solvable: the state is *visible*, only the
integrity tag stands between you and a forged `login=admin`.

## What the tag protects
`mac = HMAC-SHA256(hashKey, name|timestamp|payload)`. There is **no encryption** unless a block key was
supplied (`NewCookieStore` called with two keys). Consequences:

* When sessions are signed but not encrypted, never put secrets in them — anyone can read them.
* The timestamp is inside the MAC scope: `decode` also enforces `MaxAge`, so you cannot "refresh" an old
  cookie without the key.
* If the key is a *file* read at boot (e.g. `secret.txt`), the whole scheme reduces to file permissions.

## Attacking the key
Two honest options:

1. **Guess it.** If the app derives `hashKey` from a word, you can verify candidates offline in
   microseconds — no requests to the server needed:

```python
ts, payload, mac = base64.urlsafe_b64decode(cookie + "==").split(b"|")
msg = b"session|" + ts + b"|" + payload
hmac.new(candidate, msg, sha256).digest() == mac[:32]
```

   I ran the full rockyou list (14.3 M candidates) against a live cookie at ~345 k/s; nothing. A random
   32-character key survives this trivially.

2. **Find a different flaw.** If the key is random, stop attacking the MAC and attack the app: password
   reset, IDOR, mass assignment, CSRF against a privileged bot, or a second app that shares the key.

## Practical checklist for this family
```bash
# decode any session cookie you are given
python3 - <<'PY'
import base64,sys
raw=sys.argv[1]; d=base64.urlsafe_b64decode(raw+"="*(-len(raw)%4))
print(d.split(b"|")[0], d.split(b"|")[1], d.split(b"|")[2].hex())
PY
```
* If the payload ends in readable gob/JSON → signed-only cookie.
* If the three fields are missing → a different scheme (`itsdangerous`, JWT, custom).

## Defensive checklist

* Call `securecookie.New(hashKey, blockKey)` with a **random** 32/64-byte `hashKey` and a 32-byte
  `blockKey` — without the block key the payload is base64, not ciphertext, and any secret in it is
  readable by every user.
* Load keys from a secret manager, not from a file that also ends up in a backup or a `sha256` action.
* Rotate keys with `MaxAge` (the timestamp is inside the MAC scope) and fail closed on decode errors.
* Keep the cookie to an opaque identifier if the state is sensitive — a server-side store removes the
  whole class of "readable/forgeable session" bugs at the cost of one database lookup.

## What it looks like in practice

| Deployment | Cookie | Attack |
|---|---|---|
| this course's `cats` | signed, random key, `SameSite=None` | key brute force: 14.3 M candidates, no hit → dead end |
| this course's `pillar` | not securecookie at all: `base64(xor(login:ts, pad))` | forge `admin:<ts>`, sweep 256 pad bytes → solved |

The second row is why "it looks like a cookie" is not a threat model: read the bytes before you pick a
tool.
