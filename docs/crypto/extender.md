---
title: "Hash extender — SHA-256 length extension"
category: Crypto
tags: [length-extension, sha256, mac-bypass]
technique: "SHA-256 length extension on a prefix MAC"
status: solved
---

# SHA-256 length extension

## Setup
The service authenticates a request with `SHA256(secret || message)` and compares the digest. Since
SHA-256 is a Merkle–Damgård construction, knowing `H(secret||m)` and `len(secret||m)` is enough to
compute `H(secret || m || padding || suffix)` without the secret.

## Attack
1. Guess the secret length (brute-force 1..40: only one value produces a valid signature).
2. Continue the hash state from the known digest with a forgeable suffix:
   `sha256_padding(msg_len)` + `;admin=1` (any field your target parses).
3. Send the new message with the recomputed digest.

The tricky part here was that the target hex-encodes the *family* field, so the padding bytes had to
be smuggled as ASCII hex inside that field — otherwise the parser rejected the request. Once the
padding is hex-encoded the length bookkeeping still lines up (the server hex-decodes before hashing).

Result: `YDS{…redacted…}`

## Fix
`HMAC-SHA256(key, message)` (or SHA-3/BLAKE2, which are not length-extendable). Prefix-MAC is never a
MAC.
