---
title: "Hash extender — SHA-256 length extension"
category: Crypto
host: extender.is-course.ru
tags: [length-extension, sha256, mac-bypass, hex-fields]
technique: "SHA-256 length extension on a prefix MAC, glue smuggled through hex fields"
status: solved
---

# SHA-256 length extension

## TL;DR

The session cookie is `login:name:family:MAC`, where

```
MAC = SHA256(secret || name || ":" || family || ":" || login)
```

— a *prefix* MAC, not HMAC. Knowing one valid `(message, MAC)` pair, we can compute a valid MAC for
`message || glue || ":admin"` without the secret, which flips the trailing field to `admin`.

## Why it works

SHA-256 is a Merkle–Damgård hash: `H(m)` is the final chaining state after processing `m` in 64-byte
blocks. If you are handed that state, you can keep hashing as if you had processed `m` yourself, so

```
H(secret||m||padding(len(secret||m))||suffix)
```

is computable from `H(secret||m)` and the *length* of `secret||m`. The glue is the MD padding of the
original message — a specific blob starting with `0x80`, full of zero bytes, ending with the bit length.
Nobody validates that the message is well-formed, so anything appended after the glue is hashed as part
of the same message.

## Recovering the secret length

The secret is 32 bytes here, but guessing costs nothing: try lengths 1…64, extend for each, and keep the
one whose MAC the server accepts (or, offline, the one whose digest matches a pair you already have).

## The awkward part: the fields are hex

The cookie is `hex(login):hex(name):hex(family):hex(mac)`. The server hex-decodes each field and then
concatenates, so the glue bytes (which include `0x80`, `0x00` and the length) are transmitted as plain
hex — no escaping needed. What *does* need care is the reconstruction: after extending, the new message
must still split into exactly three fields, with the last one reading `admin`.

```python
from shaext import extend, pad

raw = base64.b64decode(cookie).decode()
lh, nh, fh, sig = raw.split(":")
name, fam, lg = bytes.fromhex(nh), bytes.fromhex(fh), bytes.fromhex(lh)
SECLEN = 32
M = name + b":" + fam + b":" + lg                      # the message the server MACs
Y = b":admin"

nd = extend(bytes.fromhex(sig), SECLEN + len(M), Y)    # forged digest
E  = M + pad(SECLEN + len(M)) + Y                      # forged message
assert E.endswith(b":admin")

login_new = b"admin"
name_new  = E[:len(name)]
fam_new   = E[len(name) + 1 : len(E) - len(Y)]
assert name_new + b":" + fam_new + b":" + login_new == E

cookie = "%s:%s:%s:%s" % (login_new.hex(), name_new.hex(), fam_new.hex(), nd.hex())
requests.get(BASE + "/", cookies={"session": base64.b64encode(cookie.encode()).decode()})
```

The response greets `Welcome, admin!` and prints the flag:

```
YDS{…redacted…}
```

## Takeaway

`SHA256(key || message)` is not a MAC. The attack works on any Merkle–Damgård hash without a final
length-masking step (MD5, SHA-1, SHA-256, SHA-512); SHA-3 and BLAKE2 are immune because their output is
not the full internal state.

## Fix

```
HMAC-SHA256(key, message)          # or SHA-3/BLAKE2, or a keyed AEAD
```

If you must build your own construction, hash `SHA256(key || SHA256(key || message))` — but do not;
use HMAC.
