---
title: "RSA: a lot in common"
category: Crypto
tags: [rsa, common-modulus, gcd]
technique: "shared modulus + Bézout (common-modulus attack)"
status: solved
---

# RSA: a lot in common

## TL;DR
Two RSA public keys share a modulus (`n1 == n2`) but use different exponents. Given two ciphertexts of
the **same plaintext** under the same `n` with coprime exponents `e1, e2`, Bézout's identity recovers
the plaintext without any factorisation:

```
a*e1 + b*e2 = gcd(e1,e2) = 1
m = c1^a * c2^b (mod n)      # negative exponents => modular inverse
```

## Steps
```python
from math import gcd
g, a, b = egcd(e1, e2)                    # a*e1 + b*e2 = 1
m = (pow(c1, a, n) * pow(c2, b, n)) % n   # handle a<0 with inverse(c1, n)**(-a)
print(bytes.fromhex(hex(m)[2:]))
```

Recovered message: `L_do_you_know_that_gods_of_death_only_eat_apples_...`

## Why this is a classic
RSA does not hide the message; with a small exponent and no padding, the same plaintext encrypted
under several keys is a linear-algebra problem. Real implementations must use OAEP padding and must
never reuse a modulus across keys/tenants.
