---
title: "RSA: a lot in common"
category: Crypto
host: is-course.ru:7004 (TCP)
tags: [rsa, shared-prime, gcd, factoring]
technique: "two RSA moduli share a prime → gcd factors both"
status: solved
---

# RSA: a lot in common

## TL;DR

The service ("menu, pick an option") generates a **fresh 2048-bit RSA keypair for every session** but
draws its primes from a pool small enough that two keys collide. Two moduli that share a prime factor
fall to a single `gcd` — no factorisation, no maths beyond Euclid. The flag is the plaintext of a
ciphertext produced under one of the two keys.

## The service

```
$ nc is-course.ru 7004
n = <2048-bit decimal>
e = 65537
encrypted message = <hex>

Menu:
1. encrypt
2. ...
3. reset (new keypair)
```

Option 3 re-keys the session; option 1 lets you encrypt an arbitrary message and prints the new `n`,
`e` and the ciphertext — which is how you harvest moduli cheaply.

## The attack

```python
from math import gcd

n0, e0, c0 = parse(banner)        # the key that holds the encrypted flag
n1 = encrypt_and_read_n()          # after one reset
n2 = encrypt_and_read_n()          # after a second reset

p = gcd(n1, n2)                    # shared prime, usually 1024 bits
if p not in (1, n1, n2):
    q = n1 // p                    # both keys are broken, not just one
```

Once a modulus is factored, RSA is invertible:

```python
def factor_and_decrypt(n, e, c, p):
    q = n // p
    d = pow(e, -1, (p - 1) * (q - 1))
    return pow(c, d, n).to_bytes((n.bit_length() + 7) // 8, "big")

msg = factor_and_decrypt(n0, e0, int(c0, 16), gcd(n1, n2))   # if n0 shares that prime
print(msg)
```

If the flag's key does not share with the first pair, keep resetting: with a deliberately small prime
pool a collision appears within a handful of keys. The recovered plaintext is the flag:

```
YDS{…redacted…}
```

## Why this is a classic

RSA's security rests entirely on `N = p·q` being hard to factor. Nothing about that argument survives
if the same `p` is reused across keys: `gcd(N1, N2)` is computed in microseconds and breaks **both**
keys. The two standard ways people get this wrong are (a) a shared prime pool / weak RNG at key
generation, and (b) reusing a modulus across tenants with different exponents (the *common modulus*
attack — `a·e1 + b·e2 = 1` via Bézout, also seen in this competition family).

## Fix

Generate keys with a CSPRNG (`crypto/rand`) and never share primes between keys; if you must rotate
keys, prove they are coprime (`gcd(n_i, n_j) == 1`) before deployment — a handful of lines in a
deploy-time check would have caught this. And use OAEP padding: with padding, a factored modulus is
still the end of the story, but the challenge's raw-textbook encryption also allows related-message
attacks.
