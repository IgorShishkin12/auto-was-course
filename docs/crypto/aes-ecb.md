---
title: "AES ECB — byte-at-a-time"
category: Crypto
host: aes.is-course.ru
tags: [aes, ecb, chosen-plaintext]
---

# AES ECB byte-at-a-time

## Oracle
```
Output: AES(user_input + secret)
```
Fixed, unknown suffix `secret` appended to attacker-controlled input, encrypted under AES-ECB with a
constant key. ECB is deterministic and block-independent, so equal 16-byte blocks produce equal
ciphertext blocks — that is the whole attack.

## Attack
1. **Find the block size** — send `A`×1, `A`×2, … until the output length jumps; the jump is 16
   (and identical blocks of `A` confirm ECB).
2. **Align** — send `15, 14, …, 0` bytes of padding so the unknown byte sits at the *last* position of
   a block.
3. **Dictionary** — for each candidate byte `c`, submit `pad + known + c` and record the block.
4. **Match** — compare the target block (`pad + known` + unknown byte) with the dictionary; the
   collision reveals one more plaintext byte. Repeat, shifting the alignment every block.

```python
pad = b'A' * (bs - 1 - len(known) % bs)
target = oracle(pad)[:bs*((len(known)//bs)+1)][-bs:]
for c in range(256):
    if oracle(pad + known + bytes([c]))[:bs] == target[-bs:]: known += bytes([c]); break
```
The recovered "secret" is the flag.

## Fix
Use a random IV per message with CBC/CTR, or better an AEAD (AES-GCM/ChaCha20-Poly1305) — and never
concatenate attacker input with a secret.
