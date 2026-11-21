---
title: "Pillar — cookie XOR, no authentication tag"
category: Web
host: pillar.is-course.ru
tags: [cookies, xor, bit-flipping, auth-bypass]
technique: "repeating-key XOR cookie, no MAC — forge `admin:<ts>`"
status: solved
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
3. An early, misleading observation: 14/16/17-byte cookies were all rejected, which *looked* like a
   strict length check. It was not — those cookies also carried an invalid token, so the rejection came
   from token validation. The real constraint is only "the login field is the first 4 bytes", and the
   fix is to make the plaintext longer than the observed 15-byte key.

The trick that works: forge `admin:<ts>`, which is 16 bytes and therefore wraps one byte past the
15-byte key. The pad byte at index 15 is unknown, so sweep all 256 candidates:

```python
pt = b"admin:" + str(int(time.time()) + 60).encode()     # 16 bytes
for guess in range(256):
    pad = KEY + bytes([guess])
    ct  = bytes(pad[i % 16] ^ c for i, c in enumerate(pt))
    if try_cookie(b64(ct)):        # "Welcome, admin!"
        break
```

`/` renders the flag once the session login equals `admin`.

## Fix
Use a real, authenticated session format (e.g. gorilla/securecookie with a random 32-byte HMAC key),
never a plain XOR "encryption" of client-side state.
