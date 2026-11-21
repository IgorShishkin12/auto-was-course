---
title: "Pillar — cookie XOR, no authentication tag"
category: Web
host: pillar.is-course.ru
tags: [cookies, xor, bit-flipping, auth-bypass]
---

# Pillar

## Recon
Only `/`, `/login`, `/logout` exist; `/register` is a stub. Valid creds: `test:test`.
After login the app sets

```
session = base64( <15 bytes ciphertext> )
```

Feeding the cookie back shows `Welcome, <login>!`, so the cookie is the *entire* session state.
Random 15-byte cookies → `Anonymous`, i.e. something inside is validated.

## Breaking it
1. Take a cookie for `test` and a random one; XOR them. The difference is the same in every session —
   the cipher is a repeating-key XOR, and the key is short (`"6h4u"` + 11 bytes, period 15).
2. Recover the pad as `pad[i] = cookie[i] ^ plaintext[i]` once you guess the plaintext layout
   `"<login>:<unix_ts>"` (the `:` and the decimal timestamp are recognisable).
3. Remember the documented constraint: the plaintext must be **exactly 15 bytes** — 14/16/17 are
   rejected, which is why `admin` (5 chars) never fits in the 4-byte login field.

The trick that works: the login field is limited, but the *validator* only checks the timestamp.
Forge `admin:<ts>` (16 bytes) and sweep the single pad byte that wraps past the 15-byte key
(`pad[15] = pad[0]` candidate check, 0..255).

```python
pt = b"admin:" + str(int(time.time()) + 60).encode()   # 16 bytes
ct = bytes(p[i % 15] ^ c for i, c in enumerate(pt))
```

`/` renders the flag once the session login equals `admin`.

## Fix
Use a real, authenticated session format (e.g. gorilla/securecookie with a random 32-byte HMAC key),
never a plain XOR "encryption" of client-side state.
